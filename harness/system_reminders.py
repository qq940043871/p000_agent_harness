"""
System Reminders - 行为干预与防死循环机制

功能：
- 检测 Agent 行为模式
- 防止陷入死循环
- 自动注入干预提示
- 行为评分与警告
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Callable, Protocol

from .message import Message, MessageRole


class LoopType(Enum):
    """循环类型"""
    REPETITION = auto()      # 重复执行
    OSCILLATION = auto()     # 振荡（来回切换）
    STUCK = auto()           # 卡住
    NO_PROGRESS = auto()     # 无进展
    INFINITE_TOOL = auto()   # 无限调用工具


@dataclass
class BehaviorRecord:
    """行为记录"""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    action_type: str = ""           # 动作类型
    action_detail: str = ""          # 动作详情
    result: str = ""                 # 执行结果
    tokens_used: int = 0             # 消耗 Token
    loop_detected: LoopType | None = None


@dataclass
class LoopDetectionConfig:
    """循环检测配置"""
    max_repeated_actions: int = 3       # 最大重复动作次数
    max_tool_calls_same: int = 5         # 同一工具最大调用次数
    max_oscillations: int = 3            # 最大振荡次数
    window_size: int = 10                # 检测窗口大小
    progress_threshold: int = 3          # 无进展判定次数
    time_window_seconds: int = 120       # 时间窗口（秒）


@dataclass
class LoopWarning:
    """循环警告"""
    loop_type: LoopType
    severity: int                        # 1-5，5 最严重
    message: str
    suggestion: str
    evidence: list[str] = field(default_factory=list)
    suggested_injection: str = ""


class LoopDetector:
    """
    循环检测器

    检测并预防 Agent 陷入死循环。
    """

    def __init__(self, config: LoopDetectionConfig | None = None):
        self.config = config or LoopDetectionConfig()
        self._action_history: list[BehaviorRecord] = []
        self._tool_call_counts: dict[str, int] = {}
        self._last_progress_index: int = 0
        self._warnings: list[LoopWarning] = []

    def record_action(
        self,
        action_type: str,
        action_detail: str = "",
        result: str = "",
        tokens_used: int = 0,
    ) -> None:
        """记录 Agent 动作"""
        record = BehaviorRecord(
            action_type=action_type,
            action_detail=action_detail,
            result=result,
            tokens_used=tokens_used,
        )
        self._action_history.append(record)

        # 更新工具调用计数
        if action_type == "tool_call":
            tool_name = action_detail
            self._tool_call_counts[tool_name] = self._tool_call_counts.get(tool_name, 0) + 1

        # 清理过旧的记录
        self._cleanup_old_records()

    def _cleanup_old_records(self) -> None:
        """清理超过时间窗口的记录"""
        cutoff = datetime.now() - timedelta(seconds=self.config.time_window_seconds)
        cutoff_str = cutoff.isoformat()

        # 保留最近的记录
        self._action_history = [
            r for r in self._action_history
            if r.timestamp > cutoff_str
        ]

    def detect_loops(self) -> list[LoopWarning]:
        """
        检测循环

        Returns:
            检测到的循环警告列表
        """
        self._warnings = []
        window = self._action_history[-self.config.window_size:]

        # 检测重复动作
        self._check_repetition(window)

        # 检测工具调用过多
        self._check_excessive_tools()

        # 检测振荡
        self._check_oscillation(window)

        # 检测无进展
        self._check_no_progress()

        return self._warnings

    def _check_repetition(self, window: list[BehaviorRecord]) -> None:
        """检测重复动作"""
        if len(window) < self.config.max_repeated_actions:
            return

        # 检查连续重复
        for i in range(len(window) - self.config.max_repeated_actions + 1):
            consecutive = window[i:i + self.config.max_repeated_actions]
            if all(r.action_detail == consecutive[0].action_detail for r in consecutive):
                self._warnings.append(LoopWarning(
                    loop_type=LoopType.REPETITION,
                    severity=4,
                    message=f"检测到重复动作: {consecutive[0].action_detail}",
                    suggestion="你已经重复执行了相同的操作多次。请停止并尝试不同的方法。",
                    evidence=[r.action_detail for r in consecutive],
                ))
                break

    def _check_excessive_tools(self) -> None:
        """检测工具调用过多"""
        for tool_name, count in self._tool_call_counts.items():
            if count > self.config.max_tool_calls_same:
                self._warnings.append(LoopWarning(
                    loop_type=LoopType.INFINITE_TOOL,
                    severity=5,
                    message=f"工具 '{tool_name}' 被调用了 {count} 次",
                    suggestion=f"'{tool_name}' 似乎无法解决问题。请停止调用，尝试其他方法或请求人工帮助。",
                    evidence=[f"调用次数: {count}"],
                ))

    def _check_oscillation(self, window: list[BehaviorRecord]) -> None:
        """检测振荡模式（A-B-A-B）"""
        if len(window) < self.config.max_oscillations * 2:
            return

        # 检查是否有来回切换的模式
        for size in range(2, 4):  # 检查 2-3 长度的振荡
            for i in range(len(window) - size * 2):
                pattern1 = window[i:i + size]
                pattern2 = window[i + size:i + size * 2]

                if (all(p1.action_detail == p2.action_detail for p1, p2 in zip(pattern1, pattern2)) and
                    pattern1[0].action_detail != pattern2[0].action_detail):
                    self._warnings.append(LoopWarning(
                        loop_type=LoopType.OSCILLATION,
                        severity=3,
                        message=f"检测到振荡模式: {pattern1[0].action_detail} <-> {pattern2[0].action_detail}",
                        suggestion="你在两个操作之间来回切换。请停下来思考问题的根本原因。",
                        evidence=[p.action_detail for p in pattern1 + pattern2],
                    ))
                    return

    def _check_no_progress(self) -> None:
        """检测无进展"""
        if len(self._action_history) < self.config.progress_threshold * 2:
            return

        # 检查最近的结果是否都包含"失败"、"错误"等关键词
        recent_results = [r.result for r in self._action_history[-self.config.progress_threshold * 2:]]
        failure_keywords = ["error", "failed", "failure", "失败", "错误", "无法", "不行"]

        failure_count = sum(
            1 for result in recent_results
            if any(kw.lower() in result.lower() for kw in failure_keywords)
        )

        if failure_count >= self.config.progress_threshold:
            self._warnings.append(LoopWarning(
                loop_type=LoopType.NO_PROGRESS,
                severity=4,
                message=f"连续 {failure_count} 次操作失败",
                suggestion="你连续多次尝试都失败了。请停下来分析失败原因，或请求人工介入。",
                evidence=recent_results[-self.config.progress_threshold:],
            ))

    def reset(self) -> None:
        """重置检测状态"""
        self._action_history.clear()
        self._tool_call_counts.clear()
        self._warnings.clear()


class SystemReminder:
    """
    System Reminder 注入器

    在合适的时机自动注入干预提示，防止 Agent 行为失控。
    """

    def __init__(
        self,
        loop_detector: LoopDetector | None = None,
        max_reminders_per_turn: int = 2,
    ):
        self.loop_detector = loop_detector or LoopDetector()
        self.max_reminders_per_turn = max_reminders_per_turn
        self._injected_count = 0

    def generate_injection(
        self,
        turn_count: int,
        total_tokens: int = 0,
    ) -> str:
        """
        生成注入提醒

        Args:
            turn_count: 当前轮次
            total_tokens: 总消耗 Token

        Returns:
            注入的提醒文本
        """
        injections = []

        # 检测循环
        warnings = self.loop_detector.detect_loops()

        if warnings:
            # 按严重程度排序
            warnings.sort(key=lambda w: -w.severity)

            for warning in warnings[:self.max_reminders_per_turn]:
                if warning.suggested_injection:
                    injections.append(warning.suggested_injection)
                else:
                    injections.append(f"\n[系统提醒] {warning.message}\n{warning.suggestion}\n")

        # 超时提醒
        if turn_count > 30:
            injections.append(
                "\n[系统提醒] 你已经运行了很长时间（超过 30 轮）。"
                "请评估当前进度，如果问题复杂请请求人工帮助。\n"
            )

        # Token 警告
        if total_tokens > 100000:
            injections.append(
                f"\n[系统提醒] Token 消耗较高（{total_tokens:,}）。"
                "请注意效率，避免重复工作。\n"
            )

        if injections:
            self._injected_count += 1

        return "\n".join(injections)

    def build_reminder_prompt(
        self,
        turn_count: int,
        total_tokens: int = 0,
        include_behavior_check: bool = True,
    ) -> str:
        """
        构建完整的提醒提示

        Returns:
            提醒提示文本
        """
        parts = []

        # 生成注入
        injection = self.generate_injection(turn_count, total_tokens)
        if injection:
            parts.append(injection)

        # 行为检查清单
        if include_behavior_check:
            parts.append(BEHAVIOR_CHECKLIST)

        return "\n".join(parts)

    @property
    def injected_count(self) -> int:
        """已注入次数"""
        return self._injected_count


# ==================== 预设模板 ====================

BEHAVIOR_CHECKLIST = """
[行为检查清单]

