// client/src/config/api.ts

declare global {
  interface Window {
    __MUNRO_API_BASE__?: string;
  }
}

const globalWindow: (Window & { __MUNRO_API_BASE__?: string }) | undefined =
  typeof window === "undefined" ? undefined : window;

const runtimeBase =
  typeof globalWindow?.__MUNRO_API_BASE__ === "string"
    ? globalWindow.__MUNRO_API_BASE__
    : "";

const envBase =
  (typeof process !== "undefined" &&
    (process as unknown as { env?: Record<string, string | undefined> })?.env
      ?.REACT_APP_API_BASE) ||
  "";

const isDevelopment =
  typeof process !== "undefined" &&
  (process as unknown as { env?: Record<string, string | undefined> })?.env
    ?.NODE_ENV === "development";

const fallbackBase = isDevelopment
  ? "http://localhost:5000"
  : typeof globalWindow?.location?.origin === "string"
  ? globalWindow.location.origin
  : "";

const resolvedBase = [runtimeBase, envBase, fallbackBase]
  .map((value) => value.trim())
  .find((value) => value.length > 0);

export const API_BASE = resolvedBase ?? "";

if (!API_BASE) {
  // Surface misconfiguration early so API calls don't silently hit the wrong host.
  console.warn(
    "Munro Scout: no API base configured; API requests will be sent to relative URLs."
  );
}

/**
 * Helper to join the API base with a relative path without duplicating slashes.
 */
export function buildApiUrl(path: string): string {
  const normalizedBase = API_BASE.replace(/\/+$/, "");
  const normalizedPath = path.replace(/^\/+/, "");
  if (!normalizedBase) {
    return `/${normalizedPath}`;
  }
  return `${normalizedBase}/${normalizedPath}`;
}
