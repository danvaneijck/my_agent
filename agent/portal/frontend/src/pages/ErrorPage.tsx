import { useNavigate } from "react-router-dom";
import { Home, RefreshCw, AlertCircle } from "lucide-react";

interface ErrorPageProps {
  error?: Error | string;
  resetError?: () => void;
}

export default function ErrorPage({ error, resetError }: ErrorPageProps) {
  const navigate = useNavigate();

  const errorMessage =
    typeof error === "string"
      ? error
      : error?.message || "An unexpected error occurred";

  const handleRetry = () => {
    if (resetError) {
      resetError();
    } else {
      window.location.reload();
    }
  };

  const handleGoHome = () => {
    if (resetError) {
      resetError();
    }
    navigate("/");
  };

  return (
    <div className="h-full flex items-center justify-center p-4">
      <div className="max-w-md w-full text-center space-y-6">
        {/* Error icon */}
        <div className="relative">
          <div className="w-32 h-32 mx-auto rounded-full bg-red-500/10 border-4 border-red-500/20 flex items-center justify-center">
            <AlertCircle className="text-red-400" size={64} />
          </div>
        </div>

        {/* Message */}
        <div className="space-y-3">
          <h1 className="text-2xl font-bold text-white">Something Went Wrong</h1>
          <p className="text-gray-400">
            We encountered an error while processing your request.
          </p>
          {errorMessage && (
            <div className="bg-surface-light border border-red-500/20 rounded-lg p-3 text-left">
              <p className="text-xs font-mono text-red-400 break-words">
                {errorMessage}
              </p>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <button
            onClick={handleRetry}
            className="w-full sm:w-auto px-4 py-2.5 rounded-lg font-medium bg-surface-light border border-border text-gray-300 hover:bg-surface-lighter hover:text-white transition-colors flex items-center justify-center gap-2"
          >
            <RefreshCw size={18} />
            Try Again
          </button>
          <button
            onClick={handleGoHome}
            className="w-full sm:w-auto px-4 py-2.5 rounded-lg font-medium bg-accent hover:bg-accent-hover text-white transition-colors flex items-center justify-center gap-2"
          >
            <Home size={18} />
            Back to Home
          </button>
        </div>

        {/* Footer */}
        <div className="pt-8 border-t border-border">
          <p className="text-sm text-gray-500">
            If this problem persists, try{" "}
            <button
              onClick={() => {
                localStorage.clear();
                window.location.href = "/";
              }}
              className="text-accent hover:text-accent-hover hover:underline"
            >
              clearing your session
            </button>{" "}
            or{" "}
            <a
              href="/chat"
              className="text-accent hover:text-accent-hover hover:underline"
            >
              contact support
            </a>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
