import { useEffect, useState, useCallback } from "react";

const STORAGE_KEY = "comicme_session_token";

function isBrowser() {
  return typeof window !== "undefined" && typeof localStorage !== "undefined";
}

function generateToken(): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID().replace(/-/g, "");
  }
  return (
    Math.random().toString(36).slice(2) +
    Math.random().toString(36).slice(2) +
    Math.random().toString(36).slice(2)
  ).slice(0, 32);
}

function readStoredToken(): string | null {
  if (!isBrowser()) return null;
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function writeStoredToken(token: string): void {
  if (!isBrowser()) return;
  try {
    localStorage.setItem(STORAGE_KEY, token);
  } catch {
    // ignore quota / private mode errors
  }
}

let cachedToken: string | null = null;

function ensureToken(): string {
  if (cachedToken) return cachedToken;
  const existing = readStoredToken();
  if (existing) {
    cachedToken = existing;
    return existing;
  }
  const fresh = generateToken();
  writeStoredToken(fresh);
  cachedToken = fresh;
  return fresh;
}

/**
 * Read or mint the per-browser session token used by the "My Comics"
 * library. The token is stored in localStorage so it survives page
 * reloads but is wiped when the user clears site data.
 */
export function useSession(): { token: string; reset: () => string } {
  const [token, setToken] = useState<string>("");

  useEffect(() => {
    setToken(ensureToken());
  }, []);

  const reset = useCallback(() => {
    const fresh = generateToken();
    writeStoredToken(fresh);
    cachedToken = fresh;
    setToken(fresh);
    return fresh;
  }, []);

  return { token, reset };
}

/**
 * Read the token synchronously — only safe to call from event handlers or
 * the API helper, not during initial render. Used by lib/api.ts so every
 * fetch gets the header attached without a hook dependency.
 */
export function getSessionToken(): string {
  return ensureToken();
}
