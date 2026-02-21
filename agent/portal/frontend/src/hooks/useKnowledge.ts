import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";
import type { Memory, MemoryListResponse, RecallResponse } from "@/types";

export function useKnowledge(searchQuery?: string) {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMemories = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api<MemoryListResponse>("/api/knowledge?limit=200");
      setMemories(data?.memories || []);
      setError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to load memories";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  // Apply client-side text filter
  const filtered = searchQuery
    ? memories.filter((m) =>
        m.content.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : memories;

  return { memories: filtered, total: memories.length, loading, error, refetch: fetchMemories };
}

export async function rememberFact(content: string): Promise<Memory> {
  return api<Memory>("/api/knowledge", {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export async function recallMemories(
  query: string,
  maxResults = 5
): Promise<RecallResponse> {
  return api<RecallResponse>("/api/knowledge/recall", {
    method: "POST",
    body: JSON.stringify({ query, max_results: maxResults }),
  });
}

export async function forgetMemory(
  memoryId: string
): Promise<{ memory_id: string; deleted: boolean }> {
  return api<{ memory_id: string; deleted: boolean }>(
    `/api/knowledge/${memoryId}`,
    { method: "DELETE" }
  );
}
