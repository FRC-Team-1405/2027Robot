// Plays back the Pi-recorded camera feed alongside the log, in sync with the playhead.
//
// A real <video> element, not a canvas -- see bundles.ensure_preview_video on the server
// side: each session's JPEG sequence is transcoded once into an MP4 so this can seek
// natively instead of swapping <img src> per tick. Play/pause is mirrored into the video
// element so it advances smoothly on its own; useThrottledTime only corrects drift after
// a scrub/seek or slow clock skew, it doesn't drive playback frame by frame.
//
// A match has several recordings per camera (auto and teleop are separate enables, and a
// long NT dropout cuts one more), so the panel picks the segment covering the playhead and
// switches the <video> source as the playhead crosses between them. Between sessions it says
// so, with when the next one starts, rather than showing a frozen frame.
//
// Time bases: the playhead is seconds after spec.t0, segments are absolute log seconds, so
// the lookup uses playhead + spec.t0 (see lib/match.ts).

import { useEffect, useRef, useState } from 'react';

import { MODE_LABEL, cameraOptionLabel, cameraSummaries, modeAt, nextSegment, segmentAt, videoTime } from '../lib/match';
import { useClockState, usePlayer, useThrottledTime } from '../player/PlayerContext';
import type { Panel, VisionSegment } from '../player/types';

const DRIFT_TOLERANCE_SEC = 0.15;

export function VisionPanel({ panel }: { panel: Panel }) {
  const { spec } = usePlayer();
  const { playing } = useClockState();
  const time = useThrottledTime(10);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const cameras = (panel.options.cameras as string[] | undefined) ?? [];
  // Older servers ship only static.vision (one video per camera); treat that as a single segment
  // reaching to the end of the log so the panel still works against them.
  const segmentsByCamera: Record<string, VisionSegment[]> = {};
  for (const [cam, entry] of Object.entries(spec.static.vision ?? {})) {
    segmentsByCamera[cam] = [{ video: entry.video, t0: entry.t0, t1: spec.t0 + spec.duration, session: '' }];
  }
  for (const [cam, segs] of Object.entries(spec.static.vision_segments ?? {})) segmentsByCamera[cam] = segs;
  const camerasWithVideo = cameras.filter((c) => segmentsByCamera[c]?.length);

  const [camera, setCamera] = useState<string | null>(() => camerasWithVideo[0] ?? cameras[0] ?? null);

  // If the spec changes (new log) and the previously-selected camera no longer has
  // video, fall back to the first one that does rather than showing a dead player.
  useEffect(() => {
    if (camera && camerasWithVideo.includes(camera)) return;
    setCamera(camerasWithVideo[0] ?? cameras[0] ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spec]);

  const segments = camera ? segmentsByCamera[camera] : undefined;
  const abs = time + spec.t0;
  const entry = segmentAt(segments, abs);
  const targetTime = entry ? videoTime(entry, abs) : NaN;

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !entry) return;
    video.src = entry.video;
  }, [entry?.video]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !entry) return;
    if (playing) {
      video.play().catch(() => {
        // Autoplay can be blocked before the first user gesture -- the drift-correction
        // effect below will keep currentTime right regardless, so this is silent.
      });
    } else {
      video.pause();
    }
  }, [playing, entry?.video]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !entry) return;
    if (Math.abs(video.currentTime - targetTime) > DRIFT_TOLERANCE_SEC) {
      video.currentTime = targetTime;
    }
  }, [time, entry, targetTime]);

  const next = !entry ? nextSegment(segments, abs) : null;
  const mode = modeAt(spec.static.modes, spec.t0, time);

  let placeholder = '';
  if (!entry) {
    if (cameras.length === 0) placeholder = 'No camera configured for this log.';
    else if (!segments?.length) placeholder = `${camera}: ${(camera && spec.static.vision_status?.[camera]?.detail) || 'no vision recording for this window'}.`;
    else if (next) placeholder = `No recording at this moment. Next session starts at ${(next.t0 - spec.t0).toFixed(1)}s.`;
    else placeholder = 'No recording at this moment (after the last session).';
  }

  return (
    <div className="panel panel--vision">
      <div className="panel__title">
        {panel.title}
        {cameras.length > 1 ? (
          <select
            className="vision__camera-select"
            value={camera ?? ''}
            onChange={(e) => setCamera(e.target.value)}
          >
            {cameras.map((c) => (
              <option key={c} value={c} disabled={!segmentsByCamera[c]?.length}>
                {cameraOptionLabel(c, spec.static.vision_status?.[c], Boolean(segmentsByCamera[c]?.length))}
              </option>
            ))}
          </select>
        ) : camera ? (
          <span className="panel__hint">{camera}</span>
        ) : null}
        {mode && <span className={`vision__mode vision__mode--${mode}`}>{MODE_LABEL[mode] ?? mode}</span>}
      </div>
      <div className="panel__body vision__body">
        <video ref={videoRef} className="vision__video" muted playsInline hidden={!entry} />
        {!entry && <div className="vision__placeholder">{placeholder}</div>}
      </div>
      {cameras.length > 0 && (
        <ul className="vision__summary" aria-label="Recordings per camera" title="What each camera has recorded, or why it has nothing">
          {cameraSummaries(cameras, segmentsByCamera, spec.static.vision_status, spec.static.vision_coverage).map((row) => (
            <li
              key={row.camera}
              className={`vision__summary-row${row.ok ? '' : ' vision__summary-row--none'}${row.camera === camera ? ' vision__summary-row--current' : ''}`}
              onClick={() => row.ok && setCamera(row.camera)}
            >
              <strong>{row.camera}</strong> {row.text}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
