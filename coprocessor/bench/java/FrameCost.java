// Times each step PhotonVision does per camera frame, using the same native libraries PhotonVision
// uses (WPILib's OpenCV and AprilTag detector, loaded from PhotonVision's own jar on the Pi).
// Built by the experiment runner (tools/exprunner) and run on the Pi by coprocessor/bench/run.sh.
//
// Modes (every mode writes one JSON file, --out):
//   selftest  --out F [--frames-out F.mjpg] [--count N] [--width W --height H]
//             Makes synthetic frames with two tags, saves them as an MJPEG file, then runs a short
//             "steps" pass on them. Checks the program and libraries work without a camera.
//   inspect   --frames F.mjpg --out F
//             Frame count, sizes, and the JPEG layout (1-channel grey or 3-channel colour).
//   steps     --frames F.mjpg --out F [--max N] [--decimates 1,2,3] [--threads 1,4,8]
//             [--iterations 100,40] [--warmup N]
//             Per-step time for each frame: decode to colour, decode to grey, colour -> grey,
//             detect for each decimate x threads, and the 3D pose step (single-tag orthogonal
//             iteration, multi-tag solvePnP SQPNP).
//   inflight  --frames F.mjpg --out F [--workers 1,2,3,4] [--decimate 2] [--detector-threads 1]
//             [--decode color|gray] [--iterations 100] [--seconds 10] [--warmup-seconds 2]
//             N worker threads, each with its own detector, each taking the next frame:
//             "several frames in flight". Reports frames/s and per-frame time for each N.
//
// Detector settings mirror PhotonVision v2026.1.1's AprilTagPipeline.setPipeParamsImpl.

import edu.wpi.first.apriltag.AprilTag;
import edu.wpi.first.apriltag.AprilTagDetection;
import edu.wpi.first.apriltag.AprilTagDetector;
import edu.wpi.first.apriltag.AprilTagFieldLayout;
import edu.wpi.first.apriltag.AprilTagFields;
import edu.wpi.first.apriltag.AprilTagPoseEstimator;
import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.geometry.Rotation3d;
import edu.wpi.first.math.geometry.Transform3d;
import edu.wpi.first.math.geometry.Translation3d;
import edu.wpi.first.util.RawFrame;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.lang.reflect.Method;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import org.opencv.calib3d.Calib3d;
import org.opencv.core.Core;
import org.opencv.core.CvType;
import org.opencv.core.Mat;
import org.opencv.core.MatOfByte;
import org.opencv.core.MatOfDouble;
import org.opencv.core.MatOfPoint2f;
import org.opencv.core.MatOfPoint3f;
import org.opencv.core.Point;
import org.opencv.core.Point3;
import org.opencv.core.Rect;
import org.opencv.core.Scalar;
import org.opencv.core.Size;
import org.opencv.imgcodecs.Imgcodecs;
import org.opencv.imgproc.Imgproc;

public final class FrameCost {
    static final double TAG_SIZE_M = 0.1651; // 6.5 in, PhotonVision's 36h11 tag width

    public static void main(String[] argv) throws Exception {
        if (argv.length == 0) {
            System.err.println("usage: FrameCost <selftest|inspect|steps|inflight> --key value ...");
            System.exit(2);
        }
        String mode = argv[0];
        Args a = new Args(Arrays.copyOfRange(argv, 1, argv.length));
        String loader = loadNatives();
        Json out = new Json();
        out.put("mode", mode);
        out.put("env", env(loader));
        switch (mode) {
            case "selftest" -> selftest(a, out);
            case "inspect" -> inspect(a, out);
            case "steps" -> steps(a, out);
            case "inflight" -> inflight(a, out);
            default -> {
                System.err.println("unknown mode: " + mode);
                System.exit(2);
            }
        }
        Path dest = Path.of(a.req("out"));
        a.checkAllUsed();
        if (dest.getParent() != null) Files.createDirectories(dest.getParent());
        Files.writeString(dest, out.toString() + "\n", StandardCharsets.UTF_8);
        System.out.println("wrote " + dest);
    }

    // ---------------------------------------------------------------- native libraries

