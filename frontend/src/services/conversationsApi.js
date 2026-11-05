import { authHeaders } from "./authApi.js";

function notifyUnauthorized() {
  try {
    window.dispatchEvent(new Event("sweaterco:unauthorized"));
  } catch {
    // Non-browser environments do not need the logout event.
  }
}

async function request(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: authHeaders(options.headers || {}),
  });
  if (res.status === 401) {
    notifyUnauthorized();
    throw new Error("Session expired. Please log in again.");
  }
  if (res.status === 204) {
    return null;
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body?.detail || res.statusText || "Conversation request failed";
    const error = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    error.status = res.status;
    throw error;
  }
  return body;
}

export function createConversation() {
  return request("/api/conversations", { method: "POST" });
}

export function fetchConversations(limit = 50, query = "") {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  const trimmed = (query || "").trim();
  if (trimmed) {
    params.set("query", trimmed.slice(0, 100));
  }
  return request(`/api/conversations?${params.toString()}`);
}

export function fetchConversationHistory(conversationId, limit = 50) {
  return request(
    `/api/conversations/${encodeURIComponent(conversationId)}?limit=${encodeURIComponent(limit)}`,
  );
}

export function deleteConversation(conversationId) {
  return request(`/api/conversations/${encodeURIComponent(conversationId)}`, {
    method: "DELETE",
  });
}

/**
 * Detect whether the live backend exposes conversation search/delete.
 * Current production zyh only supports list/create/get — do not call
 * search/delete against it until the teammate branch is deployed.
 */
export async function detectConversationCapabilities() {
  const defaults = { search: false, delete: false };
  try {
    const res = await fetch("/openapi.json", { headers: authHeaders() });
    if (!res.ok) return defaults;
    const spec = await res.json();
    const listParams = spec?.paths?.["/api/conversations"]?.get?.parameters || [];
    const search = listParams.some(
      (param) => (param.name || param?.schema?.title) === "query" || param?.name === "query",
    );
    const del = Boolean(spec?.paths?.["/api/conversations/{conversation_id}"]?.delete);
    return { search: Boolean(search), delete: Boolean(del) };
  } catch {
    return defaults;
  }
}
