import assert from "node:assert/strict";
import { test } from "node:test";
import { readChatStream } from "../src/services/chatStream.js";
import { assistantMessage } from "../src/services/chatMessages.js";

function stream(text) {
  const bytes = new TextEncoder().encode(text);
  return new ReadableStream({ start(controller) {
    for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
    controller.close();
  } });
}
test("progress and final response survive arbitrary UTF-8 and SSE chunk boundaries", async () => {
  const progress = [];
  const result = await readChatStream(stream(': keep-alive\r\n\r\nevent: progress\r\ndata: {"message":"查询中"}\r\n\r\nevent: done\ndata: {"answer":"完成","why":{"steps":[]}}\n\n'), (text) => progress.push(text));
  assert.deepEqual(progress, ["查询中"]);
  assert.equal(result.answer, "完成");
  assert.deepEqual(result.why, { steps: [] });
});
test("disconnects and server errors never silently retry tools", async () => {
  await assert.rejects(readChatStream(stream('event: progress\ndata: {"message":"Working"}\n\n')), /Refresh the page/);
  await assert.rejects(readChatStream(stream('event: error\ndata: {"message":"Request failed"}\n\n')), /Request failed/);
});
test("new response metadata maps Why and optional summaries without any history API", () => {
  const why = { version: 1, steps: [{ title: "Question", items: ["Why?"] }] };
  const message = assistantMessage("A", { why, reasoning_summary: ["Summary"], proposed_actions: [{ type: "create_watch" }] });
  assert.deepEqual(message.why, why);
  assert.deepEqual(message.reasoningSummary, ["Summary"]);
  assert.equal(message.proposedActions[0].type, "create_watch");
  assert.equal(assistantMessage("Old payload").why, null);
});
