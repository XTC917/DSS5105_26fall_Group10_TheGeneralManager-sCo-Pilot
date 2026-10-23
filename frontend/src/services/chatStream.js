export async function readChatStream(response, handlers = {}) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail || response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (!response.body) {
    throw new Error("Chat stream is not available.");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let donePayload = null;
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() || "";
    for (const block of blocks) {
      const parsed = parseSseBlock(block);
      if (!parsed) continue;
      if (parsed.event === "progress") handlers.onProgress?.(parsed.data.message || "");
      if (parsed.event === "token") handlers.onToken?.(parsed.data);
      if (parsed.event === "error") {
        throw new Error(parsed.data.message || "Chat failed. Please try again.");
      }
      if (parsed.event === "done") donePayload = parsed.data;
    }
    if (done) break;
  }
  if (!donePayload) {
    throw new Error(
      "The answer stream ended before it finished. Refresh the page and check this conversation before sending the question again.",
    );
  }
  return donePayload;
}

function parseSseBlock(block) {
  let event = "message";
  const dataLines = [];
  for (const line of block.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (!dataLines.length) return null;
  return { event, data: JSON.parse(dataLines.join("\n")) };
}