    /** On the Pi: PhotonVision's own loader (its jar is on the classpath). Locally: java.library.path. */
    static String loadNatives() throws Exception {
        try {
            Class<?> pv = Class.forName("org.photonvision.jni.LibraryLoader");
            Method m = pv.getMethod("loadWpiLibraries");
            if (!(Boolean) m.invoke(null)) throw new IllegalStateException("PhotonVision's loadWpiLibraries() returned false");
            return "photonvision";
        } catch (ClassNotFoundException e) {
            for (String helper : List.of(
                    "edu.wpi.first.util.WPIUtilJNI$Helper",
                    "edu.wpi.first.math.jni.WPIMathJNI$Helper",
                    "edu.wpi.first.apriltag.jni.AprilTagJNI$Helper")) {
                try {
                    Class.forName(helper).getMethod("setExtractOnStaticLoad", boolean.class).invoke(null, false);
                } catch (ClassNotFoundException ignored) {
                    // not in this WPILib version
                }
            }
            for (String lib : List.of("wpiutiljni", "wpimathjni", "apriltagjni", Core.NATIVE_LIBRARY_NAME)) {
                System.loadLibrary(lib);
            }
            return "java.library.path";
        }
    }

    static Json env(String loader) {
        Json e = new Json();
        e.put("loader", loader);
        e.put("java", System.getProperty("java.version"));
        e.put("os_arch", System.getProperty("os.arch"));
        e.put("cpus", Runtime.getRuntime().availableProcessors());
        e.put("opencv", Core.VERSION);
        return e;
    }

    // ---------------------------------------------------------------- frames

    /** Splits an MJPEG stream (JPEGs back to back, as v4l2-ctl --stream-to writes them). */
    static List<byte[]> readFrames(Path file, int max) throws IOException {
        byte[] b = Files.readAllBytes(file);
        List<byte[]> frames = new ArrayList<>();
        int i = 0;
        while (i < b.length - 1 && frames.size() < max) {
            int start = indexOf(b, i, (byte) 0xFF, (byte) 0xD8);
            if (start < 0) break;
            int end = indexOf(b, start + 2, (byte) 0xFF, (byte) 0xD9);
            if (end < 0) break;
            frames.add(Arrays.copyOfRange(b, start, end + 2));
            i = end + 2;
        }
        if (frames.isEmpty()) throw new IOException("no JPEG frames found in " + file);
        return frames;
    }

    static int indexOf(byte[] b, int from, byte x, byte y) {
        for (int i = from; i < b.length - 1; i++) if (b[i] == x && b[i + 1] == y) return i;
        return -1;
    }

    /** Reads the JPEG's frame header: size, channel count and each channel's sampling. */
    static Json jpegLayout(byte[] jpg) {
        Json j = new Json();
        int i = 2;
        boolean dht = false;
        while (i + 4 <= jpg.length) {
            if ((jpg[i] & 0xFF) != 0xFF) break;
            int marker = jpg[i + 1] & 0xFF;
            int len = ((jpg[i + 2] & 0xFF) << 8) | (jpg[i + 3] & 0xFF);
            if (marker == 0xC4) dht = true;
            if (marker == 0xC0 || marker == 0xC1 || marker == 0xC2) {
                int h = ((jpg[i + 5] & 0xFF) << 8) | (jpg[i + 6] & 0xFF);
                int w = ((jpg[i + 7] & 0xFF) << 8) | (jpg[i + 8] & 0xFF);
                int nc = jpg[i + 9] & 0xFF;
                List<String> sampling = new ArrayList<>();
                for (int k = 0; k < nc; k++) {
                    int s = jpg[i + 11 + 3 * k] & 0xFF;
                    sampling.add((s >> 4) + "x" + (s & 0xF));
                }
                j.put("width", w);
                j.put("height", h);
                j.put("channels", nc);
                j.put("sampling", sampling);
                j.put("progressive", marker == 0xC2);
            }
            if (marker == 0xDA) break; // start of scan: header is over
            i += 2 + len;
        }
        j.put("has_huffman_tables", dht); // UVC cameras often leave them out (decoders use the standard ones)
        return j;
    }

