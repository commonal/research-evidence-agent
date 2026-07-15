import type {
  LLMUsageSummary,
  NodeState,
  ResearchResult,
  WorkflowEvent,
  WorkflowNode,
} from "../types";

export const workflowNodes: WorkflowNode[] = [
  "analyze_question",
  "generate_subquestions",
  "wait_for_user_selection",
  "finalize_question",
  "build_search_queries",
  "search_academic_papers",
  "select_papers",
];

export const emptyUsage: LLMUsageSummary = {
  prompt_tokens: 0,
  completion_tokens: 0,
  total_tokens: 0,
  prompt_cache_hit_tokens: 0,
  prompt_cache_miss_tokens: 0,
  reasoning_tokens: 0,
  calls: [],
};

export interface ResearchViewState {
  phase: "idle" | "running" | "waiting" | "complete" | "error";
  activity: string;
  question: string;
  nodeStates: Record<WorkflowNode, NodeState>;
  result: ResearchResult | null;
  usage: LLMUsageSummary;
  error: string | null;
}

export type ResearchAction =
  | { type: "start"; question: string; initialNode: WorkflowNode }
  | { type: "resume"; initialNode: WorkflowNode }
  | { type: "progress"; event: WorkflowEvent }
  | { type: "usage"; usage: LLMUsageSummary }
  | { type: "result"; result: ResearchResult }
  | { type: "failure"; message: string };

export function createInitialState(): ResearchViewState {
  return {
    phase: "idle",
    activity: "输入问题后，工作流将在这里实时更新",
    question: "",
    nodeStates: Object.fromEntries(
      workflowNodes.map((node) => [node, "pending"]),
    ) as Record<WorkflowNode, NodeState>,
    result: null,
    usage: emptyUsage,
    error: null,
  };
}

export function researchReducer(
  state: ResearchViewState,
  action: ResearchAction,
): ResearchViewState {
  if (action.type === "start") {
    const fresh = createInitialState();
    return {
      ...fresh,
      phase: "running",
      question: action.question,
      activity: "正在启动研究工作流",
      nodeStates: { ...fresh.nodeStates, [action.initialNode]: "running" },
    };
  }
  if (action.type === "resume") {
    return {
      ...state,
      phase: "running",
      activity: "正在恢复研究工作流",
      error: null,
      nodeStates: { ...state.nodeStates, [action.initialNode]: "running" },
    };
  }
  if (action.type === "progress") {
    const nodeStates = { ...state.nodeStates };
    if (action.event.state === "running") {
      for (const node of workflowNodes) {
        if (nodeStates[node] === "running") nodeStates[node] = "pending";
      }
    }
    nodeStates[action.event.node] = action.event.state;
    return {
      ...state,
      phase: action.event.state === "waiting" ? "waiting" : state.phase,
      activity: action.event.message,
      nodeStates,
    };
  }
  if (action.type === "usage") return { ...state, usage: action.usage };
  if (action.type === "result") {
    const nodeStates = { ...state.nodeStates };
    action.result.trace.forEach((event) => {
      nodeStates[event.node] = "completed";
    });
    const executed = new Set(action.result.trace.map((event) => event.node));
    if (action.result.status !== "awaiting_selection") {
      for (const node of ["generate_subquestions", "wait_for_user_selection"] as WorkflowNode[]) {
        if (!executed.has(node)) nodeStates[node] = "skipped";
      }
    } else {
      nodeStates.wait_for_user_selection = "waiting";
    }
    return {
      ...state,
      phase: action.result.status === "awaiting_selection" ? "waiting" : "complete",
      activity:
        action.result.status === "awaiting_selection"
          ? "请选择一个具体研究问题，工作流随后继续"
          : action.result.status === "papers_ready"
            ? `检索完成，共获得 ${action.result.papers.length} 篇去重候选论文`
            : "检索流程已结束，但当前检索式没有返回论文",
      result: action.result,
      usage: action.result.usage || emptyUsage,
      nodeStates,
      error: action.result.search_errors.length
        ? `部分检索请求失败：${action.result.search_errors.join("；")}`
        : null,
    };
  }
  return {
    ...state,
    phase: "error",
    activity: "流程遇到错误，请查看错误信息或服务终端",
    error: action.message,
  };
}
