import { authHeaders } from "./authApi.js";
import { readChatStream } from "./chatStream.js";

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

async function authed(path, options = {}) {
  const res = await fetch(path, { ...options, headers: authHeaders(options.headers) });
  if (res.status === 401) {
    notifyUnauthorized();
    throw new Error("Session expired. Please log in again.");
  }
  if (!res.ok) {
    throw new Error(await readError(res, `Request failed (${res.status})`));
  }
  return res.json();
}

export async function fetchHealth() {
  return authed("/api/health");
}

export async function fetchBriefing() {
  return authed("/api/briefing");
}

export async function fetchDiscovery(limit = 5, { all = false } = {}) {
  if (all) return authed("/api/discovery?all=true");
  return authed(`/api/discovery?limit=${limit}`);
}

export async function fetchAudit(limit = 8) {
  return authed(`/api/audit?limit=${limit}`);
}

export async function fetchWatches() {
  return authed("/api/watches");
}

export async function setFactoryDate(factoryDate) {
  return authed("/api/factory-date", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ factory_date: factoryDate }),
  });
}

export async function saveActionOffer(turnId, offer) {
  return authed(`/api/turns/${turnId}/action-offer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt: offer.prompt, action: offer.action }),
  });
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

export async function fetchActionOffer({ question, answer, traces, toolsUsed, proposedActions }) {
  const res = await fetch("/api/action-offers", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      question,
      answer,
      traces,
      tools_used: toolsUsed,
      proposed_actions: proposedActions,
    }),
  });
  if (res.status === 401) {
    notifyUnauthorized();
    throw new Error("Session expired. Please log in again.");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(`Action offer failed (${res.status})`);
  }
  return body;
}

export async function fetchSuggestions({ query, asked, focus, answer }) {
  const res = await fetch("/api/suggestions", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ query, asked, focus, answer: answer || "" }),
  });
  if (res.status === 401) {
    notifyUnauthorized();
    throw new Error("Session expired. Please log in again.");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(`Suggestions failed (${res.status})`);
  }
  return body;
}

export async function sendChat(message, conversationId, clarificationReply = false, originalQuestion = "") {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      clarification_reply: clarificationReply,
      original_question: originalQuestion,
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

export async function sendChatStream(
  message,
  conversationId,
  clarificationReply = false,
  originalQuestion = "",
  handlers = {},
) {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      clarification_reply: clarificationReply,
      original_question: originalQuestion,
    }),
    signal: handlers.signal,
  });
  if (res.status === 401) {
    notifyUnauthorized();
    throw new Error("Session expired. Please log in again.");
  }
  return readChatStream(res, handlers);
}

export { readError };
