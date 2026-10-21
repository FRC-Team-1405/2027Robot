import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  label: string;
  resetKey?: unknown;
  onError?: (message: string) => void;
}

// Local boundaries isolate cards/sections. The outer boundary also protects the
// page's hooks and view logic so a future render bug cannot unmount the app.
export class HealthBoundary extends Component<Props, { error: string | null }> {
  state = { error: null as string | null };
  static getDerivedStateFromError(error: unknown) {
    return { error: (error instanceof Error ? error.message : String(error)) || 'Unexpected rendering error.' };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`Health Check: ${this.props.label}`, error, info.componentStack);
    this.props.onError?.(`${this.props.label}: ${this.state.error}`);
  }
  componentDidUpdate(previous: Props) {
    if (this.state.error && previous.resetKey !== this.props.resetKey) this.setState({ error: null });
  }
  render() {
    if (!this.state.error) return this.props.children;
    return <div className="health__notification" role="alert">
      <strong>{this.props.label} could not be displayed.</strong>
      <p>{this.state.error}</p>
      <p>Use Retry to try displaying this panel again.</p>
      <button className="health__btn" onClick={() => this.setState({ error: null })}>Retry {this.props.label}</button>
    </div>;
  }
}
