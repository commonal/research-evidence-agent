const elements = {
  form: document.querySelector("#research-form"),
  question: document.querySelector("#question-input"),
  runButton: document.querySelector("#run-button"),
  workflowPanel: document.querySelector("#workflow-panel"),
  runStatus: document.querySelector("#run-status"),
  activity: document.querySelector("#activity-message"),
  timeline: document.querySelector("#workflow-timeline"),
  selectionPanel: document.querySelector("#selection-panel"),
  selectionOptions: document.querySelector("#selection-options"),
  customQuestion: document.querySelector("#custom-question"),
  continueButton: document.querySelector("#continue-button"),
  queryPanel: document.querySelector("#query-panel"),
  queryCount: document.querySelector("#query-count"),
  keywordList: document.querySelector("#keyword-list"),
  queryList: document.querySelector("#query-list"),
  papersPanel: document.querySelector("#papers-panel"),
  paperCount: document.querySelector("#paper-count"),
  paperList: document.querySelector("#paper-list"),
  errorPanel: document.querySelector("#error-panel"),
  errorMessage: document.querySelector("#error-message"),
  serviceState: document.querySelector("#service-state"),
  promptTokens: document.querySelector("#prompt-tokens"),
  completionTokens: document.querySelector("#completion-tokens"),
  cacheHitTokens: document.querySelector("#cache-hit-tokens"),
  totalTokens: document.querySelector("#total-tokens"),
  cacheHitRate: document.querySelector("#cache-hit-rate"),
  cacheMeter: document.querySelector("#cache-meter-value"),
  modelChip: document.querySelector("#model-chip"),
  metricNote: document.querySelector("#metric-note"),
  detailStatus: document.querySelector("#detail-status"),
  detailThread: document.querySelector("#detail-thread"),
  detailQuestion: document.querySelector("#detail-question"),
};

const appState = {
  threadId: null,
  result: null,
  running: false,
};

const statusLabels = {
  analyzing: "分析中",
  awaiting_selection: "等待选择",
  ready: "问题已确认",
  searching: "检索中",
  papers_ready: "论文已就绪",
  no_results: "暂无结果",
};

document.querySelectorAll(".example-chip").forEach((button) => {
  button.addEventListener("click", () => {
    elements.question.value = button.dataset.question || "";
    elements.question.focus();
  });
});

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = elements.question.value.trim();
  if (question.length < 3 || appState.running) return;

  resetWorkspace();
  setRunning(true);
  try {
    await consumeSSE("/api/v1/research/stream", { question });
  } catch (error) {
    handleFailure(error);
  }
});

elements.question.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    elements.form.requestSubmit();
  }
});

elements.continueButton.addEventListener("click", async () => {
  if (!appState.threadId || appState.running) return;
  const customQuestion = elements.customQuestion.value.trim();
  const selected = document.querySelector('input[name="research-option"]:checked');
  const payload = customQuestion
    ? { question: customQuestion }
    : selected
      ? { option_id: selected.value }
      : null;

  if (!payload) {
    showError("请选择一个候选问题，或输入自定义研究问题。");
    return;
  }

  hideError();
  setRunning(true);
  elements.continueButton.disabled = true;
  try {
    await consumeSSE(
      `/api/v1/research/${encodeURIComponent(appState.threadId)}/selection/stream`,
      payload,
    );
  } catch (error) {
    handleFailure(error);
  }
});

async function checkHealth() {
  try {
    const response = await fetch("/health", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("health check failed");
    elements.serviceState.className = "service-state online";
    elements.serviceState.querySelector("span").textContent = "本地服务在线";
  } catch (_error) {
    elements.serviceState.className = "service-state offline";
    elements.serviceState.querySelector("span").textContent = "服务未连接";
  }
}

async function consumeSSE(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    const body = await response.text();
    throw new Error(body || `请求失败（HTTP ${response.status}）`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
    buffer = buffer.replace(/\r\n/g, "\n");

    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      processSSEFrame(frame);
      boundary = buffer.indexOf("\n\n");
    }
    if (done) break;
  }
}

function processSSEFrame(frame) {
  if (!frame.trim()) return;
  let eventName = "message";
  const dataLines = [];
  frame.split("\n").forEach((line) => {
    if (line.startsWith("event:")) eventName = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  });
  if (!dataLines.length) return;

  const data = JSON.parse(dataLines.join("\n"));
  if (eventName === "progress") updateProgress(data);
  if (eventName === "usage") renderUsage(data);
  if (eventName === "result") handleResult(data);
  if (eventName === "error") throw new Error(data.message || "工作流执行失败");
}