    // ---------------------------------------------------------------- detector, as PhotonVision sets it up

    static AprilTagDetector detector(int threads, float decimate) {
        AprilTagDetector d = new AprilTagDetector();
        AprilTagDetector.Config c = new AprilTagDetector.Config();
        c.numThreads = threads;
        c.refineEdges = true; // our pipelines' setting (11-10 PipelineJson)
        c.quadSigma = 0f; // blur 0
        c.quadDecimate = decimate;
        d.setConfig(c);
        AprilTagDetector.QuadThresholdParameters q = new AprilTagDetector.QuadThresholdParameters();
        q.minClusterPixels = 5;
        q.maxNumMaxima = 10;
        q.criticalAngle = 45 * Math.PI / 180.0;
        q.maxLineFitMSE = 10.0f;
        q.minWhiteBlackDiff = 5;
        q.deglitch = false;
        d.setQuadThresholdParameters(q);
        d.addFamily("tag36h11");
        return d;
    }

    /** Keeps what PhotonVision keeps: decision margin >= 30, hamming 0 (our pipeline settings). */
    static List<AprilTagDetection> filter(AprilTagDetection[] raw) {
        List<AprilTagDetection> out = new ArrayList<>();
        for (AprilTagDetection d : raw) if (d.getDecisionMargin() >= 30 && d.getHamming() == 0) out.add(d);
        return out;
    }

    /** Approximate intrinsics: the timing doesn't depend on the exact values. */
    static final class Camera {
        final double fx, fy, cx, cy;
        final Mat k;
        final MatOfDouble dist = new MatOfDouble(0, 0, 0, 0, 0);

        Camera(int w, int h) {
            fx = fy = 0.9 * w;
            cx = w / 2.0;
            cy = h / 2.0;
            k = new Mat(3, 3, CvType.CV_64F);
            k.put(0, 0, fx, 0, cx, 0, fy, cy, 0, 0, 1);
        }
    }

    /** Single-tag pose for every tag (PhotonVision with "single-tag always" on): undistort + orthogonal iteration. */
    static void singleTagPoses(List<AprilTagDetection> dets, Camera cam, AprilTagPoseEstimator est, int iterations) {
        for (AprilTagDetection d : dets) {
            MatOfPoint2f pts = new MatOfPoint2f();
            Point[] corners = new Point[4];
            for (int i = 0; i < 4; i++) corners[i] = new Point(d.getCornerX(i), d.getCornerY(i));
            pts.fromArray(corners);
            Calib3d.undistortImagePoints(pts, pts, cam.k, cam.dist);
            Point[] u = pts.toArray();
            double[] fixed = new double[8];
            for (int i = 0; i < 4; i++) {
                fixed[2 * i] = u[i].x;
                fixed[2 * i + 1] = u[i].y;
            }
            est.estimateOrthogonalIteration(d.getHomography(), fixed, iterations);
            pts.release();
        }
    }

    /** Multi-tag: one SQPNP solve over every tag in the field layout (as PhotonVision's MultiTargetPNPPipe). */
    static boolean multiTagPose(List<AprilTagDetection> dets, Camera cam, AprilTagFieldLayout layout) {
        List<Point3> obj = new ArrayList<>();
        List<Point> img = new ArrayList<>();
        for (AprilTagDetection d : dets) {
            Optional<Pose3d> p = layout.getTagPose(d.getId());
            if (p.isEmpty()) continue;
            double s = TAG_SIZE_M / 2;
            double[][] local = {{0, -s, -s}, {0, s, -s}, {0, s, s}, {0, -s, s}};
            for (int i = 0; i < 4; i++) {
                Translation3d t = p.get().plus(new Transform3d(new Translation3d(local[i][0], local[i][1], local[i][2]), new Rotation3d())).getTranslation();
                obj.add(new Point3(-t.getY(), -t.getZ(), t.getX())); // NWU -> EDN, as PhotonVision converts
                img.add(new Point(d.getCornerX(i), d.getCornerY(i)));
            }
        }
        if (obj.size() < 8) return false;
        MatOfPoint3f o = new MatOfPoint3f();
        o.fromList(obj);
        MatOfPoint2f im = new MatOfPoint2f();
        im.fromList(img);
        Mat rvec = new Mat(), tvec = new Mat();
        Calib3d.solvePnP(o, im, cam.k, cam.dist, rvec, tvec, false, Calib3d.SOLVEPNP_SQPNP);
        o.release();
        im.release();
        rvec.release();
        tvec.release();
        return true;
    }

