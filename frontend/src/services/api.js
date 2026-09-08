export async function fetchHealth() {
  const res = await fetch("/api/health");
  if (!res.ok) {
    throw new Error(`Health check failed (${res.status})`);
  }
  return res.json();
}

export async function fetchBriefing() {
  const res = await fetch("/api/briefing");
  if (!res.ok) {
    throw new Error(`Briefing failed (${res.status})`);
  }
  return res.json();
}

export async function fetchDiscovery(limit = 5) {
  const res = await fetch(`/api/discovery?limit=${limit}`);
  if (!res.ok) {
    throw new Error(`Discovery failed (${res.status})`);
  }
  return res.json();
}

export async function fetchAudit(limit = 8) {
  const res = await fetch(`/api/audit?limit=${limit}`);
  if (!res.ok) {
    throw new Error(`Audit failed (${res.status})`);
  }
  return res.json();
}

export async function fetchWatches(asOf) {
  const query = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
  const res = await fetch(`/api/watches${query}`);
  if (!res.ok) {
    throw new Error(`Watches failed (${res.status})`);
  }
  return res.json();
}

export async function confirmAction(action) {
  const res = await fetch("/api/actions/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
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
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
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
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
    }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = body.detail || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}
