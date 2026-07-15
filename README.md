# Research Evidence Agent

这是一个面向 AI/计算机方向研究生和科研人员的科研证据检索 Agent。项目从 GPT Researcher 的搜索流程原型起步，现已拆分为独立的 LangGraph + FastAPI 应用。

当前提交保留可离线运行的通用搜索基线：

```text
分析问题 -> 规划子查询 -> 并行搜索 -> 评估证据
                         ^          |
                         | 证据不足 |
                         +-- 改写查询
                                    |
                              生成带引用回答
                                    |
                                校验引用
```

项目使用 LangGraph 表达条件分支、补充搜索循环和 `MemorySaver` 线程状态，使用 FastAPI 提供普通 JSON 与 SSE 流式接口。科研工作台已迁移为 React + TypeScript + Vite，生产构建由 FastAPI 直接托管，因此日常运行仍只需启动一个 Uvicorn 服务。默认 provider 不需要 API Key，可以验证图、接口和状态流转。项目不再导入或动态加载父项目代码。

科研 MVP 已实现“问题收敛 → 学术检索式生成 → arXiv 论文发现”这一段主链路。宽泛问题会通过 LangGraph `interrupt/resume` 等待用户选择；具体问题会生成英文检索式，查询 arXiv，并对论文元数据去重。PDF 全文证据提取与可追溯结论仍属于下一阶段。详细范围见 [PROJECT_GUIDE.md](PROJECT_GUIDE.md)。

## 快速开始

在本目录执行：

```powershell
uv sync --dev
uv run pytest
uv run uvicorn research_evidence_agent.api:app --app-dir src --reload --port 8010 --env-file .env
```

打开 `http://127.0.0.1:8010/` 使用科研工作台；接口文档位于 `http://127.0.0.1:8010/docs`。也可以直接调用：

```powershell
$body = @{
  query = "LangGraph 如何帮助构建可恢复的深度搜索 Agent？"
  mode = "deep"
  max_iterations = 2
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8010/api/v1/search `
  -ContentType "application/json" `
  -Body $body
```

流式接口为 `POST /api/v1/search/stream`，依次发送 `progress` 和 `result` SSE 事件。

### 前端开发

仓库提交了 Vite 生产构建，直接启动 FastAPI 即可使用。如果需要修改前端，在第二个终端执行：

```powershell
cd frontend
npm install
npm run dev
```

Vite 开发地址为 `http://127.0.0.1:5173/`，会把 `/api`、`/health`、`/docs` 和 `/openapi.json` 代理到 `8010` 端口。修改完成后运行：

```powershell
npm test
npm run build
```

`npm run build` 会执行 TypeScript 检查，并将生产资源重新生成到 `src/research_evidence_agent/web/`，供 FastAPI 单端口托管。

## API

- `GET /health`：服务与 provider 状态。
- `POST /api/v1/search`：执行完整图并返回回答、引用、证据质量和节点轨迹。
- `POST /api/v1/search/stream`：以 SSE 推送节点进度和最终结果。
- `POST /api/v1/research/plan`：分析研究问题；宽泛问题返回候选子问题并暂停线程。
- `POST /api/v1/research/stream`：以 SSE 推送科研节点的运行、完成、等待以及最终结果。
- `POST /api/v1/research/{thread_id}/selection`：选择或修改具体子问题，恢复线程并执行学术检索。
- `POST /api/v1/research/{thread_id}/selection/stream`：以 SSE 恢复宽泛问题对应的研究线程。

检索完成后状态为 `papers_ready`，响应包含 `search_plan`、去重后的 `papers`、可诊断的 `search_errors`，以及模型调用的 `usage` 汇总与明细。DeepSeek usage 包括输入、输出、总 token、Prompt 缓存命中/未命中和推理 token。默认使用离线 Demo Provider；启用真实 arXiv 检索时可设置以下环境变量：

```dotenv
RESEARCH_PAPER_PROVIDER=arxiv
ACADEMIC_QUERY_PLANNER=demo
RESEARCH_MAX_RESULTS_PER_QUERY=5
```

`ACADEMIC_QUERY_PLANNER=openai_compatible` 可使用兼容 OpenAI Chat Completions 的模型生成更好的英文检索式，此时还需配置 `LLM_API_KEY`、`LLM_BASE_URL` 和 `LLM_MODEL`。当前返回的是论文元数据与摘要，不能称为全文证据结论。

也可单独运行真实数据源冒烟验证：

```powershell
uv run python scripts/smoke_arxiv.py
```

请求中的 `max_iterations` 表示最多搜索轮数，而不是额外重试次数。证据不足且仍有搜索预算时，图会进入 `rewrite_query`，然后重新搜索；达到上限后会基于已有证据回答并明确证据限制。

## 项目结构

```text
frontend/                       # React + TypeScript + Vite 源码与测试
├── src/components/             # 输入、时间线、选择、Usage、检索式和论文组件
├── src/hooks/                  # SSE 研究流程 Hook
└── src/state/                  # useReducer 工作台状态

src/research_evidence_agent/
├── api.py                  # FastAPI 应用与 SSE 接口
├── config.py               # 环境配置
├── models.py               # API 模型
├── service.py              # Graph 调用与流式事件转换
├── web/                    # Vite 生产构建，由 FastAPI 托管
├── graph/
│   ├── builder.py          # LangGraph 节点和边
│   ├── nodes.py            # 搜索 Agent 节点实现
│   └── state.py            # 结构化 Graph State
├── providers/
│   ├── base.py             # 可注入协议
│   ├── demo.py             # 离线通用检索和回答
│   └── arxiv.py            # arXiv Atom API Provider
└── research/
    ├── academic.py         # 学术检索式规划与离线论文 Provider
    ├── builder.py          # 科研 LangGraph 工作流
    ├── nodes.py            # 问题收敛和论文发现节点
    └── state.py            # 科研工作流状态
```

## 独立性与来源

仓库运行时不依赖 GPT Researcher。项目的初始搜索闭环来源及许可证说明见 [NOTICE.md](NOTICE.md) 和 [LICENSE](LICENSE)。父项目模块只会在出现明确需求时逐个评估，并优先以小型独立接口重新实现。
