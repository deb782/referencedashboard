import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) {
    // Surface the real cause (helps diagnose blank/white screens in production)
    // eslint-disable-next-line no-console
    console.error("[AppError]", error, info?.componentStack);
  }
  componentDidUpdate(prev) { if (prev.routeKey !== this.props.routeKey && this.state.error) this.setState({ error: null }); }
  render() {
    if (this.state.error) {
      return (
        <div className="max-w-lg mx-auto py-24 text-center" data-testid="route-error">
          <div className="overline mb-3">Something went wrong</div>
          <h2 className="font-display text-3xl font-medium text-ink tracking-tight">This screen hit an error.</h2>
          <p className="text-sm text-ink2 mt-3">The rest of the app is fine. Try reloading this section.</p>
          <button onClick={() => window.location.reload()} className="btn-primary mt-6">Reload</button>
        </div>
      );
    }
    return this.props.children;
  }
}
