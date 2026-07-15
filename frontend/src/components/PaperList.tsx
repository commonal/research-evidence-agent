import type { Paper } from "../types";

export function PaperList({ papers }: { papers: Paper[] }) {
  return (
    <section className="panel papers-panel">
      <div className="panel-heading">
        <div><span className="section-index">04</span><h2>候选论文</h2></div>
        <span className="micro-label">{papers.length} 篇</span>
      </div>
      <p className="section-copy">当前为摘要级候选集，尚未经过全文证据提取与语义重排。</p>
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
        <span className="paper-rank">#{String(index + 1).padStart(2, "0")}</span>
        <span className="paper-meta">arXiv:{paper.arxiv_id} · {formatDate(paper.published_at)}</span>
      </div>
      <h3><a href={safeUrl(paper.abs_url)} target="_blank" rel="noreferrer">{paper.title}</a></h3>
      <div className="paper-meta">{authors}{authorSuffix}</div>
      <div className="paper-categories">
        {paper.categories.map((category) => <span className="paper-category" key={category}>{category}</span>)}
      </div>
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