function updateProgress(event) {
  const item = elements.timeline.querySelector(`[data-node="${event.node}"]`);
  if (!item) return;

  if (event.state === "running") {
    elements.timeline.querySelectorAll("li.running").forEach((node) => {
      node.classList.remove("running");
    });
  }
  item.classList.remove("running", "completed", "waiting", "skipped");
  item.classList.add(event.state || "running");

  const stateText = item.querySelector(".step-state");
  stateText.textContent = {
    running: "进行中",
    completed: "已完成",
    waiting: "等待输入",
  }[event.state] || "已更新";
  elements.activity.textContent = event.message || "工作流状态已更新";
}

function handleResult(result) {
  appState.result = result;
  appState.threadId = result.thread_id;
  elements.detailStatus.textContent = statusLabels[result.status] || result.status;
  elements.detailThread.textContent = shortId(result.thread_id);
  elements.detailQuestion.textContent = result.selected_question || result.original_question;

  applyTrace(result.trace || []);
  renderUsage(result.usage || emptyUsage());

  if (result.status === "awaiting_selection") {
    renderSelection(result.subquestions || []);
    setRunStatus("waiting", "等待问题选择");
    elements.activity.textContent = "请选择一个具体研究问题，工作流随后继续";
    setRunning(false);
    return;
  }

  elements.selectionPanel.classList.add("is-hidden");
  renderSearchPlan(result.search_plan);
  renderPapers(result.papers || []);
  markConditionalSteps(result.trace || []);

  if (result.search_errors?.length) {
    showError(`部分检索请求失败：${result.search_errors.join("；")}`);
  }

  if (result.status === "papers_ready") {
    setRunStatus("complete", "流程已完成");
    elements.activity.textContent = `检索完成，共获得 ${result.papers.length} 篇去重候选论文`;
  } else if (result.status === "no_results") {
    setRunStatus("complete", "未找到论文");
    elements.activity.textContent = "检索流程已结束，但当前检索式没有返回论文";
  }
  setRunning(false);
}

function applyTrace(trace) {
  trace.forEach((event) => {
    const item = elements.timeline.querySelector(`[data-node="${event.node}"]`);
    if (!item) return;
    item.classList.remove("running", "waiting", "skipped");
    item.classList.add("completed");
    item.querySelector(".step-state").textContent = "已完成";
  });
}

function markConditionalSteps(trace) {
  const executed = new Set(trace.map((event) => event.node));
  ["generate_subquestions", "wait_for_user_selection"].forEach((node) => {
    if (executed.has(node)) return;
    const item = elements.timeline.querySelector(`[data-node="${node}"]`);
    item.classList.add("skipped");
    item.querySelector(".step-state").textContent = "已跳过";
  });
}

function renderSelection(subquestions) {
  elements.selectionOptions.innerHTML = subquestions
    .map(
      (option, index) => `
        <label class="selection-option">
          <input type="radio" name="research-option" value="${escapeHtml(option.id)}" ${index === 0 ? "checked" : ""} />
          <span>
            <strong>${escapeHtml(option.question)}</strong>
            <small>${escapeHtml(option.scope)}</small>
          </span>
        </label>`,
    )
    .join("");
  elements.customQuestion.value = "";
  elements.selectionPanel.classList.remove("is-hidden");
  elements.selectionPanel.scrollIntoView({ behavior: "smooth", block: "center" });
}

function renderSearchPlan(plan) {
  if (!plan?.queries?.length) {
    elements.queryPanel.classList.add("is-hidden");
    return;
  }
  elements.queryCount.textContent = `${plan.queries.length} 条检索式`;
  elements.keywordList.innerHTML = (plan.keywords || [])
    .map((keyword) => `<span>${escapeHtml(keyword)}</span>`)
    .join("");
  elements.queryList.innerHTML = plan.queries
    .map((query) => `<div class="query-item"><code>${escapeHtml(query)}</code></div>`)
    .join("");
  elements.queryPanel.classList.remove("is-hidden");
}

