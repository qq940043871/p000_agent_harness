"""
Context Compaction - 上下文压缩模块

实现阶梯降级策略，根据 Token 预算动态压缩对话上下文。

阶梯降级策略：
1. 保留 System Prompt 和 Agent 规范（最高优先级）
2. 保留最近 N 轮对话
3. 中间消息尝试摘要
4. 早期消息完全压缩或丢弃
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Protocol

from .message import Message, MessageRole


class CompactionStrategy(Enum):
    """压缩策略"""
    NONE = auto()           # 不压缩
    TRUNCATE = auto()       # 直接截断
    SUMMARY = auto()        # 生成摘要
    MIXED = auto()          # 混合策略：最近消息保留，远端摘要


class CompactionLevel(Enum):
    """压缩级别（优先级从高到低）"""
    SYSTEM = 0      # System Prompt - 永不压缩
    AGENTS = 1      # AGENTS.md 等规范文件
    TOOL_DEFS = 2   # 工具定义
    RECENT = 3      # 最近 N 轮对话
    MIDDLE = 4      # 中间消息
    OLD = 5         # 早期消息


@dataclass
class CompactionConfig:
    """压缩配置"""
    # Token 预算配置
    max_total_tokens: int = 128000       # 最大总 Token
    reserved_tokens: int = 32000          # 保留空间（给输出）
    min_context_tokens: int = 4000        # 最少上下文 Token

    # 阶梯降级阈值
    warning_threshold: float = 0.75       # 警告阈值（75%）
    compaction_threshold: float = 0.85    # 开始压缩阈值（85%）

    # 摘要配置
    summary_model: str = "claude-3-haiku"  # 摘要用小模型
    summary_instruction: str = "简明摘要，保留关键信息："

    # 保留策略
    preserve_last_n: int = 6              # 保留最近 N 轮
    preserve_tools: bool = True           # 保留工具定义


@dataclass
class TokenEstimate:
    """Token 估算结果"""
    total: int = 0
    system: int = 0
    tools: int = 0
    messages: int = 0
    available: int = 0

    @property
    def usage_ratio(self) -> float:
        """使用比例"""
        if self.total == 0:
            return 0.0
        return (self.total - self.available) / self.total


class TokenCounter(Protocol):
    """Token 计数器协议"""
    def count(self, text: str) -> int: ...


class SimpleTokenCounter:
    """简单的 Token 计数器（按字数估算）"""

    def count(self, text: str) -> int:
        """中英文混合估算：中文 2 字符 ≈ 1 Token，英文 4 字符 ≈ 1 Token"""
        if not text:
            return 0

        # 统计中文字符和英文字符
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        other_chars = len(text) - chinese_chars - english_chars

        # 估算 Token
        return (chinese_chars * 0.5) + (english_chars * 0.25) + (other_chars * 0.25)


class TiktokenCounter:
    """Tiktoken Token 计数器（精确）"""

    def __init__(self, encoding: str = "cl100k_base"):
        self._counter: TokenCounter = SimpleTokenCounter()  # 默认回退
        try:
            import tiktoken
            self._encoder = tiktoken.get_encoding(encoding)
        except ImportError:
            self._encoder = None

    def count(self, text: str) -> int:
        if self._encoder:
            return len(self._encoder.encode(text))
        return self._counter.count(text)


@dataclass
class CompactionResult:
    """压缩结果"""
    original_count: int = 0       # 原始消息数
    compressed_count: int = 0     # 压缩后消息数
    original_tokens: int = 0      # 原始 Token 数
    compressed_tokens: int = 0    # 压缩后 Token 数
    removed_messages: int = 0     # 删除的消息数
    summaries_added: int = 0      # 添加的摘要数
    strategy: CompactionStrategy = CompactionStrategy.NONE


class ContextCompactor:
    """
    上下文压缩器

    使用阶梯降级策略压缩对话上下文，保持关键信息的同时控制 Token 消耗。
    """

    def __init__(
        self,
        config: CompactionConfig | None = None,
        token_counter: TokenCounter | None = None,
    ):
        self.config = config or CompactionConfig()
        self.counter = token_counter or SimpleTokenCounter()

        # 压缩策略
        self._strategy_callbacks: list[Callable[[list[Message]], list[Message]]] = []

    def register_strategy(
        self,
        name: str,
        callback: Callable[[list[Message]], list[Message]]
    ) -> None:
        """注册自定义压缩策略"""
        self._strategy_callbacks.append(callback)

    def estimate_tokens(
        self,
        system_prompt: str,
        tools: list[dict],
        messages: list[Message]
    ) -> TokenEstimate:
        """估算当前 Token 使用情况"""
        system_tokens = self.counter.count(system_prompt)
        tool_tokens = sum(self.counter.count(json.dumps(t, ensure_ascii=False)) for t in tools)
        message_tokens = sum(self.counter.count(m.content or "") for m in messages)

        max_tokens = self.config.max_total_tokens - self.config.reserved_tokens

        return TokenEstimate(
            total=max_tokens,
            system=system_tokens,
            tools=tool_tokens,
            messages=message_tokens,
            available=max_tokens - system_tokens - tool_tokens - message_tokens
        )

    def should_compact(self, estimate: TokenEstimate) -> bool:
        """判断是否需要压缩"""
        used = estimate.total - estimate.available
        return (used / estimate.total) >= self.config.compaction_threshold

    def get_compaction_level(self, estimate: TokenEstimate) -> CompactionLevel:
        """获取当前压缩级别"""
        ratio = (estimate.total - estimate.available) / estimate.total

        if ratio < 0.5:
            return CompactionLevel.RECENT
        elif ratio < 0.7:
            return CompactionLevel.MIDDLE
        else:
            return CompactionLevel.OLD

    def compact(
        self,
        messages: list[Message],
        target_tokens: int | None = None,
        strategy: CompactionStrategy = CompactionStrategy.MIXED
    ) -> CompactionResult:
        """
        执行上下文压缩

        Args:
            messages: 原始消息列表
            target_tokens: 目标 Token 数（可选）
            strategy: 压缩策略

        Returns:
            压缩结果
        """
        original_count = len(messages)
        original_tokens = sum(self.counter.count(m.content or "") for m in messages)

        if target_tokens is None:
            target_tokens = self.config.min_context_tokens

        # 应用压缩策略
        if strategy == CompactionStrategy.NONE:
            return CompactionResult(
                original_count=original_count,
                compressed_count=original_count,
                original_tokens=original_tokens,
                compressed_tokens=original_tokens
            )

        elif strategy == CompactionStrategy.TRUNCATE:
            compressed = self._truncate(messages, target_tokens)

        elif strategy == CompactionStrategy.SUMMARY:
            compressed = self._summarize(messages, target_tokens)

        elif strategy == CompactionStrategy.MIXED:
            compressed = self._mixed_compaction(messages, target_tokens)

        else:
            compressed = messages

        # 计算结果
        compressed_tokens = sum(self.counter.count(m.content or "") for m in compressed)

        return CompactionResult(
            original_count=original_count,
            compressed_count=len(compressed),
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            removed_messages=original_count - len(compressed),
            strategy=strategy
        )

    def _truncate(self, messages: list[Message], target_tokens: int) -> list[Message]:
        """直接截断策略：从最旧的消息开始删除"""
        # 保留最近的 N 条
        preserved = messages[-self.config.preserve_last_n:]

        # 如果保留的消息已满足需求，直接返回
        preserved_tokens = sum(self.counter.count(m.content or "") for m in preserved)
        if preserved_tokens <= target_tokens:
            return preserved

        # 否则只保留最后一条
        return [messages[-1]]

    def _summarize(self, messages: list[Message], target_tokens: int) -> list[Message]:
        """摘要策略：将旧消息替换为摘要"""
        if len(messages) <= self.config.preserve_last_n:
            return messages

        # 保留最近的消息
        preserved = messages[-self.config.preserve_last_n:]

        # 对旧消息生成摘要
        old_messages = messages[:-self.config.preserve_last_n]
        summary = self._generate_summary(old_messages)

        # 创建摘要消息
        summary_msg = Message(
            role=MessageRole.SYSTEM,
            content=f"[早期对话摘要]\n{summary}",
            metadata={"compacted": True, "original_count": len(old_messages)}
        )

        return [summary_msg] + preserved

    def _mixed_compaction(self, messages: list[Message], target_tokens: int) -> list[Message]:
        """
        混合压缩策略：
        1. 保留最近的 N 条消息
        2. 中间消息生成摘要
        3. 早期消息丢弃
        """
        if len(messages) <= self.config.preserve_last_n:
            return messages

        # 计算当前 Token
        current_tokens = sum(self.counter.count(m.content or "") for m in messages)

        # 如果已经满足要求，不压缩
        if current_tokens <= target_tokens:
            return messages

        # 保留最近消息
        preserved = messages[-self.config.preserve_last_n:]
        preserved_tokens = sum(self.counter.count(m.content or "") for m in preserved)

        # 中间部分
        middle_start = self.config.preserve_last_n // 2
        middle_end = len(messages) - self.config.preserve_last_n
        middle_messages = messages[middle_start:middle_end]

        # 早期部分（丢弃）
        old_messages = messages[:middle_start]

        result = []

        # 添加早期摘要（如果有）
        if old_messages and self.config.preserve_last_n > 3:
            old_summary = self._generate_summary(old_messages)
            result.append(Message(
                role=MessageRole.SYSTEM,
                content=f"[早期对话摘要]\n{old_summary}",
                metadata={"compacted": True, "type": "old_summary"}
            ))

        # 添加中间摘要（如果有）
        if middle_messages:
            middle_summary = self._generate_summary(middle_messages)
            result.append(Message(
                role=MessageRole.SYSTEM,
                content=f"[中间对话摘要]\n{middle_summary}",
                metadata={"compacted": True, "type": "middle_summary"}
            ))

        # 添加保留的消息
        result.extend(preserved)

        return result

    def _generate_summary(self, messages: list[Message]) -> str:
        """生成消息摘要"""
        if not messages:
            return ""

        # 简单摘要：提取关键信息
        summary_parts = []

        for msg in messages[:10]:  # 最多处理 10 条
            if msg.content:
                # 截取前 100 字符
                content = msg.content[:100]
                if len(msg.content) > 100:
                    content += "..."
                summary_parts.append(f"[{msg.role.value}] {content}")

        if len(messages) > 10:
            summary_parts.append(f"... (共 {len(messages)} 条消息已摘要)")

        return "\n".join(summary_parts)


class StreamingCompactor(ContextCompactor):
    """
    流式压缩器 - 支持增量压缩

    在长对话中持续监控 Token 使用情况，自动触发压缩。
    """

    def __init__(
        self,
        config: CompactionConfig | None = None,
        token_counter: TokenCounter | None = None,
        auto_compact: bool = True,
    ):
        super().__init__(config, token_counter)
        self.auto_compact = auto_compact
        self._last_compaction: CompactionResult | None = None
        self._compaction_count = 0

    def check_and_compact(
        self,
        system_prompt: str,
        tools: list[dict],
        messages: list[Message],
        force: bool = False
    ) -> tuple[list[Message], CompactionResult | None]:
        """
        检查并执行压缩（如果需要）

        Returns:
            (压缩后的消息, 压缩结果或None)
        """
        estimate = self.estimate_tokens(system_prompt, tools, messages)

        # 检查是否需要压缩
        if not force and not self.should_compact(estimate):
            return messages, None

        # 执行压缩
        result = self.compact(messages, strategy=CompactionStrategy.MIXED)
        self._last_compaction = result
        self._compaction_count += 1

        # 重新估算
        compressed_messages = self._get_compressed_messages(messages, result)

        return compressed_messages, result

    def _get_compressed_messages(
        self,
        messages: list[Message],
        result: CompactionResult
    ) -> list[Message]:
        """根据压缩结果获取压缩后的消息"""
        if result.strategy == CompactionStrategy.MIXED:
            return self._mixed_compaction(messages, self.config.min_context_tokens)
        elif result.strategy == CompactionStrategy.TRUNCATE:
            return self._truncate(messages, self.config.min_context_tokens)
        elif result.strategy == CompactionStrategy.SUMMARY:
            return self._summarize(messages, self.config.min_context_tokens)
        return messages

    @property
    def compaction_count(self) -> int:
        """压缩次数"""
        return self._compaction_count

    @property
    def last_result(self) -> CompactionResult | None:
        """最后一次压缩结果"""
        return self._last_compaction


# ==================== Prompt 模板 ====================

COMPACTION_WARNING_TEMPLATE = """
[上下文即将达到限制]

当前 Token 使用情况：
- 系统/工具: {system_tokens} tokens
- 对话消息: {message_tokens} tokens
- 可用空间: {available_tokens} tokens

已执行 {compaction_count} 次压缩。
"""


def format_compaction_warning(
    estimate: TokenEstimate,
    compaction_count: int = 0
) -> str:
    """格式化压缩警告"""
    return COMPACTION_WARNING_TEMPLATE.format(
        system_tokens=estimate.system + estimate.tools,
        message_tokens=estimate.messages,
        available_tokens=estimate.available,
        compaction_count=compaction_count
    )
