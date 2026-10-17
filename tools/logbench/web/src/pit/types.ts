// Shape of GET /api/live/snapshot (server/live_nt.py's read()).

export interface CameraReading {
  connected: boolean;
  current_fps: number;
  visible_tag_ids: number[];
  health_score: number;
  health_reason: string;
  health_stillness: number;
  health_area: number;
  health_ambiguity: number;
  health_fps: number;
  health_jitter: number;
  health_acceptance: number;
  health_latency: number;
  health_multitag: number;
  // Computed in live_nt.py from the factors above -- not published by the robot itself.
  motion_score: number | null;
}

export interface LiveSnapshot {
  nt_connected: boolean;
  lin_speed: number;
  ang_speed: number;
  cross_score: number;
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
