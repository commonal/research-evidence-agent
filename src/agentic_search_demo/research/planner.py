from __future__ import annotations

from typing import Protocol

from agentic_search_demo.research.state import SubQuestion


class QuestionPlanner(Protocol):
    name: str

    async def is_broad(self, question: str) -> bool: ...

    async def decompose(self, question: str) -> list[SubQuestion]: ...


class DemoQuestionPlanner:
    """Deterministic planner used for offline development and API tests."""

    name = "demo_question_planner"
    _focused_markers = (
        "是否",
        "能否",
        "如何",
        "为什么",
        "相比",
        "哪些",
        "在什么",
        "how",
        "why",
        "whether",
        "compare",
        "versus",
    )

    async def is_broad(self, question: str) -> bool:
        normalized = question.strip().lower()
        has_focus = any(marker in normalized for marker in self._focused_markers)
        return len(normalized) < 28 and not has_focus

    async def decompose(self, question: str) -> list[SubQuestion]:
        topic = question.strip().rstrip("？?")
        candidates = (
            (
                f"{topic}的主要技术路线及其核心机制是什么？",
                "梳理代表性方法、关键假设与技术演进。",
            ),
            (
                f"{topic}在典型 AI 任务中的效果与限制是什么？",
                "关注实验结果、适用场景与失败条件。",
            ),
            (
                f"{topic}研究通常使用哪些数据集和评价指标？",
                "比较常用实验设置以及指标的可比性。",
            ),
            (
                f"{topic}在不同模型规模和应用场景下的表现是否一致？",
                "考察结论在模型、数据和任务变化下的适用范围。",
            ),
        )
        return [
            SubQuestion(id=f"sq_{index}", question=text, scope=scope)
            for index, (text, scope) in enumerate(candidates, start=1)
        ]
