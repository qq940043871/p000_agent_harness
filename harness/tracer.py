"""
Tracer - Agent 执行链路追踪系统

功能：
- 完整的执行链路记录
- 失败决策路径复盘
- 性能分析
- 可视化追踪
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any
from uuid import uuid4


class SpanType(Enum):
    """Span 类型"""
    LLM_CALL = auto()           # LLM 调用
    TOOL_CALL = auto()          # 工具调用
    COMPACTION = auto()         # 上下文压缩
    THOUGHT = auto()            # 思考过程
    ACTION = auto()             # 行动
    OBSERVATION = auto()        # 观察
    RESPONSE = auto()           # 响应
    ERROR = auto()              # 错误


class SpanStatus(Enum):
    """Span 状态"""
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class Span:
    """执行 Span"""
    span_id: str
    trace_id: str
    parent_id: str | None

    name: str = ""
    span_type: SpanType = SpanType.ACTION

    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: str | None = None
    duration_ms: float = 0.0

    status: SpanStatus = SpanStatus.OK
    error_message: str = ""

    # 内容
    input: Any = None
    output: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # 子 Span
    children: list[Span] = field(default_factory=list)

    def __post_init__(self):
        if not self.name:
            self.name = self.span_type.name

    def finish(self, status: SpanStatus = SpanStatus.OK, error: str = "") -> None:
        """结束 Span"""
        self.end_time = datetime.now().isoformat()
        self.status = status
        self.error_message = error

        # 计算持续时间
        try:
            start = datetime.fromisoformat(self.start_time)
            end = datetime.fromisoformat(self.end_time)
            self.duration_ms = (end - start).total_seconds() * 1000
        except ValueError:
            self.duration_ms = 0.0

    def add_child(self, span: Span) -> None:
        """添加子 Span"""
        self.children.append(span)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "type": self.span_type.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "error_message": self.error_message,
            "input": self.input,
            "output": self.output,
            "metadata": self.metadata,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class Trace:
    """完整追踪"""
    trace_id: str
    session_id: str = ""
    user_message: str = ""

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ended_at: str | None = None
    total_duration_ms: float = 0.0

    spans: list[Span] = field(default_factory=list)
    root_span: Span | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    # 统计
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0

    status: SpanStatus = SpanStatus.OK
    error_message: str = ""

    def finish(self, status: SpanStatus = SpanStatus.OK, error: str = "") -> None:
        """结束追踪"""
        self.ended_at = datetime.now().isoformat()
        self.status = status
        self.error_message = error

        # 计算总持续时间
        try:
            start = datetime.fromisoformat(self.created_at)
            end = datetime.fromisoformat(self.ended_at)
            self.total_duration_ms = (end - start).total_seconds() * 1000
        except ValueError:
            self.total_duration_ms = 0.0

    def add_span(self, span: Span) -> None:
        """添加 Span"""
        self.spans.append(span)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "user_message": self.user_message,
            "created_at": self.created_at,
            "ended_at": self.ended_at,
            "total_duration_ms": self.total_duration_ms,
            "total_llm_calls": self.total_llm_calls,
            "total_tool_calls": self.total_tool_calls,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "status": self.status.value,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "spans": [s.to_dict() for s in self.spans],
        }


class Tracer:
    """
    链路追踪器

    记录 Agent 的完整执行链路。
    """

    def __init__(self, storage_path: str | Path | None = None):
        self.storage_path = Path(storage_path) if storage_path else None
        if self.storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)

        # 当前追踪
        self._current_trace: Trace | None = None
        self._span_stack: list[Span] = []
        self._trace_cache: dict[str, Trace] = {}

    # ==================== 追踪管理 ====================

    def start_trace(
        self,
        session_id: str,
        user_message: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        开始新追踪

        Returns:
            trace_id
        """
        trace_id = str(uuid4())[:16]
        self._current_trace = Trace(
            trace_id=trace_id,
            session_id=session_id,
            user_message=user_message,
            metadata=metadata or {},
        )
        self._span_stack.clear()
        return trace_id

    def end_trace(
        self,
        status: SpanStatus = SpanStatus.OK,
        error: str = "",
    ) -> Trace | None:
        """结束当前追踪"""
        if not self._current_trace:
            return None

        self._current_trace.finish(status, error)

        # 保存到缓存
        self._trace_cache[self._current_trace.trace_id] = self._current_trace

        # 持久化
        if self.storage_path:
            self._save_trace(self._current_trace)

        trace = self._current_trace
        self._current_trace = None
        self._span_stack.clear()

        return trace

    # ==================== Span 管理 ====================

    def start_span(
        self,
        name: str,
        span_type: SpanType,
        input: Any = None,
        parent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Span:
        """开始新 Span"""
        if not self._current_trace:
            raise RuntimeError("No active trace")

        span = Span(
            span_id=str(uuid4())[:16],
            trace_id=self._current_trace.trace_id,
            parent_id=parent_id,
            name=name,
            span_type=span_type,
            input=input,
            metadata=metadata or {},
        )

        # 如果有父 Span，添加到父
        if self._span_stack and parent_id is None:
            parent = self._span_stack[-1]
            parent.add_child(span)

        # 更新追踪统计
        if span_type == SpanType.LLM_CALL:
            self._current_trace.total_llm_calls += 1
        elif span_type == SpanType.TOOL_CALL:
            self._current_trace.total_tool_calls += 1

        self._current_trace.add_span(span)
        self._span_stack.append(span)

        return span

    def end_span(
        self,
        span: Span,
        output: Any = None,
        status: SpanStatus = SpanStatus.OK,
        error: str = "",
    ) -> None:
        """结束 Span"""
        span.output = output
        span.finish(status, error)

        # 弹出栈
        if self._span_stack and self._span_stack[-1] == span:
            self._span_stack.pop()

    @property
    def current_span(self) -> Span | None:
        """获取当前 Span"""
        return self._span_stack[-1] if self._span_stack else None

    # ==================== 便捷方法 ====================

    def trace_llm_call(
        self,
        model: str,
        messages: list[dict],
        response: dict | None = None,
    ) -> Span:
        """追踪 LLM 调用"""
        span = self.start_span(
            name=f"LLM:{model}",
            span_type=SpanType.LLM_CALL,
            input={"model": model, "message_count": len(messages)},
        )

        if response:
            span.output = response
            # 提取 token 使用
            usage = response.get("usage", {})
            tokens = usage.get("total_tokens", 0)
            self._current_trace.total_tokens += tokens

        return span

    def trace_tool_call(
        self,
        tool_name: str,
        arguments: dict,
        result: Any = None,
    ) -> Span:
        """追踪工具调用"""
        return self.start_span(
            name=f"Tool:{tool_name}",
            span_type=SpanType.TOOL_CALL,
            input={"tool": tool_name, "args": arguments},
            metadata={"result": result} if result else {},
        )

    def trace_thought(self, thought: str) -> Span:
        """追踪思考过程"""
        return self.start_span(
            name="Think",
            span_type=SpanType.THOUGHT,
            input=thought,
        )

    def trace_action(self, action: str, target: str | None = None) -> Span:
        """追踪行动"""
        return self.start_span(
            name=f"Action:{action}",
            span_type=SpanType.ACTION,
            input={"action": action, "target": target},
        )

    def trace_error(
        self,
        error: str,
        context: dict | None = None,
    ) -> Span:
        """追踪错误"""
        return self.start_span(
            name="Error",
            span_type=SpanType.ERROR,
            input=error,
            metadata=context or {},
        )

    # ==================== 上下文管理器 ====================

    class SpanContext:
        """Span 上下文管理器"""

        def __init__(self, tracer: Tracer, span: Span):
            self.tracer = tracer
            self.span = span

        def __enter__(self):
            return self.span

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                self.span.finish(SpanStatus.ERROR, str(exc_val))
            else:
                self.span.finish()
            return False

    def span(
        self,
        name: str,
        span_type: SpanType = SpanType.ACTION,
        input: Any = None,
    ) -> SpanContext:
        """创建 Span 上下文管理器"""
        span = self.start_span(name, span_type, input)
        return self.SpanContext(self, span)

    # ==================== 查询与分析 ====================

    def get_trace(self, trace_id: str) -> Trace | None:
        """获取追踪"""
        if trace_id in self._trace_cache:
            return self._trace_cache[trace_id]

        # 从磁盘加载
        if self.storage_path:
            path = self.storage_path / f"{trace_id}.json"
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return self._reconstruct_trace(data)

        return None

    def _reconstruct_trace(self, data: dict) -> Trace:
        """重建 Trace"""
        trace = Trace(
            trace_id=data["trace_id"],
            session_id=data.get("session_id", ""),
            user_message=data.get("user_message", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            ended_at=data.get("ended_at"),
            total_duration_ms=data.get("total_duration_ms", 0),
            total_llm_calls=data.get("total_llm_calls", 0),
            total_tool_calls=data.get("total_tool_calls", 0),
            total_tokens=data.get("total_tokens", 0),
            total_cost=data.get("total_cost", 0),
            status=SpanStatus(data.get("status", "ok")),
            error_message=data.get("error_message", ""),
            metadata=data.get("metadata", {}),
        )

        # 重建 Spans
        for span_data in data.get("spans", []):
            trace.add_span(self._reconstruct_span(span_data))

        return trace

    def _reconstruct_span(self, data: dict) -> Span:
        """重建 Span"""
        return Span(
            span_id=data["span_id"],
            trace_id=data["trace_id"],
            parent_id=data.get("parent_id"),
            name=data.get("name", ""),
            span_type=SpanType[data.get("type", "ACTION")],
            start_time=data.get("start_time", datetime.now().isoformat()),
            end_time=data.get("end_time"),
            duration_ms=data.get("duration_ms", 0),
            status=SpanStatus(data.get("status", "ok")),
            error_message=data.get("error_message", ""),
            input=data.get("input"),
            output=data.get("output"),
            metadata=data.get("metadata", {}),
        )

    def _save_trace(self, trace: Trace) -> None:
        """保存追踪到磁盘"""
        if not self.storage_path:
            return

        path = self.storage_path / f"{trace.trace_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(trace.to_dict(), f, ensure_ascii=False, indent=2)

    # ==================== 分析方法 ====================

    def analyze_trace(self, trace: Trace) -> dict:
        """
        分析追踪

        Returns:
            分析报告
        """
        # 收集所有 Span
        all_spans = self._flatten_spans(trace.spans)

        # 计算统计
        total_duration = sum(s.duration_ms for s in all_spans)
        llm_spans = [s for s in all_spans if s.span_type == SpanType.LLM_CALL]
        tool_spans = [s for s in all_spans if s.span_type == SpanType.TOOL_CALL]

        # 找出最慢的操作
        slowest = sorted(all_spans, key=lambda s: -s.duration_ms)[:5]

        # 找出失败的步骤
        errors = [s for s in all_spans if s.status == SpanStatus.ERROR]

        return {
            "trace_id": trace.trace_id,
            "session_id": trace.session_id,
            "total_duration_ms": trace.total_duration_ms,
            "total_spans": len(all_spans),
            "llm_calls": len(llm_spans),
            "tool_calls": len(tool_spans),
            "total_tokens": trace.total_tokens,
            "llm_duration_ms": sum(s.duration_ms for s in llm_spans),
            "tool_duration_ms": sum(s.duration_ms for s in tool_spans),
            "slowest_operations": [
                {"name": s.name, "duration_ms": s.duration_ms, "type": s.span_type.name}
                for s in slowest
            ],
            "errors": [
                {"name": s.name, "error": s.error_message}
                for s in errors
            ],
            "status": trace.status.value,
        }

    def _flatten_spans(self, spans: list[Span]) -> list[Span]:
        """展开所有 Span（包含子 Span）"""
        result = []
        for span in spans:
            result.append(span)
            if span.children:
                result.extend(self._flatten_spans(span.children))
        return result

    # ==================== 报告生成 ====================

    def generate_report(self, trace: Trace) -> str:
        """生成追踪报告"""
        analysis = self.analyze_trace(trace)

        lines = [
            "=" * 60,
            "🔍 执行链路追踪报告",
            "=" * 60,
            f"Trace ID:    {trace.trace_id}",
            f"Session ID:  {trace.session_id}",
            f"状态:        {trace.status.value.upper()}",
            "-" * 60,
            "📊 性能统计:",
            f"  总耗时:     {trace.total_duration_ms:.2f} ms",
            f"  LLM 调用:   {analysis['llm_calls']} 次 ({analysis['llm_duration_ms']:.2f} ms)",
            f"  工具调用:   {analysis['tool_calls']} 次 ({analysis['tool_duration_ms']:.2f} ms)",
            f"  Token 消耗: {trace.total_tokens:,}",
            "-" * 60,
            "🐢 最慢操作:",
        ]

        for i, op in enumerate(analysis["slowest_operations"], 1):
            lines.append(f"  {i}. {op['name']} ({op['type']}): {op['duration_ms']:.2f} ms")

        if analysis["errors"]:
            lines.append("-" * 60)
            lines.append("❌ 错误列表:")
            for err in analysis["errors"]:
                lines.append(f"  - {err['name']}: {err['error']}")

        lines.append("=" * 60)

        return "\n".join(lines)


# ==================== OpenTelemetry 兼容 ====================

class OpenTelemetryExporter:
    """
    OpenTelemetry 格式导出器

    导出追踪数据到支持 OpenTelemetry 的追踪系统。
    """

    def __init__(self, service_name: str = "openclaw-agent"):
        self.service_name = service_name

    def export(self, trace: Trace) -> dict:
        """
        导出为 OpenTelemetry 格式

        Returns:
            OpenTelemetry 格式的追踪数据
        """
        spans = []
        for span in trace.spans:
            spans.append(self._convert_span(span))

        return {
            "resourceSpans": [{
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": self.service_name}},
                        {"key": "session.id", "value": {"stringValue": trace.session_id}},
                    ]
                },
                "scopeSpans": [{
                    "spans": spans
                }]
            }]
        }

    def _convert_span(self, span: Span) -> dict:
        """转换单个 Span"""
        return {
            "traceId": span.trace_id,
            "spanId": span.span_id,
            "parentSpanId": span.parent_id or "",
            "name": span.name,
            "kind": span.span_type.name,
            "startTimeUnixNano": self._to_nano(span.start_time),
            "endTimeUnixNano": self._to_nano(span.end_time) if span.end_time else 0,
            "status": {
                "code": 1 if span.status == SpanStatus.ERROR else 0,
                "message": span.error_message,
            },
            "attributes": [
                {"key": "span.type", "value": {"stringValue": span.span_type.name}},
                {"key": "duration_ms", "value": {"doubleValue": span.duration_ms}},
            ],
        }

    def _to_nano(self, iso_time: str) -> int:
        """转换为纳秒时间戳"""
        try:
            dt = datetime.fromisoformat(iso_time)
            return int(dt.timestamp() * 1_000_000_000)
        except (ValueError, TypeError):
            return 0
