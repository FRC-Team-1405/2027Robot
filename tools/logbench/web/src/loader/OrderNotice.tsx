// Shown wherever logbench opens a log whose records are out of time order (plain WPILib FRC_*.wpilog:
// NetworkTables values are written a few ms after newer records). Logbench reads each signal on its own,
// so nothing here is affected; the WPILog Janitor needs a time-ordered copy before it can trim the log.

export interface OrderInfo {
  n_late: number;
  late_pct: number;
  max_late_ms: number;
}

export function OrderNotice({ order, className = 'warning' }: { order: OrderInfo | null | undefined; className?: string }) {
  if (!order) return null;
  return (
    <div className={className} role="status">
      {order.n_late.toLocaleString()} records ({order.late_pct.toFixed(1)}%) in this log are out of time order. That doesn't affect
      anything shown here. You can clean it up with the WPILog Janitor (Order page), which makes a time-ordered copy; it needs
      one before it can trim this log.
    </div>
  );
}
