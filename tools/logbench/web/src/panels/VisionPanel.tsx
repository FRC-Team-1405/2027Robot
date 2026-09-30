// Plays back the Pi-recorded camera feed alongside the log, in sync with the playhead.
//
// A real <video> element, not a canvas -- see bundles.ensure_preview_video on the server
// side: each session's JPEG sequence is transcoded once into an MP4 so this can seek
// natively instead of swapping <img src> per tick. Play/pause is mirrored into the video
// element so it advances smoothly on its own; useThrottledTime only corrects drift after
// a scrub/seek or slow clock skew, it doesn't drive playback frame by frame.

import { useEffect, useRef, useState } from 'react';

import { useClockState, usePlayer, useThrottledTime } from '../player/PlayerContext';
import type { Panel } from '../player/types';

const DRIFT_TOLERANCE_SEC = 0.15;

export function VisionPanel({ panel }: { panel: Panel }) {
  const { spec } = usePlayer();
  const { playing } = useClockState();
  const time = useThrottledTime(10);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const cameras = (panel.options.cameras as string[] | undefined) ?? [];
  const vision = spec.static.vision ?? {};
  const camerasWithVideo = cameras.filter((c) => vision[c]);

  const [camera, setCamera] = useState<string | null>(() => camerasWithVideo[0] ?? cameras[0] ?? null);

  // If the spec changes (new log) and the previously-selected camera no longer has
  // video, fall back to the first one that does rather than showing a dead player.
  useEffect(() => {
    if (camera && camerasWithVideo.includes(camera)) return;
    setCamera(camerasWithVideo[0] ?? cameras[0] ?? null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spec]);

  const entry = camera ? vision[camera] : undefined;

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

  const targetTime = entry ? time - entry.t0 : NaN;
  const duration = videoRef.current?.duration;
  const outOfRange = Boolean(
    !entry ||
      Number.isNaN(targetTime) ||
      targetTime < 0 ||
      (duration && !Number.isNaN(duration) && targetTime > duration),
  );

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !entry || outOfRange) return;
    if (Math.abs(video.currentTime - targetTime) > DRIFT_TOLERANCE_SEC) {
      video.currentTime = targetTime;
    }
  }, [time, entry, outOfRange, targetTime]);

  return (
    <div className="panel panel--vision">
      <div className="panel__title">
        {panel.title}
        {camerasWithVideo.length > 1 ? (
          <select
            className="vision__camera-select"
            value={camera ?? ''}
            onChange={(e) => setCamera(e.target.value)}
          >
            {cameras.map((c) => (
              <option key={c} value={c} disabled={!vision[c]}>
                {c}{!vision[c] ? ' (no recording)' : ''}
              </option>
            ))}
          </select>
        ) : camera ? (
          <span className="panel__hint">{camera}</span>
        ) : null}
      </div>
      <div className="panel__body vision__body">
        <video ref={videoRef} className="vision__video" muted playsInline hidden={!entry || outOfRange} />
        {(!entry || outOfRange) && (
          <div className="vision__placeholder">
            {cameras.length === 0
              ? 'No camera configured for this log.'
              : !entry
                ? 'No vision recording for this window.'
                : 'Outside the recorded window.'}
          </div>
        )}
      </div>
    </div>
  );
}