    // ---------------------------------------------------------------- modes

    static void inspect(Args a, Json out) throws IOException {
        List<byte[]> frames = readFrames(Path.of(a.req("frames")), Integer.MAX_VALUE);
        out.put("frames", frames.size());
        out.put("jpeg", jpegLayout(frames.get(0)));
        long total = 0;
        for (byte[] f : frames) total += f.length;
        out.put("mean_frame_bytes", total / frames.size());
    }

    static void steps(Args a, Json out) throws IOException {
        List<byte[]> frames = readFrames(Path.of(a.req("frames")), a.integer("max", 200));
        int[] decimates = a.ints("decimates", "1,2,3");
        int[] threads = a.ints("threads", "1,4,8");
        int[] iterations = a.ints("iterations", "100,40");
        int warmup = a.integer("warmup", 30);
        stepsOn(frames, decimates, threads, iterations, warmup, out);
    }

    static void stepsOn(List<byte[]> frames, int[] decimates, int[] threads, int[] iterations, int warmup, Json out) {
        Json layout0 = jpegLayout(frames.get(0));
        out.put("frames", frames.size());
        out.put("jpeg", layout0);
        AprilTagFieldLayout field = AprilTagFieldLayout.loadField(AprilTagFields.kDefaultField);

        Map<String, Timer> t = new LinkedHashMap<>();
        Map<String, AprilTagDetector> dets = new LinkedHashMap<>();
        for (int d : decimates) for (int th : threads) dets.put("detect_dec" + d + "_threads" + th, detector(th, d));
        Map<String, double[]> tagCounts = new LinkedHashMap<>();
        for (String k : dets.keySet()) tagCounts.put(k, new double[1]);

        Camera cam = null;
        AprilTagPoseEstimator est = null;
        int poseFrames = 0, multiFrames = 0;

        for (int pass = 0; pass < 2; pass++) {
            boolean record = pass == 1;
            int n = record ? frames.size() : Math.min(warmup, frames.size());
            for (int i = 0; i < n; i++) {
                MatOfByte buf = new MatOfByte(frames.get(i));

                long s = System.nanoTime();
                Mat color = Imgcodecs.imdecode(buf, Imgcodecs.IMREAD_COLOR);
                long e = System.nanoTime();
                if (record) t.computeIfAbsent("decode_color", x -> new Timer()).add(e - s);

                s = System.nanoTime();
                Mat greyDirect = Imgcodecs.imdecode(buf, Imgcodecs.IMREAD_GRAYSCALE);
                e = System.nanoTime();
                if (record) t.computeIfAbsent("decode_gray", x -> new Timer()).add(e - s);

                Mat grey = new Mat();
                s = System.nanoTime();
                Imgproc.cvtColor(color, grey, Imgproc.COLOR_BGR2GRAY);
                e = System.nanoTime();
                if (record) t.computeIfAbsent("color_to_gray", x -> new Timer()).add(e - s);

                if (cam == null) {
                    cam = new Camera(grey.cols(), grey.rows());
                    est = new AprilTagPoseEstimator(new AprilTagPoseEstimator.Config(TAG_SIZE_M, cam.fx, cam.fy, cam.cx, cam.cy));
                }

                List<AprilTagDetection> poseInput = null;
                for (Map.Entry<String, AprilTagDetector> d : dets.entrySet()) {
                    s = System.nanoTime();
                    AprilTagDetection[] raw = d.getValue().detect(grey);
                    e = System.nanoTime();
                    List<AprilTagDetection> kept = filter(raw);
                    if (record) {
                        t.computeIfAbsent(d.getKey(), x -> new Timer()).add(e - s);
                        tagCounts.get(d.getKey())[0] += kept.size();
                    }
                    if (poseInput == null || kept.size() > poseInput.size()) poseInput = kept;
                }

                if (poseInput != null && !poseInput.isEmpty()) {
                    for (int it : iterations) {
                        s = System.nanoTime();
                        singleTagPoses(poseInput, cam, est, it);
                        e = System.nanoTime();
                        if (record) t.computeIfAbsent("pose_single_all_tags_iter" + it, x -> new Timer()).add(e - s);
                    }
                    s = System.nanoTime();
                    boolean did = multiTagPose(poseInput, cam, field);
                    e = System.nanoTime();
                    if (record && did) {
                        t.computeIfAbsent("pose_multitag", x -> new Timer()).add(e - s);
                        multiFrames++;
                    }
                    if (record) poseFrames++;
                }
                buf.release();
                color.release();
                greyDirect.release();
                grey.release();
            }
        }
        for (AprilTagDetector d : dets.values()) d.close();

        Json steps = new Json();
        for (Map.Entry<String, Timer> e : t.entrySet()) {
            Json s = e.getValue().summary();
            double[] c = tagCounts.get(e.getKey());
            if (c != null) s.put("tags_per_frame", round(c[0] / frames.size(), 2));
            steps.put(e.getKey(), s);
        }
        out.put("steps_ms", steps);
        out.put("frames_with_tags_for_pose", poseFrames);
        out.put("frames_with_multitag", multiFrames);
    }

