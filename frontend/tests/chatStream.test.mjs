import assert from "node:assert/strict";
import test from "node:test";

import { readChatStream } from "../src/services/chatStream.js";

function responseFrom(chunks) {
  const encoder = new TextEncoder();
  return {
    ok: true,
    body: {
      getReader() {
        let index = 0;
        return {
          async read() {
            if (index >= chunks.length) return { value: undefined, done: true };
            const value = encoder.encode(chunks[index]);
            index += 1;
            return { value, done: false };
          },
        };
      },
    },
  };
}

test("progress and answer tokens arrive before the finished response", async () => {
  const progress = [];
  const tokens = [];
  const payload = await readChatStream(
    responseFrom([
      'event: progress\ndata: {"message":"Checking the question…"}\n\n',
      'event: token\ndata: {"text":"ORD"}\n\nevent: token\ndata: {"text":"-120"}\n\n',
      'event: done\ndata: {"answer":"ORD-120 is overdue.","why":{"steps":[]}}\n\n',
    ]),
    {
      onProgress: (message) => progress.push(message),
      onToken: (token) => tokens.push(token),
    },
  );
  assert.deepEqual(progress, ["Checking the question…"]);
  assert.deepEqual(tokens, [{ text: "ORD" }, { text: "-120" }]);
  assert.equal(payload.answer, "ORD-120 is overdue.");
});

test("a stream that ends before done does not look like a finished answer", async () => {
  await assert.rejects(
    () => readChatStream(responseFrom(['event: token\ndata: {"text":"partial"}\n\n'])),
    /before it finished/,
  );
});
