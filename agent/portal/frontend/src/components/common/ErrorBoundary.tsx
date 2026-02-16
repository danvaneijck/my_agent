/**
 * ErrorBoundary - React error boundary with branded error UI
 */
import { Component, type ReactNode } from "react";
import { AlertCircle, RefreshCw, Home } from "lucide-react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * Error boundary that catches React errors and displays a branded error screen
 */
export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  handleGoHome = () => {
    window.location.href = "/";
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gray-50 dark:bg-surface flex items-center justify-center p-4">
          <div className="max-w-md w-full text-center space-y-6">
            {/* Icon */}
            <div className="flex justify-center">
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-br from-red-500/20 to-red-500/5 rounded-full blur-xl" />
                <div className="relative bg-gradient-to-br from-red-500/10 to-red-500/5 p-6 rounded-full">
                  <AlertCircle className="w-12 h-12 text-red-500" strokeWidth={1.5} />
                </div>
              </div>
            </div>

            {/* Content */}
            <div className="space-y-2">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Something went wrong</h1>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                An unexpected error occurred. Try refreshing the page or going back to the homepage.
              </p>
            </div>


            {/* Actions */}
            <div className="flex flex-col sm:flex-row gap-3 justify-center mt-6">
              <button
                onClick={this.handleReload}
                className="px-6 py-2.5 bg-accent hover:bg-accent-hover text-white rounded-lg font-medium transition-colors inline-flex items-center justify-center gap-2"
              >
                <RefreshCw size={16} />
                Reload Page
              </button>
              <button
                onClick={this.handleGoHome}
                className="px-6 py-2.5 bg-surface-lighter hover:bg-surface-light border border-border text-gray-200 rounded-lg font-medium transition-colors inline-flex items-center justify-center gap-2"
              >
                <Home size={16} />
                Go Home
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