function renderPapers(papers) {
  elements.paperCount.textContent = `${papers.length} 篇`;
  if (!papers.length) {
    elements.paperList.innerHTML = '<p class="section-copy">没有找到匹配的候选论文。</p>';
    elements.papersPanel.classList.remove("is-hidden");
    return;
  }

  elements.paperList.innerHTML = papers
    .map((paper, index) => {
      const authors = (paper.authors || []).slice(0, 4).join(" · ");
      const authorSuffix = (paper.authors || []).length > 4 ? " 等" : "";
      const categories = (paper.categories || [])
        .map((category) => `<span class="paper-category">${escapeHtml(category)}</span>`)
        .join("");
      return `
        <article class="paper-card">
          <div class="paper-topline">
            <span class="paper-rank">#${String(index + 1).padStart(2, "0")}</span>
            <span class="paper-meta">arXiv:${escapeHtml(paper.arxiv_id)} · ${formatDate(paper.published_at)}</span>
          </div>
          <h3><a href="${safeUrl(paper.abs_url)}" target="_blank" rel="noreferrer">${escapeHtml(paper.title)}</a></h3>
          <div class="paper-meta">${escapeHtml(authors)}${authorSuffix}</div>
          <div class="paper-categories">${categories}</div>
          <details>
            <summary>查看摘要</summary>
            <p>${escapeHtml(paper.abstract)}</p>
          </details>
        </article>`;
    })
    .join("");
  elements.papersPanel.classList.remove("is-hidden");
}

function renderUsage(usage) {
  const calls = usage.calls || [];
  const latest = calls[calls.length - 1];
  elements.promptTokens.textContent = formatNumber(usage.prompt_tokens);
  elements.completionTokens.textContent = formatNumber(usage.completion_tokens);
  elements.cacheHitTokens.textContent = formatNumber(usage.prompt_cache_hit_tokens);
  elements.totalTokens.textContent = formatNumber(usage.total_tokens);

  if (latest) {
    elements.modelChip.textContent = `${latest.provider} / ${latest.model}`;
    elements.metricNote.textContent = `${calls.length} 次模型调用 · 推理 Token ${formatNumber(usage.reasoning_tokens)}`;
  } else {
    elements.modelChip.textContent = "Demo planner / 无模型调用";
    elements.metricNote.textContent = "当前运行未产生可计费的 LLM token。";
  }

  const promptTotal = usage.prompt_cache_hit_tokens + usage.prompt_cache_miss_tokens;
  const rate = promptTotal > 0 ? usage.prompt_cache_hit_tokens / promptTotal : 0;
  elements.cacheHitRate.textContent = promptTotal > 0 ? `${Math.round(rate * 100)}%` : "—";
  elements.cacheMeter.style.width = `${Math.round(rate * 100)}%`;
}

function resetWorkspace() {
  appState.threadId = null;
  appState.result = null;
  hideError();
  elements.selectionPanel.classList.add("is-hidden");
  elements.queryPanel.classList.add("is-hidden");
  elements.papersPanel.classList.add("is-hidden");
  elements.detailStatus.textContent = "启动中";
  elements.detailThread.textContent = "—";
  elements.detailQuestion.textContent = elements.question.value.trim();
  elements.timeline.querySelectorAll("li").forEach((item) => {
    item.classList.remove("running", "completed", "waiting", "skipped");
    const conditional = ["generate_subquestions", "wait_for_user_selection"].includes(item.dataset.node);
    item.querySelector(".step-state").textContent = conditional ? "条件节点" : "待执行";
  });
  renderUsage(emptyUsage());
  elements.modelChip.textContent = "等待模型调用";
  elements.metricNote.textContent = "完成 LLM 调用后显示供应商返回的实际 usage。";
}

function setRunning(running) {
  appState.running = running;
  elements.runButton.disabled = running;
  elements.continueButton.disabled = running;
  elements.workflowPanel.classList.toggle("is-running", running);
  if (running) setRunStatus("running", "流程运行中");
}

function setRunStatus(kind, label) {
  elements.runStatus.className = `status-badge ${kind}`;
  elements.runStatus.textContent = label;
}

function handleFailure(error) {
  setRunning(false);
  setRunStatus("error", "执行失败");
  elements.detailStatus.textContent = "执行失败";
  elements.activity.textContent = "流程遇到错误，请查看下方信息或服务终端";
  showError(error instanceof Error ? error.message : String(error));
}

function showError(message) {
  elements.errorMessage.textContent = message;
  elements.errorPanel.classList.remove("is-hidden");
}

function hideError() {
  elements.errorPanel.classList.add("is-hidden");
  elements.errorMessage.textContent = "";
}

function emptyUsage() {
  return {
    prompt_tokens: 0,
    completion_tokens: 0,
    total_tokens: 0,
    prompt_cache_hit_tokens: 0,
    prompt_cache_miss_tokens: 0,
    reasoning_tokens: 0,
    calls: [],
  };
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("zh-CN");
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "日期未知" : date.toLocaleDateString("zh-CN");
}

function shortId(value) {
  return value ? `${value.slice(0, 8)}…` : "—";
}

function safeUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? escapeHtml(url.href) : "#";
  } catch (_error) {
    return "#";
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

checkHealth();
