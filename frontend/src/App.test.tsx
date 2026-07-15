import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App", () => {
  it("渲染科研工作台的主要功能区域", () => {
    const html = renderToStaticMarkup(<App />);

    expect(html).toContain("提出研究问题");
    expect(html).toContain('id="workflow-timeline"');
    expect(html).toContain("模型用量");
    expect(html).toContain("API 文档");
  });
});
