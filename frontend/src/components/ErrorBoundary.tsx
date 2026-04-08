import { Component, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  showDetails: boolean;
}

export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, showDetails: false };
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error("ErrorBoundary caught an error:", error, info);
  }

  handleRetry = (): void => {
    this.setState({ hasError: false, error: null, showDetails: false });
  };

  toggleDetails = (): void => {
    this.setState((prev) => ({ showDetails: !prev.showDetails }));
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-start gap-4 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900">Something went wrong</h2>

          <button
            type="button"
            onClick={this.handleRetry}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-2"
          >
            Try Again
          </button>

          <div className="w-full">
            <button
              type="button"
              onClick={this.toggleDetails}
              className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
              aria-expanded={this.state.showDetails}
            >
              <span className="select-none">{this.state.showDetails ? "▾" : "▸"}</span>
              <span>Show details</span>
            </button>

            {this.state.showDetails && (
              <div className="mt-2 rounded bg-gray-50 p-3 text-xs text-gray-600">
                <p className="font-medium">Error:</p>
                <p className="mt-1 break-words">{this.state.error?.message}</p>
              </div>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
