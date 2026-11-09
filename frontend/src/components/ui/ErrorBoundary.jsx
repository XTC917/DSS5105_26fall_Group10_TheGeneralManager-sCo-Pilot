import { Component } from "react";

/**
 * Catches render/lifecycle errors in the wrapped view and shows a friendly
 * fallback instead of a blank white page. "Reload page" refreshes the app so
 * the user can continue.
 */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary] caught an error:", error, errorInfo && errorInfo.componentStack);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="flex min-h-[300px] items-center justify-center">
          <div className="flex min-h-[300px] flex-col items-center justify-center gap-3 rounded-lg border border-line bg-surface p-6 text-center">
            <p className="font-medium text-foreground">Something went wrong.</p>
            {this.state.error && this.state.error.message && (
              <p className="type-caption text-muted">{this.state.error.message}</p>
            )}
            <button
              type="button"
              onClick={this.handleRetry}
              className="focus-ring rounded-control border border-line bg-surface px-3 py-1.5 type-caption font-medium text-foreground transition-colors hover:bg-surfaceMuted"
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
