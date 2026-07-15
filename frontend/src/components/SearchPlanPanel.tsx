import type { SearchPlan } from "../types";

export function SearchPlanPanel({ plan }: { plan: SearchPlan }) {
  return (
    <section className="panel result-panel">
      <div className="panel-heading">
        <div><span className="section-index">03</span><h2>学术检索策略</h2></div>
        <span className="micro-label">{plan.queries.length} 条检索式</span>
      </div>
      <div className="keyword-list">
        {plan.keywords.map((keyword) => <span key={keyword}>{keyword}</span>)}
      </div>
      <div className="query-list">
        {plan.queries.map((query) => <div className="query-item" key={query}><code>{query}</code></div>)}
      </div>
    </section>
  );
}
