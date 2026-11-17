// Shape of GET /api/live/snapshot (server/live_nt.py's read()).

export interface CameraReading {
  connected: boolean;
  current_fps: number | null;
  visible_tag_ids: number[];
  health_score: number | null;
  health_reason: string;
  health_stillness: number | null;
  health_area: number | null;
  health_ambiguity: number | null;
  health_fps: number | null;
  health_jitter: number | null;
  health_acceptance: number | null;
  health_latency: number | null;
  health_multitag: number | null;
  // Computed in live_nt.py from the factors above -- not published by the robot itself.
  motion_score: number | null;
}

export interface LiveSnapshot {
  nt_connected: boolean;
  lin_speed: number | null;
  ang_speed: number | null;
  cross_score: number | null;
  cross_reason: string;
  cameras: Record<string, CameraReading>;
}

export const FACTOR_FIELDS: { key: keyof CameraReading; label: string }[] = [
  { key: 'health_stillness', label: 'Stillness' },
  { key: 'health_area', label: 'Tag area' },
  { key: 'health_ambiguity', label: 'Ambiguity' },
  { key: 'health_fps', label: 'FPS' },
  { key: 'health_jitter', label: 'Jitter' },
  { key: 'health_acceptance', label: 'Acceptance' },
  { key: 'health_latency', label: 'Latency' },
  { key: 'health_multitag', label: 'Multi-tag' },
];
