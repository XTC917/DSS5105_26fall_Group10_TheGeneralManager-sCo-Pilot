import { authHeaders } from "./authApi.js";

function notifyUnauthorized() {
  try {
    window.dispatchEvent(new Event("sweaterco:unauthorized"));
  } catch {
    // Non-browser environment.
  }
}

async function conversationRequest(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: authHeaders(options.headers || {}),
  });

  const body = await response.json().catch(() => ({}));

  if (response.status === 401) {
    notifyUnauthorized();
    throw new Error("Session expired. Please log in again.");
  }

  if (!response.ok) {
    const detail =
      body?.detail ??
      body?.message ??
      `Request failed (${response.status})`;

    throw new Error(
      typeof detail === "string" ? detail : JSON.stringify(detail),
    );
  }

  return body;
}

export function createConversation() {
  return conversationRequest("/api/conversations", {
    method: "POST",
  });
}

export function listConversations(limit = 50) {
  return conversationRequest(
    `/api/conversations?limit=${encodeURIComponent(limit)}`,
  );
}

export function fetchConversationHistory(
  conversationId,
  { limit = 50, beforeTurnId = null } = {},
) {
  const query = new URLSearchParams({
    limit: String(limit),
  });

  if (beforeTurnId !== null) {
    query.set("before_turn_id", String(beforeTurnId));
  }

  return conversationRequest(
    `/api/conversations/${encodeURIComponent(conversationId)}?${query}`,
  );
}