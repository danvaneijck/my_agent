const TOKEN_KEY = "portal_token";
const USER_KEY = "portal_user";

export interface PortalUser {
  user_id: string;
  username: string;
  permission_level: string;
}

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getUser(): PortalUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setUser(user: PortalUser) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export async function api<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${getToken()}`,
    ...(options.headers as Record<string, string>),
  };

  // Don't set Content-Type for FormData (browser sets multipart boundary)
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const resp = await fetch(path, { ...options, headers });

  if (resp.status === 401) {
    clearAuth();
    window.location.reload();
    throw new Error("Unauthorized");
  }

  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`${resp.status}: ${body}`);
  }

  return resp.json();
}

/** Fetch a file as a blob URL (for images, downloads). Caller must revoke. */
export async function apiFetchBlobUrl(path: string): Promise<string> {
  const resp = await fetch(path, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (resp.status === 401) {
    clearAuth();
    window.location.reload();
    throw new Error("Unauthorized");
  }
  if (!resp.ok) throw new Error(`${resp.status}`);
  const blob = await resp.blob();
  return URL.createObjectURL(blob);
}

/** Trigger an authenticated file download in the browser. */
export async function apiDownloadFile(fileId: string, filename: string) {
  const url = await apiFetchBlobUrl(`/api/files/${fileId}/download`);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
