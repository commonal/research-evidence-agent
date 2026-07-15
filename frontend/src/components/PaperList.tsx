import type { Paper } from "../types";

export function PaperList({ papers }: { papers: Paper[] }) {
  return (
    <section className="panel papers-panel">
      <div className="panel-heading">
        <div><span className="section-index">04</span><h2>候选论文</h2></div>
        <span className="micro-label">{papers.length} 篇</span>
      </div>
      <p className="section-copy">匹配分基于标题、摘要关键词和多检索式命中，仅用于本次候选集排序。</p>
      <div className="paper-list">
        {papers.length ? papers.map((paper, index) => (
          <PaperCard key={paper.arxiv_id} paper={paper} index={index} />
        )) : <p className="section-copy">没有找到匹配的候选论文。</p>}
      </div>
    </section>
  );
}

function PaperCard({ paper, index }: { paper: Paper; index: number }) {
  const authors = paper.authors.slice(0, 4).join(" · ");
  const authorSuffix = paper.authors.length > 4 ? " 等" : "";
  return (
    <article className="paper-card">
      <div className="paper-topline">
        <div className="paper-scoreline">
          <span className="paper-rank">#{String(index + 1).padStart(2, "0")}</span>
          <span className="relevance-score">匹配分 {paper.relevance_score}</span>
        </div>
        <span className="paper-meta">arXiv:{paper.arxiv_id} · {formatDate(paper.published_at)}</span>
      </div>
      <h3><a href={safeUrl(paper.abs_url)} target="_blank" rel="noreferrer">{paper.title}</a></h3>
      <div className="paper-meta">{authors}{authorSuffix}</div>
      <div className="paper-categories">
        {paper.categories.map((category) => <span className="paper-category" key={category}>{category}</span>)}
      </div>
      {paper.matched_keywords.length > 0 && (
        <p className="matched-keywords">命中：{paper.matched_keywords.join(" · ")}</p>
      )}
      <details><summary>查看摘要</summary><p>{paper.abstract}</p></details>
    </article>
  );
}

function safeUrl(value: string) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "#";
  } catch {
    return "#";
  }
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "日期未知" : date.toLocaleDateString("zh-CN");
}
