// Mirrors camera_calibration/health_display.severity_word / server/core/severity.py.
// Shared by ReadoutPanel (replay) and the Pit Check page (live) so both color a score
// identically no matter where the bands came from (spec.static.severity for a replay,
// /api/metric-catalog's `severity` field for a live connection).
export interface SeverityBand {
  min: number;
  color: string;
  label?: string;
}

export function severityColor(bands: SeverityBand[], value: number): string {
  if (Number.isNaN(value)) return '#6b7280';
  for (const b of bands) if (value >= b.min) return b.color;
  return '#6b7280';
}
