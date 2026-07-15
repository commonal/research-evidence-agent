import { useEffect, useRef, useState } from "react";

import type { ResearchSelection, SubQuestion } from "../types";

interface QuestionSelectionProps {
  options: SubQuestion[];
  disabled: boolean;
  onSelect: (selection: ResearchSelection) => void | Promise<void>;
}

export function QuestionSelection({ options, disabled, onSelect }: QuestionSelectionProps) {
  const panelRef = useRef<HTMLElement>(null);
  const [optionId, setOptionId] = useState(options[0]?.id || "");
  const [customQuestion, setCustomQuestion] = useState("");
  const [validationError, setValidationError] = useState("");

  useEffect(() => {
    setOptionId(options[0]?.id || "");
    setCustomQuestion("");
    setValidationError("");
  }, [options]);

  useEffect(() => {
    panelRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  function submit() {
    const custom = customQuestion.trim();
    if (custom && custom.length < 3) {
      setValidationError("自定义问题至少需要 3 个字符。");
      return;
    }
    if (!custom && !optionId) {
      setValidationError("请选择一个候选问题，或输入自定义问题。");
      return;
    }
    setValidationError("");
    void onSelect(custom ? { question: custom } : { option_id: optionId });
  }

  return (
    <section className="panel selection-panel" ref={panelRef}>
      <div className="panel-heading">
        <div><span className="section-index">03</span><h2>选择研究方向</h2></div>
        <span className="status-badge waiting">等待你的选择</span>
      </div>
      <p className="section-copy">原问题范围较宽。选择一个候选问题，或输入你修改后的具体问题。</p>
      <div className="selection-options">
        {options.map((option) => (
          <label className="selection-option" key={option.id}>
            <input
              type="radio"
              name="research-option"
              value={option.id}
              checked={optionId === option.id}
              onChange={() => setOptionId(option.id)}
              disabled={disabled}
            />
            <span><strong>{option.question}</strong><small>{option.scope}</small></span>
          </label>
        ))}
      </div>
      <label className="custom-question-label" htmlFor="custom-question">或者，自定义最终问题</label>
      <textarea
        id="custom-question"
        rows={3}
        placeholder="输入更具体、可检索的研究问题"
        value={customQuestion}
        onChange={(event) => setCustomQuestion(event.target.value)}
        disabled={disabled}
      />
      {validationError && <p className="inline-error">{validationError}</p>}
      <div className="selection-actions">
        <button type="button" className="primary-button" onClick={submit} disabled={disabled}>
          <span>{disabled ? "正在继续" : "确认并继续"}</span><b aria-hidden="true">→</b>
        </button>
      </div>
    </section>
  );
}
