import type { SSEMessage } from "../types";

export class SSEDecoder {
  private buffer = "";

  push(chunk: string): SSEMessage[] {
    this.buffer += chunk;
    this.buffer = this.buffer.replace(/\r\n/g, "\n");
    const messages: SSEMessage[] = [];
    let boundary = this.buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const frame = this.buffer.slice(0, boundary);
      this.buffer = this.buffer.slice(boundary + 2);
      const message = parseFrame(frame);
      if (message) messages.push(message);
      boundary = this.buffer.indexOf("\n\n");
    }
    return messages;
  }

  finish(): SSEMessage[] {
    const frame = this.buffer.trim();
    this.buffer = "";
    const message = parseFrame(frame);
    return message ? [message] : [];
  }
}

function parseFrame(frame: string): SSEMessage | null {
  if (!frame.trim()) return null;
  let event = "message";
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (!dataLines.length) return null;
  return { event, data: JSON.parse(dataLines.join("\n")) };
}

export async function streamPost(
  url: string,
  payload: unknown,
  onMessage: (message: SSEMessage) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok || !response.body) {
    const body = await response.text();
    throw new Error(body || `请求失败（HTTP ${response.status}）`);
  }

  const reader = response.body.getReader();
  const textDecoder = new TextDecoder("utf-8");
  const sseDecoder = new SSEDecoder();
  while (true) {
    const { value, done } = await reader.read();
    const chunk = textDecoder.decode(value || new Uint8Array(), { stream: !done });
    sseDecoder.push(chunk).forEach(onMessage);
    if (done) break;
  }
  sseDecoder.finish().forEach(onMessage);
}
