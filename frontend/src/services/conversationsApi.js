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
  const body = await res.json().catch(() => ({}));
  if (res.status === 401) {
    notifyUnauthorized();
    throw new Error("Session expired. Please log in again.");
  }
  if (!res.ok) {
    const detail = body?.detail || res.statusText || "Conversation request failed";
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}

export function createConversation() {
  return request("/api/conversations", { method: "POST" });
}

export function fetchConversations(limit = 50) {
  return request(`/api/conversations?limit=${encodeURIComponent(limit)}`);
}

export function fetchConversationHistory(conversationId, limit = 50) {
  return request(
    `/api/conversations/${encodeURIComponent(conversationId)}?limit=${encodeURIComponent(limit)}`,
  );
}