在继续之前，请确认：
1. 你是否在重复同样的操作？检查最近 3-5 步是否相同。
2. 最近的尝试是否都在失败？连续失败说明方向错误。
3. 是否有进展？每一步都应该让你更接近目标。
4. Token 消耗是否过高？避免重复读取大文件。

如果以上任何一个问题的答案是"是"，请停下来思考新的方法。
"""

LOOP_INTERVENTION_TEMPLATE = """
[紧急干预]

检测到异常行为模式：
{loop_type}

你已经 {evidence}

{severity_stars}

建议立即停止当前操作：
{suggestion}

请用以下格式回复你的修正计划：
1. 停止原因：
2. 新的方法：
3. 预期结果：
"""


def format_loop_intervention(warning: LoopWarning) -> str:
    """格式化循环干预提示"""
    stars = "⚠️" * warning.severity
    return LOOP_INTERVENTION_TEMPLATE.format(
        loop_type=warning.loop_type.name,
        evidence="\n".join(f"- {e}" for e in warning.evidence),
        severity_stars=stars,
        suggestion=warning.suggestion,
    )


# ==================== Reminder 策略 ====================

class ReminderStrategy(Protocol):
    """提醒策略协议"""
    def should_inject(
        self,
        turn_count: int,
        token_usage: int,
        warnings: list[LoopWarning],
    ) -> bool: ...

    def get_injection(self, context: dict) -> str: ...


class ConservativeStrategy:
    """保守策略 - 只在明确问题时提醒"""
    def should_inject(self, turn_count: int, token_usage: int, warnings: list[LoopWarning]) -> bool:
        return any(w.severity >= 4 for w in warnings)

    def get_injection(self, context: dict) -> str:
        warnings = context.get("warnings", [])
        return "\n".join(w.suggestion for w in warnings if w.severity >= 4)


class AggressiveStrategy:
    """激进策略 - 频繁提醒"""
    def should_inject(self, turn_count: int, token_usage: int, warnings: list[LoopWarning]) -> bool:
        return turn_count > 5 or len(warnings) > 0

    def get_injection(self, context: dict) -> str:
        warnings = context.get("warnings", [])
        return "\n".join(w.suggestion for w in warnings)


class AdaptiveStrategy:
    """自适应策略 - 根据严重程度调整"""
    def should_inject(self, turn_count: int, token_usage: int, warnings: list[LoopWarning]) -> bool:
        if not warnings:
            return turn_count > 20  # 无警告时，20 轮后提醒

        # 根据严重程度调整
        max_severity = max(w.severity for w in warnings)
        return max_severity >= 3 or len(warnings) >= 2

    def get_injection(self, context: dict) -> str:
        warnings = context.get("warnings", [])
        return self._build_adaptive_injection(warnings)

    def _build_adaptive_injection(self, warnings: list[LoopWarning]) -> str:
        parts = []

        for w in warnings:
            if w.severity >= 4:
                parts.append(f"🔴 {w.message}\n{w.suggestion}")
            elif w.severity >= 3:
                parts.append(f"🟡 {w.message}\n{w.suggestion}")
            else:
                parts.append(f"💡 {w.suggestion}")

        return "\n\n".join(parts)
