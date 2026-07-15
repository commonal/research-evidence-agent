import type { LLMUsageSummary } from "../types";

export function UsagePanel({ usage, phase }: { usage: LLMUsageSummary; phase: string }) {
  const latest = usage.calls.at(-1);
  const finishedWithoutModel = !latest && ["waiting", "complete"].includes(phase);
  const promptTotal = usage.prompt_cache_hit_tokens + usage.prompt_cache_miss_tokens;
  const cacheRate = promptTotal > 0 ? usage.prompt_cache_hit_tokens / promptTotal : 0;

  return (
    <section className="panel metrics-panel">
      <div className="panel-heading compact">
        <div><span className="section-index">LIVE</span><h2>模型用量</h2></div>
      </div>
      <div className="model-chip">
        {latest
          ? `${latest.provider} / ${latest.model}`
          : finishedWithoutModel
            ? "Demo planner / 无模型调用"
            : "等待模型调用"}
      </div>
      <div className="metrics-grid">
        <Metric label="输入 Token" value={usage.prompt_tokens} />
        <Metric label="输出 Token" value={usage.completion_tokens} />
        <Metric label="缓存命中" value={usage.prompt_cache_hit_tokens} />
        <Metric label="总 Token" value={usage.total_tokens} />
      </div>
      <div className="cache-meter">
        <div><span>Prompt 缓存命中率</span><strong>{promptTotal ? `${Math.round(cacheRate * 100)}%` : "—"}</strong></div>
        <div className="meter-track"><i style={{ width: `${Math.round(cacheRate * 100)}%` }} /></div>
      </div>
      <p className="metric-note">
        {latest
          ? `${usage.calls.length} 次模型调用 · 推理 Token ${formatNumber(usage.reasoning_tokens)}`
          : finishedWithoutModel
            ? "当前运行未产生可计费的 LLM token。"
            : "完成 LLM 调用后显示供应商返回的实际 usage。"}
      </p>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return <div><small>{label}</small><strong>{formatNumber(value)}</strong></div>;
}

function formatNumber(value: number) {
  return Number(value || 0).toLocaleString("zh-CN");
}
