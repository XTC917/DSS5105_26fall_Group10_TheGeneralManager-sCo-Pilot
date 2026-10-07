import assert from "node:assert/strict";
import { test } from "node:test";
import { assistantMessage, fetchAllConversationHistory, turnsToMessages, listConversations } from "../src/services/conversationsApi.js";

test("restore user and assistant messages, evidence and action ownership", () => {
  const meta = { tools_used: ["get_order_status"], traces: [{ tool: "get_order_status" }],
    routing_intent: "proceed", charts: [{ type: "bar" }], tables: [{ title: "Orders" }],
    proposed_actions: [{ type: "add_order_note", order_id: "ORD-120" }],
    clarification: { options: [{ label: "ORD-120" }] } };
  const messages = turnsToMessages([{ id: 42, question: "How is ORD-120 doing?", answer: "Answer", response_json: meta }]);
  assert.deepEqual(messages.map((message) => message.role), ["user", "assistant"]);
  assert.equal(messages[0].content, "How is ORD-120 doing?");
  assert.equal(messages[1].content, "Answer");
  assert.deepEqual(messages[1].toolsUsed, meta.tools_used);
  assert.deepEqual(messages[1].traces, meta.traces);
  assert.deepEqual(messages[1].charts, meta.charts);
  assert.deepEqual(messages[1].tables, meta.tables);
  assert.deepEqual(messages[1].clarification, meta.clarification);
  assert.equal(messages[1].routingIntent, "proceed");
  assert.equal(messages[1].proposedActions[0]._turn_id, 42);
  assert.equal(meta.proposed_actions[0]._turn_id, undefined);
});

test("new and restored answers share the same rendering metadata", () => {
  const meta = { tools_used: ["find_orders"], limitation: "needs_clarification", proposed_actions: [] };
  const restored = turnsToMessages([{ id: 1, question: "Q", answer: "A", response_json: meta }])[1];
  assert.deepEqual(restored, assistantMessage("A", meta));
  assert.deepEqual(turnsToMessages([]), []);
});

test("restore dismissed decisions without offering the action again", () => {
  const decision = { status: "dismissed", summary: "Dismissed" };
  const messages = turnsToMessages([{ id: 1, question: "Q", answer: "A", response_json: { decision, proposed_actions: [] } }]);
  assert.deepEqual(messages[1].decision, decision);
  assert.deepEqual(messages[1].proposedActions, []);
});

test("fetch every history page in chronological order with existing auth headers", async (t) => {
  const urls = [];
  t.mock.method(globalThis, "fetch", async (url, options) => {
    urls.push(url);
    assert.ok(options.headers);
    const page = urls.length === 1
      ? { conversation: { id: "id" }, turns: Array.from({ length: 50 }, (_, i) => ({ id: i + 4 })), next_before_turn_id: 4 }
      : { conversation: { id: "id" }, turns: [{ id: 1 }, { id: 2 }, { id: 3 }], next_before_turn_id: null };
    return new Response(JSON.stringify(page), { status: 200 });
  });
  const history = await fetchAllConversationHistory("id");
  assert.equal(history.turns.length, 53);
  assert.deepEqual(history.turns.map((turn) => turn.id), Array.from({ length: 53 }, (_, i) => i + 1));
  assert.deepEqual(urls, ["/api/conversations/id?limit=50", "/api/conversations/id?limit=50&before_turn_id=4"]);
});

test("an authorization failure triggers the existing logout event", async (t) => {
  const events = [];
  const previousWindow = globalThis.window;
  globalThis.window = { dispatchEvent: (event) => events.push(event.type) };
  t.after(() => {
    if (previousWindow === undefined) delete globalThis.window;
    else globalThis.window = previousWindow;
  });
  t.mock.method(globalThis, "fetch", async () => new Response("{}", { status: 401 }));
  await assert.rejects(listConversations(), /Session expired/);
  assert.deepEqual(events, ["sweaterco:unauthorized"]);
});

test("a history failure is surfaced so the UI can retry", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({ detail: "History unavailable" }), { status: 503 }));
  await assert.rejects(fetchAllConversationHistory("id"), /History unavailable/);
});
