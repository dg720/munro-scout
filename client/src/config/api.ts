// client/src/config/api.ts

const envBase =
  (typeof process !== "undefined" &&
    (process as unknown as { env?: Record<string, string | undefined> })?.env
      ?.REACT_APP_API_BASE) ||
  "";

export const API_BASE = envBase.trim() || "http://localhost:5000";

/**
 * Helper to join the API base with a relative path without duplicating slashes.
 */
export function buildApiUrl(path: string): string {
  const normalizedBase = API_BASE.replace(/\/+$/, "");
  const normalizedPath = path.replace(/^\/+/, "");
  return `${normalizedBase}/${normalizedPath}`;
}
