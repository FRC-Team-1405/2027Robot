# PhotonVision Camera Intrinsics Calibration

Use this procedure for every physical camera that supplies AprilTag poses. Camera intrinsics
describe the camera's lens and image sensor; they are different from the robot-to-camera mount
position and angles in `VisionConstants.CameraConfig.transform`.

PhotonVision's calibration is specific to **one physical camera at one resolution**. Do not copy
values between two cameras of the same model, and do not keep `fx`, `fy`, `cx`, `cy`, or distortion
values after changing resolution, crop, image rotation, lens focus, or the lens itself.

PhotonVision's official procedure is here:
[Calibrating Your Camera](https://docs.photonvision.org/en/latest/docs/calibration/calibration.html).
This guide adds the project-specific step of copying the result into `VisionConstants.java`.

## What the Java values mean

The constructor order is:

```java
new CameraIntrinsics(width, height, fx, fy, cx, cy, distortion)
```

| Java value | Meaning | Where it comes from |
| --- | --- | --- |
| `width` | Horizontal image size (X), in pixels | Calibrated PhotonVision resolution |
| `height` | Vertical image size (Y), in pixels | Calibrated PhotonVision resolution |
| `fx` | Horizontal focal length, in pixel units | Camera matrix row 1, column 1 |
| `fy` | Vertical focal length, in pixel units | Camera matrix row 2, column 2 |
| `cx` | X coordinate of the optical center, in pixels | Camera matrix row 1, column 3 |
| `cy` | Y coordinate of the optical center, in pixels | Camera matrix row 2, column 3 |
| `distortion` | Lens-distortion model | PhotonVision/OpenCV coefficients, unchanged and in order |

The camera matrix displayed or exported by PhotonVision has this layout:

```text
[ fx,  0, cx ]
[  0, fy, cy ]
[  0,  0,  1 ]
```

PhotonVision's eight-value OpenCV distortion order is:

```text
[k1, k2, p1, p2, k3, k4, k5, k6]
```

Copy the coefficients exactly, including negative signs and scientific notation. If the result
contains only five coefficients, append three zeroes; never rearrange the values.

`cx` is normally near `width / 2`, and `cy` near `height / 2`, but those are only sanity checks.
They are calibrated results, not values to replace with the exact image center. Likewise, `fx` and
`fy` cannot be obtained by reading the advertised lens focal length.

## Before collecting images

1. Put the final camera on its final USB port and confirm its PhotonVision nickname (`Left` or
   `Right`). Keep each physical camera associated with its own calibration.
2. Select the resolution and image rotation that the AprilTag pipeline will actually use. For the
   settings recorded in `notes/9-5.md`, that is currently **800 pixels wide by 600 pixels high**.
3. Set and secure the final lens focus. Calibration may be performed before or after mounting, but
   the camera, lens, focus, and resolution must not change afterward. If calibrating on the robot,
   keep the robot/camera stationary and move the board.
4. In PhotonVision's **Cameras > Camera Calibration** view, download a ChArUco target. ChArUco is
   preferred over a plain chessboard.
5. Print at 100% with no “fit to page” scaling, attach the paper to something rigid and flat, then
   measure the actual black-square spacing and marker size with calipers. Enter the measured sizes,
   board width/height, and correct marker dictionary in PhotonVision. Swapping board width and
   height produces a bad calibration.
6. Use bright, diffuse, steady lighting. Avoid motion blur, glare, deep shadows, a bent target, and
   exposure flicker. The detected-corner overlay must line up with the printed board before saving
   a frame.

## Collect and solve

1. Start calibration for the exact pipeline resolution.
2. Keep the camera still and move/tilt the target through the image. Capture the center, all four
   corners, all four edges, close and farther views, portrait and landscape orientations, and
   varied tilts up to about 45 degrees. Avoid collecting many nearly identical or perfectly
   straight-on frames.
3. There is no single required distance. For a close view, make the board fill much of the frame
   without clipping it; for the farthest view, every required corner must still be detected
   reliably. Include several distances between those limits. A useful mix is roughly one-third
   close, one-third middle-distance, and one-third far, while still prioritizing full image-area
   coverage and varied angles.
4. Twelve usable images is the minimum. Aim for roughly 30–50 sharp, genuinely different images
   with calibration corners distributed across the entire image. More duplicate images do not make
   a better calibration.
5. Finish the calibration. As a practical first check, PhotonVision recommends a mean reprojection
   error below about 1 pixel and a calculated field of view within about 10 degrees of the camera
   datasheet. Inspect high-error images, remove blurry or misdetected ones, and recalibrate if the
   coverage or result is poor.
6. Open the completed resolution in PhotonVision's calibration list and record its resolution,
   camera matrix, and distortion coefficients. Download the raw calibration JSON as a backup. Also
   export all PhotonVision settings after both cameras are complete.
7. Repeat the whole procedure for the other physical camera.

## Update `VisionConstants.java`

Change all fields of one `CameraIntrinsics` together. For example, suppose an **illustrative**
800x600 result shows:

```text
camera matrix = [612.34, 0, 401.20, 0, 611.98, 297.85, 0, 0, 1]
distortion    = [0.051, -0.087, -0.001, 0.002, 0.026, 0.0, 0.003, -0.004]
```

The matching Java is:

```java
new CameraIntrinsics(
        800.0,  // width: horizontal/X pixels
        600.0,  // height: vertical/Y pixels
        612.34, // fx
        611.98, // fy
        401.20, // cx
        297.85, // cy
        new double[] { 0.051, -0.087, -0.001, 0.002,
                0.026, 0.0, 0.003, -0.004 })
```

These numbers only demonstrate the mapping; **do not paste them onto the robot**. Replace them with
that camera's PhotonVision result. Notice that `fx`, `fy`, `cx`, and `cy` come from positions
`[0]`, `[4]`, `[2]`, and `[5]` respectively in the flattened 3x3 matrix.

Do not resolve a resolution mismatch by editing only `width` and `height`. The complete calibration
must match what PhotonVision uses, because this project passes the Java camera matrix and distortion
back into PhotonLib for robot pose estimation.

## Validate before competition

- Confirm PhotonVision's selected pipeline mode and the Java `width`/`height` are identical for
  each camera.
- Build and deploy the robot code, then view several known AprilTags from close, far, centered, and
  near-edge positions. Look for stable poses and an optical center reasonably near the image center.
- Place the stationary robot at a few tape-measured poses and compare the estimated field pose.
  Test each camera alone as well as both together; a calibration accidentally copied between
  cameras often becomes obvious here.
- Save the raw calibration JSON and a PhotonVision settings export with the camera nickname,
  physical camera identity, resolution, PhotonVision version, and date in the filename.
- Recalibrate if the physical camera/lens is replaced, focus changes, or any resolution, crop, or
  rotation setting changes. Remeasuring only the mount transform is sufficient when only the
  camera's position or angle on the robot changes.