    static void inflight(Args a, Json out) throws Exception {
        List<byte[]> frames = readFrames(Path.of(a.req("frames")), a.integer("max", 400));
        int[] workers = a.ints("workers", "1,2,3,4");
        int decimate = a.integer("decimate", 2);
        int detThreads = a.integer("detector-threads", 1);
        String decode = a.str("decode", "color");
        if (!decode.equals("color") && !decode.equals("gray")) throw new IllegalArgumentException("--decode color|gray");
        int iterations = a.integer("iterations", 100);
        double seconds = a.dbl("seconds", 10);
        double warmupSeconds = a.dbl("warmup-seconds", 2);
        out.put("frames", frames.size());
        out.put("jpeg", jpegLayout(frames.get(0)));
        out.put("decimate", decimate);
        out.put("detector_threads", detThreads);
        out.put("decode", decode);
        out.put("pose_iterations", iterations);
        out.put("seconds", seconds);

        List<Json> results = new ArrayList<>();
        for (int n : workers) {
            results.add(inflightOnce(frames, n, decimate, detThreads, decode, iterations, warmupSeconds, seconds));
            System.out.println("workers=" + n + " done");
        }
        out.put("by_workers", results);
    }

    static Json inflightOnce(List<byte[]> frames, int n, int decimate, int detThreads, String decode,
                             int iterations, double warmupSeconds, double seconds) throws InterruptedException {
        AtomicLong next = new AtomicLong();
        AtomicBoolean recording = new AtomicBoolean(false);
        AtomicBoolean stop = new AtomicBoolean(false);
        Timer[] timers = new Timer[n];
        long[] counts = new long[n];
        Thread[] ts = new Thread[n];
        AprilTagFieldLayout field = AprilTagFieldLayout.loadField(AprilTagFields.kDefaultField);
        for (int w = 0; w < n; w++) {
            final int id = w;
            timers[w] = new Timer();
            ts[w] = new Thread(() -> {
                AprilTagDetector det = detector(detThreads, decimate);
                Camera cam = null;
                AprilTagPoseEstimator est = null;
                while (!stop.get()) {
                    byte[] jpg = frames.get((int) (next.getAndIncrement() % frames.size()));
                    long s = System.nanoTime();
                    MatOfByte buf = new MatOfByte(jpg);
                    Mat grey;
                    if (decode.equals("color")) {
                        Mat color = Imgcodecs.imdecode(buf, Imgcodecs.IMREAD_COLOR);
                        grey = new Mat();
                        Imgproc.cvtColor(color, grey, Imgproc.COLOR_BGR2GRAY);
                        color.release();
                    } else {
                        grey = Imgcodecs.imdecode(buf, Imgcodecs.IMREAD_GRAYSCALE);
                    }
                    if (cam == null) {
                        cam = new Camera(grey.cols(), grey.rows());
                        est = new AprilTagPoseEstimator(new AprilTagPoseEstimator.Config(TAG_SIZE_M, cam.fx, cam.fy, cam.cx, cam.cy));
                    }
                    List<AprilTagDetection> kept = filter(det.detect(grey));
                    if (iterations > 0 && !kept.isEmpty()) {
                        singleTagPoses(kept, cam, est, iterations);
                        multiTagPose(kept, cam, field);
                    }
                    long e = System.nanoTime();
                    buf.release();
                    grey.release();
                    if (recording.get()) {
                        timers[id].add(e - s);
                        counts[id]++;
                    }
                }
                det.close();
            }, "bench-worker-" + w);
            ts[w].start();
        }
        Thread.sleep((long) (warmupSeconds * 1000));
        long start = System.nanoTime();
        recording.set(true);
        Thread.sleep((long) (seconds * 1000));
        recording.set(false);
        long elapsed = System.nanoTime() - start;
        stop.set(true);
        for (Thread t : ts) t.join();

        Timer all = new Timer();
        long total = 0;
        for (int w = 0; w < n; w++) {
            all.addAll(timers[w]);
            total += counts[w];
        }
        Json r = new Json();
        r.put("workers", n);
        r.put("frames_done", total);
        r.put("frames_per_s", round(total / (elapsed / 1e9), 1));
        r.put("per_frame_ms", all.summary());
        return r;
    }

