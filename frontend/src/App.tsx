import { useEffect, useState } from "react";

import { PaperList } from "./components/PaperList";
import { QuestionSelection } from "./components/QuestionSelection";
import { ResearchInput } from "./components/ResearchInput";
import { RunDetails } from "./components/RunDetails";
import { SearchPlanPanel } from "./components/SearchPlanPanel";
import { UsagePanel } from "./components/UsagePanel";
import { WorkflowTimeline } from "./components/WorkflowTimeline";
import { useResearchRun } from "./hooks/useResearchRun";

type ServiceStatus = "checking" | "online" | "offline";

const serviceLabels: Record<ServiceStatus, string> = {
  checking: "连接服务中",
  online: "服务在线",
  offline: "服务离线",
};

export default function App() {
  const { state, start, select } = useResearchRun();
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus>("checking");

  useEffect(() => {
    const controller = new AbortController();
    fetch("/health", { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        setServiceStatus("online");
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          setServiceStatus("offline");
        }
      });
    return () => controller.abort();
  }, []);

  const result = state.result;
  const running = state.phase === "running";
  const awaitingSelection = result?.status === "awaiting_selection";

  return (
    <div className="page-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Research Evidence Agent 首页">
          <span className="brand-mark" aria-hidden="true">R</span>
          <span><strong>Research Evidence</strong><small>Agent Workspace</small></span>
        </a>
        <div className="topbar-actions">
          <span className="environment-pill">REACT MVP</span>
          <span className={`service-state ${serviceStatus}`} aria-live="polite">
            <i aria-hidden="true" /><span>{serviceLabels[serviceStatus]}</span>
          </span>
          <a className="docs-link" href="/docs" target="_blank" rel="noreferrer">API 文档</a>
        </div>
      </header>

      <main>
        <section className="hero">
          <div>
            <p className="eyebrow">AI / 计算机科研证据工作台</p>
            <h1>把研究问题，变成一条<br /><em>可观察的证据路径。</em></h1>
          </div>
          <p className="hero-copy">
            收敛研究问题、生成学术检索式并发现 arXiv 论文。每个节点、模型调用和
            token 消耗都在同一条时间线中呈现。
          </p>
        </section>

        <div className="workspace-grid">
          <div className="primary-column">
            <ResearchInput disabled={running} onSubmit={start} />
            <WorkflowTimeline state={state} />

            {awaitingSelection && result && (
              <QuestionSelection
                options={result.subquestions}
                disabled={running}
                onSelect={select}
              />
            )}

            {!awaitingSelection && result?.search_plan && (
              <SearchPlanPanel plan={result.search_plan} />
            )}

            {!awaitingSelection && result && (
              <PaperList papers={result.papers} />
            )}

            {state.error && (
              <section className="error-panel" role="alert">
                <strong>{state.phase === "error" ? "流程执行失败" : "部分检索请求未完成"}</strong>
                <p>{state.error}</p>
              </section>
            )}
          </div>

          <aside className="side-column">
            <UsagePanel usage={state.usage} phase={state.phase} />
            <RunDetails result={result} question={state.question} phase={state.phase} />
            <section className="scope-card">
              <span>当前产品边界</span>
              <strong>Paper discovery, not conclusion.</strong>
              <p>下一阶段将接入论文筛选、PDF 全文解析、证据定位和结论生成。</p>
            </section>
          </aside>
        </div>
      </main>

      <footer>
        <span>Research Evidence Agent · Local MVP</span>
        <span>React × LangGraph × FastAPI × arXiv</span>
      </footer>
    </div>
  );
}
