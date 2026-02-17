import { useState, useEffect } from "react";
import { api } from "@/api/client";

export function useProviders() {
  const [providers, setProviders] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchProviders() {
      try {
        const data = await api<{ providers: string[] }>("/api/repos/providers");
        setProviders(data.providers || []);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to fetch providers");
        setProviders([]);
      } finally {
        setLoading(false);
      }
    }
    fetchProviders();
  }, []);

  return { providers, loading, error };
}
