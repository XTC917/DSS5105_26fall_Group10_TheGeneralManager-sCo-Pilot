import { authHeaders } from "./authApi.js";

async function readError(res, fallback) {
  const body = await res.json().catch(() => ({}));
  const detail = body?.detail ?? body?.message ?? fallback;
  return typeof detail === "string" ? detail : JSON.stringify(detail);
}

function notifyUnauthorized() {
  try {
    window.dispatchEvent(new Event("sweaterco:unauthorized"));
  } catch {
    // non-browser environment; ignore
  }
}

async function authed(path) {
  const res = await fetch(path, { headers: authHeaders() });
  if (res.status === 401) {
    notifyUnauthorized();
    throw new Error("Session expired. Please log in again.");
  }
  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`);
  }
  return res.json();
}

export async function fetchHealth() {
  const res = await fetch("/api/health");
  if (!res.ok) {
    throw new Error(`Health check failed (${res.status})`);
  }
  return res.json();
}

export async function fetchBriefing() {
  return authed("/api/briefing");
}

export async function fetchDiscovery(limit = 5) {
  return authed(`/api/discovery?limit=${limit}`);
}

export async function fetchAudit(limit = 8) {
  return authed(`/api/audit?limit=${limit}`);
}

export async function fetchWatches(asOf) {
  const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
  return authed(`/api/watches${query}`);
}

export async function confirmAction(action) {
  const res = await fetch("/api/actions/confirm", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ action }),
  });
  if (res.status === 401) {
    notifyUnauthorized();
    throw new Error("Session expired. Please log in again.");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body.detail || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}

export async function declineAction(action) {
  const res = await fetch("/api/actions/decline", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ action }),
  });
  if (res.status === 401) {
    notifyUnauthorized();
    throw new Error("Session expired. Please log in again.");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body.detail || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}

export async function sendChat(message, conversationId) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
    }),
  });
  if (res.status === 401) {
    throw new Error("Session expired. Please log in again.");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body.detail || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}

export { readError };
