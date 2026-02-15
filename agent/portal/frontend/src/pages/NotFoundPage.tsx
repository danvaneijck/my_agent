import { useNavigate } from "react-router-dom";
import { Home, ArrowLeft, Search } from "lucide-react";

export default function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div className="h-full flex items-center justify-center p-4">
      <div className="max-w-md w-full text-center space-y-6">
        {/* 404 graphic */}
        <div className="relative">
          <div className="text-[120px] font-bold text-transparent bg-clip-text bg-gradient-to-r from-accent to-secondary leading-none">
            404
          </div>
          <div className="absolute inset-0 flex items-center justify-center">
            <Search className="text-accent/20" size={80} />
          </div>
        </div>

        {/* Message */}
        <div className="space-y-3">
          <h1 className="text-2xl font-bold text-white">Page Not Found</h1>
          <p className="text-gray-400">
            The page you're looking for doesn't exist or has been moved.
          </p>
        </div>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="w-full sm:w-auto px-4 py-2.5 rounded-lg font-medium bg-surface-light border border-border text-gray-300 hover:bg-surface-lighter hover:text-white transition-colors flex items-center justify-center gap-2"
          >
            <ArrowLeft size={18} />
            Go Back
          </button>
          <button
            onClick={() => navigate("/")}
            className="w-full sm:w-auto px-4 py-2.5 rounded-lg font-medium bg-accent hover:bg-accent-hover text-white transition-colors flex items-center justify-center gap-2"
          >
            <Home size={18} />
            Back to Home
          </button>
        </div>

        {/* Footer */}
        <div className="pt-8 border-t border-border">
          <p className="text-sm text-gray-500">
            Need help? Check the{" "}
            <a
              href="/settings"
              className="text-accent hover:text-accent-hover hover:underline"
            >
              settings
            </a>{" "}
            or{" "}
            <a
              href="/chat"
              className="text-accent hover:text-accent-hover hover:underline"
            >
              start a chat
            </a>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
