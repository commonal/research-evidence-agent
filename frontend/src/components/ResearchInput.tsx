import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";

interface ResearchInputProps {
  disabled: boolean;
  onSubmit: (question: string) => void | Promise<void>;
}

const examples = [
  ["长上下文 vs RAG", "长上下文模型能否在多跳问答任务中替代 RAG？"],
  ["宽泛问题拆解", "大模型记忆"],
] as const;

export function ResearchInput({ disabled, onSubmit }: ResearchInputProps) {
  const [question, setQuestion] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const normalized = question.trim();
    if (normalized.length >= 3 && !disabled) void onSubmit(normalized);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <section className="panel question-panel">
      <div className="panel-heading">
        <div><span className="section-index">01</span><h2>提出研究问题</h2></div>
        <span className="hint">Ctrl + Enter 开始</span>
      </div>
      <form onSubmit={submit}>
        <label className="sr-only" htmlFor="question-input">研究问题</label>
        <textarea
          id="question-input"
          ref={inputRef}
          name="question"
          minLength={3}
          maxLength={2000}
          rows={5}
          placeholder="例如：长上下文模型能否在多跳问答任务中替代 RAG？"
          required
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={handleKeyDown}
        />
        <div className="example-row" aria-label="示例问题">
          <span>试试：</span>
          {examples.map(([label, value]) => (
            <button
              key={label}
              type="button"
              className="example-chip"
              onClick={() => {
                setQuestion(value);
                inputRef.current?.focus();
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="form-footer">
          <p>当前范围：问题规划 · DeepSeek 检索式 · arXiv 论文发现</p>
          <button className="primary-button" type="submit" disabled={disabled}>
            <span>{disabled ? "研究进行中" : "开始研究"}</span><b aria-hidden="true">→</b>
          </button>
        </div>
      </form>
    </section>
  );
}
