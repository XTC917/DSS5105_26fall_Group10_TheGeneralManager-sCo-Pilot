import { authed } from "./api.js";

export function createConversation() {
  return authed("/api/conversations", { method: "POST" });
}

export function listConversations(limit = 50) {
  return authed(`/api/conversations?limit=${encodeURIComponent(limit)}`);
}

export function fetchConversationHistory(conversationId, { limit = 50, beforeTurnId = null } = {}) {
  const query = new URLSearchParams({ limit: String(limit) });
  if (beforeTurnId !== null) query.set("before_turn_id", String(beforeTurnId));
  return authed(`/api/conversations/${encodeURIComponent(conversationId)}?${query}`);
}

export async function fetchAllConversationHistory(conversationId) {
  const history = await fetchConversationHistory(conversationId);
  let turns = history.turns;
  let cursor = history.next_before_turn_id;
  while (cursor !== null) {
    const older = await fetchConversationHistory(conversationId, { beforeTurnId: cursor });
    turns = [...older.turns, ...turns];
    cursor = older.next_before_turn_id;
  }
  return { ...history, turns };
}

export function assistantMessage(answer, meta = {}, turnId = null) {
  return {
    role: "assistant",
    content: answer,
    toolsUsed: meta.tools_used || [],
    traces: meta.traces || [],
    limitation: meta.limitation,
    routingIntent: meta.routing_intent,
    proposedActions: (meta.proposed_actions || []).map((action) =>
      turnId === null ? action : { ...action, _turn_id: turnId },
    ),
    charts: meta.charts || [],
    tables: meta.tables || [],
    clarification: meta.clarification || null,
    decision: meta.decision || null,
  };
}

export function turnsToMessages(turns) {
  return (turns || []).flatMap((turn) => [
    { role: "user", content: turn.question },
    assistantMessage(turn.answer, turn.response_json || {}, turn.id),
  ]);
}
