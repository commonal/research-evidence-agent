import type { ResearchResult } from "../types";

const statusLabels = {
  analyzing: "分析中",
  awaiting_selection: "等待选择",
  ready: "问题已确认",
  searching: "检索中",
  papers_ready: "论文已就绪",
  no_results: "暂无结果",
};

const phaseLabels: Record<string, string> = {
  idle: "未开始",
  running: "运行中",
  waiting: "等待选择",
  complete: "已完成",
  error: "执行失败",
};

export function RunDetails({ result, question, phase }: {
  result: ResearchResult | null;
  question: string;
  phase: string;
}) {
  return (
    <section className="panel run-panel">
      <div className="panel-heading compact">
        <div><span className="section-index">RUN</span><h2>本次运行</h2></div>
      </div>
      <dl className="run-details">
        <div><dt>状态</dt><dd>{phase === "error" ? phaseLabel(phase) : result ? statusLabels[result.status] : phaseLabel(phase)}</dd></div>
        <div><dt>线程</dt><dd>{result ? shortId(result.thread_id) : "—"}</dd></div>
        <div><dt>最终问题</dt><dd>{result?.selected_question || result?.original_question || question || "—"}</dd></div>
        <div><dt>数据源</dt><dd>arXiv</dd></div>
      </dl>
    </section>
  );
}

function shortId(value: string) {
  return value ? `${value.slice(0, 8)}…` : "—";
}

function phaseLabel(phase: string) {
  return phaseLabels[phase] || phase;
}