    static void selftest(Args a, Json out) throws IOException {
        int w = a.integer("width", 800), h = a.integer("height", 600), count = a.integer("count", 60);
        List<byte[]> frames = new ArrayList<>();
        for (int i = 0; i < count; i++) frames.add(syntheticFrame(w, h, i));
        String fo = a.str("frames-out", null);
        if (fo != null) {
            ByteArrayOutputStream all = new ByteArrayOutputStream();
            for (byte[] f : frames) all.write(f);
            Path p = Path.of(fo);
            if (p.getParent() != null) Files.createDirectories(p.getParent());
            Files.write(p, all.toByteArray());
            out.put("frames_file", p.toString());
        }
        stepsOn(frames, new int[] {1, 2}, new int[] {1, 4}, new int[] {40}, 5, out);
    }

    /** A grey frame with tags 1 and 2 (both in the 2026 layout), shifted a little each frame. */
    static byte[] syntheticFrame(int w, int h, int i) {
        Mat img = new Mat(h, w, CvType.CV_8UC1, new Scalar(110 + (i % 20)));
        int size = Math.min(w, h) / 4;
        placeTag(img, 1, w / 6 + (i % 15), h / 3, size);
        placeTag(img, 2, w / 2 + (i % 15), h / 3 + 10, size);
        Mat bgr = new Mat();
        Imgproc.cvtColor(img, bgr, Imgproc.COLOR_GRAY2BGR); // a typical UVC camera sends a 3-channel JPEG
        MatOfByte buf = new MatOfByte();
        Imgcodecs.imencode(".jpg", bgr, buf, new org.opencv.core.MatOfInt(Imgcodecs.IMWRITE_JPEG_QUALITY, 90));
        byte[] b = buf.toArray();
        img.release();
        bgr.release();
        buf.release();
        return b;
    }

    static void placeTag(Mat img, int id, int x, int y, int size) {
        RawFrame f = AprilTag.generate36h11AprilTagImage(id);
        int tw = f.getWidth(), th = f.getHeight(), stride = f.getStride();
        ByteBuffer data = f.getData();
        Mat tag = new Mat(th, tw, CvType.CV_8UC1);
        byte[] row = new byte[tw];
        for (int r = 0; r < th; r++) {
            data.position(r * stride);
            data.get(row, 0, tw);
            tag.put(r, 0, row);
        }
        f.close();
        int border = size / 8;
        Mat big = new Mat();
        Imgproc.resize(tag, big, new Size(size, size), 0, 0, Imgproc.INTER_NEAREST);
        Mat white = new Mat(size + 2 * border, size + 2 * border, CvType.CV_8UC1, new Scalar(255));
        big.copyTo(white.submat(new Rect(border, border, size, size)));
        white.copyTo(img.submat(new Rect(x, y, white.cols(), white.rows())));
        tag.release();
        big.release();
        white.release();
    }

