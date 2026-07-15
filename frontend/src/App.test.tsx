import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import App from "./App";
import { PaperList } from "./components/PaperList";
import type { Paper } from "./types";

describe("App", () => {
  it("渲染科研工作台的主要功能区域", () => {
    const html = renderToStaticMarkup(<App />);

    expect(html).toContain("提出研究问题");
    expect(html).toContain('id="workflow-timeline"');
    expect(html).toContain("模型用量");
    expect(html).toContain("API 文档");
  });

  it("在论文卡片中展示匹配分和命中关键词", () => {
    const paper: Paper = {
      arxiv_id: "2401.00001",
      title: "RAG for Question Answering",
      authors: ["Researcher"],
      abstract: "RAG improves grounded answers.",
      published_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
      categories: ["cs.CL"],
      abs_url: "https://arxiv.org/abs/2401.00001",
      pdf_url: "https://arxiv.org/pdf/2401.00001",
      matched_queries: ['all:"RAG"'],
      rank: 1,
      relevance_score: 93,
      matched_keywords: ["RAG"],
    };

    const html = renderToStaticMarkup(<PaperList papers={[paper]} />);

    expect(html).toContain("匹配分 93");
    expect(html).toContain("命中：RAG");
  });
});
