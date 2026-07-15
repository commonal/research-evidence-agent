import { describe, expect, it } from "vitest";

import { createInitialState, researchReducer } from "./research";
import type { ResearchResult } from "../types";

function makeResult(overrides: Partial<ResearchResult> = {}): ResearchResult {
  return {
    request_id: "request-1",
    thread_id: "thread-1",
    status: "papers_ready",
    original_question: "长上下文模型能否替代 RAG？",
    selected_question: "长上下文模型能否在多跳问答中替代 RAG？",
    subquestions: [],
    search_plan: { queries: ["all:RAG"], keywords: ["RAG"] },
    usage: {
      prompt_tokens: 10,
      completion_tokens: 5,
      total_tokens: 15,
      prompt_cache_hit_tokens: 4,
      prompt_cache_miss_tokens: 6,
      reasoning_tokens: 2,
      calls: [],
    },
    papers: [],
    search_errors: [],
    trace: [
      { node: "analyze_question", message: "已分析", details: {} },
      { node: "finalize_question", message: "已确认", details: {} },
      { node: "build_search_queries", message: "已规划", details: {} },
      { node: "search_academic_papers", message: "已检索", details: {} },
    ],
    ...overrides,
  };
}

describe("researchReducer", () => {
  it("在明确问题完成后标记条件节点为已跳过", () => {
    const started = researchReducer(createInitialState(), {
      type: "start",
      question: "长上下文模型能否替代 RAG？",
      initialNode: "analyze_question",
    });
    const completed = researchReducer(started, {
      type: "result",
      result: makeResult(),
    });

    expect(completed.phase).toBe("complete");
    expect(completed.nodeStates.generate_subquestions).toBe("skipped");
    expect(completed.nodeStates.wait_for_user_selection).toBe("skipped");
    expect(completed.nodeStates.search_academic_papers).toBe("completed");
    expect(completed.usage.total_tokens).toBe(15);
  });

  it("在宽泛问题中保留线程并进入等待选择状态", () => {
    const waiting = researchReducer(createInitialState(), {
      type: "result",
      result: makeResult({
        status: "awaiting_selection",
        selected_question: null,
        search_plan: null,
        trace: [
          { node: "analyze_question", message: "范围较宽", details: {} },
          { node: "generate_subquestions", message: "已拆解", details: {} },
        ],
      }),
    });

    expect(waiting.phase).toBe("waiting");
    expect(waiting.nodeStates.wait_for_user_selection).toBe("waiting");
    expect(waiting.result?.thread_id).toBe("thread-1");
  });
});
