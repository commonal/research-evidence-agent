import { workflowNodes, type ResearchViewState } from "../state/research";
import type { WorkflowNode } from "../types";

const steps: Record<WorkflowNode, { title: string; description: string; conditional?: boolean }> = {
  analyze_question: { title: "分析问题", description: "判断研究范围是否足够明确" },
  generate_subquestions: { title: "拆解子问题", description: "宽泛问题生成候选研究方向", conditional: true },
  wait_for_user_selection: { title: "用户确认", description: "选择或修改最终研究问题", conditional: true },
  finalize_question: { title: "确认研究问题", description: "锁定本次检索的研究边界" },
  build_search_queries: { title: "生成检索式", description: "调用 LLM 生成英文 arXiv 查询" },
  search_academic_papers: { title: "检索论文", description: "查询 arXiv、合并结果并去重" },
  select_papers: { title: "相关性评分", description: "按标题、摘要和检索命中计算匹配分" },
};

const stateLabels = {
  pending: "待执行",
  running: "进行中",
  completed: "已完成",
  waiting: "等待输入",
  skipped: "已跳过",
  error: "执行失败",
};

const phaseLabels = {
  idle: "等待开始",
  running: "流程运行中",
  waiting: "等待问题选择",
  complete: "流程已完成",
  error: "执行失败",
};

export function WorkflowTimeline({ state }: { state: ResearchViewState }) {
  return (
    <section className={`panel workflow-panel ${state.phase === "running" ? "is-running" : ""}`}>
      <div className="panel-heading">
        <div><span className="section-index">02</span><h2>工作流进度</h2></div>
        <span className={`status-badge ${state.phase}`}>{phaseLabels[state.phase]}</span>
      </div>
      <div className="current-activity">
        <span className="activity-signal" aria-hidden="true"><i /><i /><i /></span>
        <div><small>当前活动</small><strong>{state.activity}</strong></div>
      </div>
      <ol className="timeline" id="workflow-timeline">
        {workflowNodes.map((node, index) => {
          const nodeState = state.nodeStates[node];
          return (
            <li key={node} data-node={node} className={nodeState === "pending" ? "" : nodeState}>
              <span className="step-marker">{index + 1}</span>
              <div><strong>{steps[node].title}</strong><p>{steps[node].description}</p></div>
              <span className="step-state">
                {nodeState === "pending" && steps[node].conditional ? "条件节点" : stateLabels[nodeState]}
              </span>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
