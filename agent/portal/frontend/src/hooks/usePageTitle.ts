/**
 * usePageTitle - Hook to set document title with Nexus branding
 */
import { useEffect } from "react";

/**
 * Sets the document title with Nexus branding
 * @param title - Page-specific title (e.g., "Dashboard", "Projects")
 */
export function usePageTitle(title: string) {
  useEffect(() => {
    const previousTitle = document.title;
    document.title = title ? `${title} - Nexus` : "Nexus - AI Orchestration Platform";

    return () => {
      document.title = previousTitle;
    };
  }, [title]);
}
