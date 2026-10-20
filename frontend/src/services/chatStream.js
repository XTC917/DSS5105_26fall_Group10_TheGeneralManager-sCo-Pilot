// SSE frames and UTF-8 characters may span arbitrary transport chunks.
export async function readChatStream(body, onProgress = () => {}) {
  if (!body) throw new Error("Chat stream is unavailable. Refresh the page before retrying.");
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result;
  function frame(text) {
    let event = "message";
    const data = [];
    for (const line of text.split(/\r?\n/)) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
    }
    if (!data.length) return;
    const value = JSON.parse(data.join("\n"));
    if (event === "progress") onProgress(value.message);
    if (event === "error") throw new Error(value.message || "Chat failed.");
    if (event === "done") result = value;
  }
  try {
    while (result === undefined) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let match;
      while ((match = /\r?\n\r?\n/.exec(buffer))) {
        frame(buffer.slice(0, match.index));
        buffer = buffer.slice(match.index + match[0].length);
      }
      if (done) break;
    }
    if (result === undefined) throw new Error("Connection interrupted before the final answer arrived. Refresh the page before retrying; do not automatically repeat an action.");
    return result;
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
