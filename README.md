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

项目使用 LangGraph 表达条件分支、补充搜索循环和 `MemorySaver` 线程状态，使用 FastAPI 提供普通 JSON 与 SSE 流式接口。默认 provider 不需要 API Key，可以验证图、接口和状态流转。项目不再导入或动态加载父项目代码。

科研 MVP 将在此基线上实现：宽泛问题拆解、用户选择具体子问题、Arxiv 检索、论文全文证据提取以及可追溯结论生成。详细范围见 [PROJECT_GUIDE.md](PROJECT_GUIDE.md)。

## 快速开始

在本目录执行：

```powershell
uv sync --dev
uv run pytest
uv run uvicorn agentic_search_demo.api:app --app-dir src --reload --port 8010
```

打开 `http://127.0.0.1:8010/docs`，或调用：

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

## API

- `GET /health`：服务与 provider 状态。
- `POST /api/v1/search`：执行完整图并返回回答、引用、证据质量和节点轨迹。
- `POST /api/v1/search/stream`：以 SSE 推送节点进度和最终结果。

请求中的 `max_iterations` 表示最多搜索轮数，而不是额外重试次数。证据不足且仍有搜索预算时，图会进入 `rewrite_query`，然后重新搜索；达到上限后会基于已有证据回答并明确证据限制。

## 项目结构

```text
src/agentic_search_demo/
├── api.py                  # FastAPI 应用与 SSE 接口
├── config.py               # 环境配置
├── models.py               # API 模型
├── service.py              # Graph 调用与流式事件转换
├── graph/
│   ├── builder.py          # LangGraph 节点和边
│   ├── nodes.py            # 搜索 Agent 节点实现
│   └── state.py            # 结构化 Graph State
└── providers/
    ├── base.py             # 可注入协议
    └── demo.py             # 离线检索和回答
```

## 独立性与来源

仓库运行时不依赖 GPT Researcher。项目的初始搜索闭环来源及许可证说明见 [NOTICE.md](NOTICE.md) 和 [LICENSE](LICENSE)。父项目模块只会在出现明确需求时逐个评估，并优先以小型独立接口重新实现。
