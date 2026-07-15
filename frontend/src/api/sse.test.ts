import { describe, expect, it } from "vitest";

import { SSEDecoder } from "./sse";

describe("SSEDecoder", () => {
  it("可以解析跨数据块的 UTF-8 SSE 帧", () => {
    const decoder = new SSEDecoder();

    expect(decoder.push('event: progress\ndata: {"node":"analyze_')).toEqual([]);
    expect(decoder.push('question","message":"分析问题"}\n\n')).toEqual([
      {
        event: "progress",
        data: { node: "analyze_question", message: "分析问题" },
      },
    ]);
  });

  it("支持多行 data 和没有末尾空行的最后一帧", () => {
    const decoder = new SSEDecoder();
    decoder.push('event: result\ndata: {"status":\n');
    decoder.push('data: "papers_ready"}');

    expect(decoder.finish()).toEqual([
      { event: "result", data: { status: "papers_ready" } },
    ]);
  });
});
