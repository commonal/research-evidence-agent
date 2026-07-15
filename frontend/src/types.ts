export type ResearchStatus =
  | "analyzing"
  | "awaiting_selection"
  | "ready"
  | "searching"
  | "papers_ready"
  | "no_results";

export type WorkflowNode =
  | "analyze_question"
  | "generate_subquestions"
  | "wait_for_user_selection"
  | "finalize_question"
  | "build_search_queries"
  | "search_academic_papers";

export type NodeState = "pending" | "running" | "completed" | "waiting" | "skipped" | "error";

export interface WorkflowEvent {
  node: WorkflowNode;
  state: NodeState;
  message: string;
  details: Record<string, unknown>;
}

export interface SubQuestion {
  id: string;
  question: string;
  scope: string;
}

export interface SearchPlan {
  queries: string[];
  keywords: string[];
}

export interface Paper {
  arxiv_id: string;
  title: string;
  authors: string[];
  abstract: string;
  published_at: string;
  updated_at: string;
  categories: string[];
  abs_url: string;
  pdf_url: string;
  matched_queries: string[];
  rank: number;
}

export interface LLMUsageCall {
  operation: string;
  provider: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  prompt_cache_hit_tokens: number;
  prompt_cache_miss_tokens: number;
  reasoning_tokens: number;
}

export interface LLMUsageSummary {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  prompt_cache_hit_tokens: number;
  prompt_cache_miss_tokens: number;
  reasoning_tokens: number;
  calls: LLMUsageCall[];
}

export interface ResearchResult {
  request_id: string;
  thread_id: string;
  status: ResearchStatus;
  original_question: string;
  selected_question: string | null;
  subquestions: SubQuestion[];
  search_plan: SearchPlan | null;
  usage: LLMUsageSummary;
  papers: Paper[];
  search_errors: string[];
  trace: Array<Omit<WorkflowEvent, "state">>;
}

export type ResearchSelection = { option_id: string } | { question: string };

export interface SSEMessage<T = unknown> {
  event: "progress" | "usage" | "result" | "error" | string;
  data: T;
}