    // ---------------------------------------------------------------- small helpers

    static double round(double v, int places) {
        double m = Math.pow(10, places);
        return Math.round(v * m) / m;
    }

    static final class Timer {
        private long[] ns = new long[256];
        private int n;

        void add(long v) {
            if (n == ns.length) ns = Arrays.copyOf(ns, n * 2);
            ns[n++] = v;
        }

        void addAll(Timer o) {
            for (int i = 0; i < o.n; i++) add(o.ns[i]);
        }

        Json summary() {
            Json j = new Json();
            j.put("n", n);
            if (n == 0) return j;
            long[] s = Arrays.copyOf(ns, n);
            Arrays.sort(s);
            double sum = 0;
            for (long v : s) sum += v;
            j.put("median", round(s[n / 2] / 1e6, 3));
            j.put("p95", round(s[Math.min(n - 1, (int) Math.ceil(0.95 * n) - 1)] / 1e6, 3));
            j.put("mean", round(sum / n / 1e6, 3));
            j.put("min", round(s[0] / 1e6, 3));
            return j;
        }
    }

    /** --key value arguments. Unknown keys are an error, so a typo in a run plan doesn't go unnoticed. */
    static final class Args {
        private final Map<String, String> m = new LinkedHashMap<>();
        private final java.util.Set<String> used = new java.util.HashSet<>();

        Args(String[] a) {
            for (int i = 0; i < a.length; i++) {
                if (!a[i].startsWith("--") || i + 1 >= a.length) throw new IllegalArgumentException("expected --key value, got: " + a[i]);
                m.put(a[i].substring(2), a[++i]);
            }
        }

        String str(String k, String def) {
            used.add(k);
            return m.getOrDefault(k, def);
        }

        String req(String k) {
            String v = str(k, null);
            if (v == null) throw new IllegalArgumentException("missing --" + k);
            return v;
        }

        int integer(String k, int def) {
            return Integer.parseInt(str(k, String.valueOf(def)));
        }

        double dbl(String k, double def) {
            return Double.parseDouble(str(k, String.valueOf(def)));
        }

        int[] ints(String k, String def) {
            return Arrays.stream(str(k, def).split(",")).map(String::trim).mapToInt(Integer::parseInt).toArray();
        }

        void checkAllUsed() {
            for (String k : m.keySet()) if (!used.contains(k)) throw new IllegalArgumentException("unknown option --" + k);
        }
    }

    /** Minimal JSON writer (no dependencies on the Pi beyond PhotonVision's jar). */
    static final class Json {
        private final Map<String, Object> m = new LinkedHashMap<>();

        void put(String k, Object v) {
            m.put(k, v);
        }

        @Override
        public String toString() {
            return write(m);
        }

        static String write(Object v) {
            if (v == null) return "null";
            if (v instanceof Json j) return write(j.m);
            if (v instanceof String s) return '"' + s.replace("\\", "\\\\").replace("\"", "\\\"") + '"';
            if (v instanceof Double d) return String.format(Locale.ROOT, "%s", d);
            if (v instanceof Number || v instanceof Boolean) return v.toString();
            if (v instanceof Map<?, ?> map) {
                StringBuilder b = new StringBuilder("{");
                boolean first = true;
                for (Map.Entry<?, ?> e : map.entrySet()) {
                    if (!first) b.append(", ");
                    first = false;
                    b.append(write(String.valueOf(e.getKey()))).append(": ").append(write(e.getValue()));
                }
                return b.append('}').toString();
            }
            if (v instanceof List<?> list) {
                StringBuilder b = new StringBuilder("[");
                for (int i = 0; i < list.size(); i++) {
                    if (i > 0) b.append(", ");
                    b.append(write(list.get(i)));
                }
                return b.append(']').toString();
            }
            return write(v.toString());
        }
    }
}
