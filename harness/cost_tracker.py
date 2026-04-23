"""
Cost Tracker - Token 消耗追踪系统

功能：
- 实时追踪 Token 使用
- 成本计算
- 多轮对话成本报告
- 预算控制与告警
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any


class ModelType(Enum):
    """模型类型"""
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet"
    CLAUDE_3_HAIKU = "claude-3-haiku"
    GPT_4_O = "gpt-4o"
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_35_TURBO = "gpt-3.5-turbo"
    DEEPSEEK = "deepseek-chat"
    DOUYIN = "doubao-pro"
    QWEN = "qwen-plus"


@dataclass
class ModelPricing:
    """模型定价（每 1M Tokens）"""
    input_price: float = 3.0      # 输入 Token 价格（美元）
    output_price: float = 15.0     # 输出 Token 价格（美元）
    cache_creation_price: float = 3.75  # 缓存创建价格
    cache_read_price: float = 0.30     # 缓存读取价格


# 模型定价表（2024年最新）
MODEL_PRICING: dict[str, ModelPricing] = {
    "claude-3-5-sonnet": ModelPricing(
        input_price=3.0,
        output_price=15.0,
        cache_creation_price=3.75,
        cache_read_price=0.30,
    ),
    "claude-3-5-haiku": ModelPricing(
        input_price=0.8,
        output_price=4.0,
    ),
    "gpt-4o": ModelPricing(
        input_price=5.0,
        output_price=15.0,
    ),
    "gpt-4-turbo": ModelPricing(
        input_price=10.0,
        output_price=30.0,
    ),
    "gpt-3.5-turbo": ModelPricing(
        input_price=0.5,
        output_price=1.5,
    ),
    "deepseek-chat": ModelPricing(
        input_price=0.14,
        output_price=0.28,
    ),
    "doubao-pro": ModelPricing(
        input_price=0.8,
        output_price=2.0,
    ),
    "qwen-plus": ModelPricing(
        input_price=0.6,
        output_price=2.0,
    ),
}


@dataclass
class TokenUsage:
    """Token 使用记录"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """总 Token 数"""
        return (
            self.prompt_tokens +
            self.completion_tokens +
            self.cache_creation_tokens +
            self.cache_read_tokens
        )

    @property
    def cached_tokens(self) -> int:
        """缓存 Token 数"""
        return self.cache_creation_tokens + self.cache_read_tokens

    def to_dict(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class CostRecord:
    """成本记录"""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    model: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)
    cost: float = 0.0
    turn_count: int = 0
    session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnCost:
    """单轮成本"""
    turn: int
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class CostTracker:
    """
    成本追踪器

    追踪 Token 消耗和成本计算。
    """

    def __init__(
        self,
        default_model: str = "claude-3-5-sonnet",
        budget: float | None = None,
    ):
        self.default_model = default_model
        self.budget = budget

        # 成本记录
        self._records: list[CostRecord] = []
        self._turn_costs: list[TurnCost] = []

        # 当前会话
        self._current_session: str | None = None
        self._current_turn: int = 0

    def start_session(self, session_id: str) -> None:
        """开始新会话"""
        self._current_session = session_id
        self._current_turn = 0
        self._records.append(CostRecord(session_id=session_id))

    def end_session(self) -> CostRecord | None:
        """结束当前会话"""
        if not self._records or self._current_session is None:
            return None

        # 计算会话总成本
        session_records = [
            r for r in self._records
            if r.session_id == self._current_session
        ]

        total_usage = TokenUsage()
        total_cost = 0.0

        for record in session_records:
            total_usage.prompt_tokens += record.usage.prompt_tokens
            total_usage.completion_tokens += record.usage.completion_tokens
            total_cost += record.cost

        # 更新最后一条记录
        last_record = session_records[-1] if session_records else None
        if last_record:
            last_record.usage = total_usage
            last_record.cost = total_cost

        return last_record

    def record_usage(
        self,
        model: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> CostRecord:
        """
        记录 Token 使用

        Args:
            model: 模型名称
            prompt_tokens: 输入 Token 数
            completion_tokens: 输出 Token 数
            cache_creation_tokens: 缓存创建 Token 数
            cache_read_tokens: 缓存读取 Token 数
            metadata: 额外元数据

        Returns:
            成本记录
        """
        model = model or self.default_model
        self._current_turn += 1

        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_creation_tokens=cache_creation_tokens,
            cache_read_tokens=cache_read_tokens,
        )

        # 计算成本
        cost = self.calculate_cost(model, usage)

        record = CostRecord(
            model=model,
            usage=usage,
            cost=cost,
            turn_count=self._current_turn,
            session_id=self._current_session or "",
            metadata=metadata or {},
        )

        self._records.append(record)

        # 记录单轮成本
        self._turn_costs.append(TurnCost(
            turn=self._current_turn,
            model=model,
            input_tokens=prompt_tokens + cache_read_tokens,
            output_tokens=completion_tokens,
            cost=cost,
        ))

        return record

    def calculate_cost(self, model: str, usage: TokenUsage) -> float:
        """
        计算成本

        Args:
            model: 模型名称
            usage: Token 使用量

        Returns:
            成本（美元）
        """
        pricing = MODEL_PRICING.get(model, ModelPricing())

        # 计算各部分成本
        input_cost = usage.prompt_tokens * pricing.input_price / 1_000_000
        output_cost = usage.completion_tokens * pricing.output_price / 1_000_000

        cache_creation_cost = usage.cache_creation_tokens * pricing.cache_creation_price / 1_000_000
        cache_read_cost = usage.cache_read_tokens * pricing.cache_read_price / 1_000_000

        return input_cost + output_cost + cache_creation_cost + cache_read_cost

    # ==================== 统计方法 ====================

    def get_total_cost(self, session_id: str | None = None) -> float:
        """获取总成本"""
        records = self._records
        if session_id:
            records = [r for r in records if r.session_id == session_id]
        return sum(r.cost for r in records)

    def get_total_tokens(self, session_id: str | None = None) -> TokenUsage:
        """获取总 Token 数"""
        records = self._records
        if session_id:
            records = [r for r in records if r.session_id == session_id]

        total = TokenUsage()
        for record in records:
            total.prompt_tokens += record.usage.prompt_tokens
            total.completion_tokens += record.usage.completion_tokens
            total.cache_creation_tokens += record.usage.cache_creation_tokens
            total.cache_read_tokens += record.usage.cache_read_tokens

        return total

    def get_turn_count(self) -> int:
        """获取当前轮次"""
        return self._current_turn

    def get_stats(self) -> dict:
        """获取完整统计信息"""
        total_usage = self.get_total_tokens()
        total_cost = self.get_total_cost()
        
        return {
            "total_cost": total_cost,
            "total_prompt_tokens": total_usage.prompt_tokens,
            "total_completion_tokens": total_usage.completion_tokens,
            "total_tokens": total_usage.total_tokens,
            "turn_count": self._current_turn,
            "average_cost_per_turn": self.get_average_cost_per_turn(),
            "budget": self.budget,
            "over_budget": self.should_stop() if self.budget else False,
        }

    def get_average_cost_per_turn(self) -> float:
        """获取平均每轮成本"""
        if self._current_turn == 0:
            return 0.0
        return self.get_total_cost() / self._current_turn

    def get_cost_breakdown(self, session_id: str | None = None) -> dict[str, float]:
        """获取成本细分"""
        records = self._records
        if session_id:
            records = [r for r in records if r.session_id == session_id]

        breakdown: dict[str, dict[str, int]] = {}

        for record in records:
            model = record.model
            if model not in breakdown:
                breakdown[model] = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "turn_count": 0,
                }

            breakdown[model]["prompt_tokens"] += record.usage.prompt_tokens
            breakdown[model]["completion_tokens"] += record.usage.completion_tokens
            breakdown[model]["turn_count"] += 1

        # 计算每模型的美元成本
        result = {}
        for model, data in breakdown.items():
            usage = TokenUsage(
                prompt_tokens=data["prompt_tokens"],
                completion_tokens=data["completion_tokens"],
            )
            result[model] = {
                "cost": self.calculate_cost(model, usage),
                "turns": data["turn_count"],
            }

        return result

    # ==================== 预算控制 ====================

    def check_budget(self) -> tuple[bool, float]:
        """
        检查预算

        Returns:
            (是否超预算, 当前成本)
        """
        current_cost = self.get_total_cost()
        if self.budget is None:
            return False, current_cost

        return current_cost >= self.budget, current_cost

    def should_stop(self) -> bool:
        """判断是否应该停止（超预算）"""
        over_budget, _ = self.check_budget()
        return over_budget

    # ==================== 报告生成 ====================

    def generate_report(self, session_id: str | None = None) -> str:
        """生成成本报告"""
        records = self._records
        if session_id:
            records = [r for r in records if r.session_id == session_id]

        if not records:
            return "暂无成本记录"

        total_usage = self.get_total_tokens(session_id)
        total_cost = self.get_total_cost(session_id)
        turn_count = len(records)
        avg_cost = total_cost / turn_count if turn_count > 0 else 0

        # 模型使用分布
        model_usage: dict[str, dict[str, int]] = {}
        for record in records:
            model = record.model
            if model not in model_usage:
                model_usage[model] = {"input": 0, "output": 0, "turns": 0}
            model_usage[model]["input"] += record.usage.prompt_tokens
            model_usage[model]["output"] += record.usage.completion_tokens
            model_usage[model]["turns"] += 1

        lines = [
            "=" * 50,
            "📊 成本报告",
            "=" * 50,
            f"会话 ID: {session_id or '全部'}",
            f"总轮次: {turn_count}",
            "-" * 50,
            "Token 使用统计:",
            f"  输入 Tokens:  {total_usage.prompt_tokens:,}",
            f"  输出 Tokens:  {total_usage.completion_tokens:,}",
            f"  缓存读取:    {total_usage.cache_read_tokens:,}",
            f"  总计:        {total_usage.total_tokens:,}",
            "-" * 50,
            "💰 成本统计:",
            f"  总成本:      ${total_cost:.4f}",
            f"  平均/轮:     ${avg_cost:.4f}",
            f"  预算状态:    {'⚠️ 超预算' if self.should_stop() else '✅ 正常'}",
        ]

        if self.budget:
            lines.append(f"  预算上限:    ${self.budget:.2f}")

        if model_usage:
            lines.append("-" * 50)
            lines.append("📱 模型使用分布:")
            for model, data in model_usage.items():
                model_cost = self.calculate_cost(
                    model,
                    TokenUsage(prompt_tokens=data["input"], completion_tokens=data["output"])
                )
                lines.append(f"  {model}:")
                lines.append(f"    Tokens: {data['input']:,} → {data['output']:,}")
                lines.append(f"    成本: ${model_cost:.4f} ({data['turns']} 轮)")

        lines.append("=" * 50)

        return "\n".join(lines)

    # ==================== 持久化 ====================

    def save(self, path: str | Path) -> None:
        """保存到文件"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "budget": self.budget,
            "default_model": self.default_model,
            "records": [
                {
                    **r.__dict__,
                    "usage": r.usage.to_dict(),
                }
                for r in self._records
            ],
            "turn_costs": [
                {
                    "turn": tc.turn,
                    "model": tc.model,
                    "input_tokens": tc.input_tokens,
                    "output_tokens": tc.output_tokens,
                    "cost": tc.cost,
                    "timestamp": tc.timestamp,
                }
                for tc in self._turn_costs
            ],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> "CostTracker":
        """从文件加载"""
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        tracker = cls(
            default_model=data.get("default_model", "claude-3-5-sonnet"),
            budget=data.get("budget"),
        )

        # 重建记录
        for record_data in data.get("records", []):
            usage_data = record_data.pop("usage", {})
            usage = TokenUsage(**usage_data)
            record = CostRecord(**record_data, usage=usage)
            tracker._records.append(record)

        return tracker


# ==================== 装饰器 ====================

def track_cost(tracker: CostTracker, model: str | None = None):
    """
    追踪成本的装饰器

    Usage:
        @track_cost(tracker, "gpt-4")
        async def call_llm(prompt):
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            # 从结果中提取 token 使用
            if isinstance(result, dict):
                tracker.record_usage(
                    model=model,
                    prompt_tokens=result.get("usage", {}).get("prompt_tokens", 0),
                    completion_tokens=result.get("usage", {}).get("completion_tokens", 0),
                    cache_creation_tokens=result.get("usage", {}).get("cache_creation_tokens", 0),
                    cache_read_tokens=result.get("usage", {}).get("cache_read_tokens", 0),
                )

            return result

        return wrapper
    return decorator
