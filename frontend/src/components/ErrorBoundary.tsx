/**
 * Catches render errors so one broken page does not blank the whole app.
 *
 * Without this, any exception thrown during render unmounts the entire tree and
 * leaves a white screen with nothing to go on — which is exactly how a stale
 * `stats_core` wheel (an engine response missing a field the UI expected)
 * presented: no message, no stack, no clue where to look.
 */
import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** Changing this resets the boundary — e.g. the current route. */
  resetKey?: string;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // The panel shows one line; keep the component stack in the console, which
    // is the only place it can be read after the fact.
    console.error("[stats-analysis] render error", error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="page">
        <div className="error-panel">
          <h2>This page hit an error</h2>
          <p className="muted">
            The rest of the app still works — switch pages to carry on. Your data and saved
            analyses are untouched.
          </p>
          <pre>{error.message}</pre>
          <p className="muted">
            If this followed a code change, a stale <code>stats_core</code> wheel is a common
            cause: run <code>npm run sync-core</code> (or rebuild the image) so the browser gets
            the current Python. The full stack is in the browser console.
          </p>
          <button className="btn" onClick={() => this.setState({ error: null })}>
            Try again
          </button>
        </div>
      </div>
    );
  }
}
