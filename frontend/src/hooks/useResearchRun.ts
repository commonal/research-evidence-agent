import { useCallback, useEffect, useReducer, useRef } from "react";

import { streamPost } from "../api/sse";
import { createInitialState, researchReducer } from "../state/research";
import type {
  LLMUsageSummary,
  ResearchResult,
  ResearchSelection,
  SSEMessage,
  WorkflowEvent,
} from "../types";

export function useResearchRun() {
  const [state, dispatch] = useReducer(researchReducer, undefined, createInitialState);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const consume = useCallback(async (url: string, payload: unknown) => {
    controller.current?.abort();
    controller.current = new AbortController();
    try {
      await streamPost(url, payload, handleMessage, controller.current.signal);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      dispatch({
        type: "failure",
        message: error instanceof Error ? error.message : String(error),
      });
    }

    function handleMessage(message: SSEMessage) {
      if (message.event === "progress") {
        dispatch({ type: "progress", event: message.data as WorkflowEvent });
      } else if (message.event === "usage") {
        dispatch({ type: "usage", usage: message.data as LLMUsageSummary });
      } else if (message.event === "result") {
        dispatch({ type: "result", result: message.data as ResearchResult });
      } else if (message.event === "error") {
        const data = message.data as { message?: string };
        throw new Error(data.message || "工作流执行失败");
      }
    }
  }, []);

  const start = useCallback(
    async (question: string) => {
      dispatch({ type: "start", question, initialNode: "analyze_question" });
      await consume("/api/v1/research/stream", { question });
    },
    [consume],
  );

  const select = useCallback(
    async (selection: ResearchSelection) => {
      const threadId = state.result?.thread_id;
      if (!threadId) return;
      dispatch({ type: "resume", initialNode: "wait_for_user_selection" });
      await consume(
        `/api/v1/research/${encodeURIComponent(threadId)}/selection/stream`,
        selection,
      );
    },
    [consume, state.result],
  );

  return { state, start, select };
}
