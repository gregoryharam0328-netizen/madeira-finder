function resolveApiUrl() {
  const envUrl = (process.env.NEXT_PUBLIC_API_URL || "").trim();
  if (envUrl) return envUrl.replace(/\/+$/, "");

  if (typeof window !== "undefined") {
    const origin = window.location.origin;
    // Render production fallback: if frontend env var was not injected at build time,
    // infer backend host from the known service pair.
    if (origin === "https://madeira-frontend.onrender.com") {
      return "https://madeira-backend.onrender.com";
    }
  }

  return "http://localhost:8000";
}

const API_URL = resolveApiUrl();

const FETCH_TIMEOUT_MS = 120_000;

export async function apiFetch(path: string, options: RequestInit = {}) {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  let timer: ReturnType<typeof setTimeout> | null = null;
  let signal = options.signal;
  if (!signal) {
    const controller = new AbortController();
    signal = controller.signal;
    timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
      cache: "no-store",
      signal,
    });
  } catch (e) {
    const raw = e instanceof Error ? e.message : "Network error";
    const isAbort =
      raw === "AbortError" || (typeof DOMException !== "undefined" && e instanceof DOMException && e.name === "AbortError");
    if (timer && isAbort) {
      throw new Error(`Request timed out after ${FETCH_TIMEOUT_MS / 1000}s (${API_URL}${path}).`);
    }
    if (raw === "Failed to fetch" || raw.includes("NetworkError")) {
      throw new Error(
        `Cannot reach the API at ${API_URL}. Start the backend (uvicorn), set NEXT_PUBLIC_API_URL in the frontend .env, and ensure BACKEND_CORS_ORIGINS includes this site’s origin.`
      );
    }
    throw new Error(raw);
  } finally {
    if (timer) clearTimeout(timer);
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = (data as { detail?: unknown }).detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail) && detail.length > 0 && typeof detail[0] === "object" && detail[0] !== null && "msg" in detail[0]
          ? String((detail[0] as { msg: unknown }).msg)
          : `Request failed (${response.status})`;
    throw new Error(message);
  }
  return response.json();
}
