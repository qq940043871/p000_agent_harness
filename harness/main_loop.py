# harness/main_loop.py
# Agent Main Loop - 核心心脏

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Any, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class LoopStatus(Enum):
    """Main Loop 执行状态"""
    RUNNING = "running"
    COMPLETED = "completed"
    MAX_TURNS_REACHED = "max_turns_reached"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class LoopStats:
    """Main Loop 执行统计"""
    turns: int = 0
    total_tokens: int = 0
    tool_calls: int = 0
    start_time: float = field(default_factory=time.time)
    error_count: int = 0
    
    @property
    def elapsed(self) -> float:
        """已执行时间（秒）"""
        return time.time() - self.start_time
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "turns": self.turns,
            "total_tokens": self.total_tokens,
            "tool_calls": self.tool_calls,
            "elapsed_seconds": round(self.elapsed, 2),
            "error_count": self.error_count,
        }


@dataclass
class LoopResult:
    """Main Loop 执行结果"""
    status: LoopStatus
    content: str
    stats: LoopStats
    error: Optional[Exception] = None
    
    def is_success(self) -> bool:
        """是否成功完成"""
        return self.status == LoopStatus.COMPLETED


@dataclass
class TurnResult:
    """单轮执行结果"""
    turn: int
    response: Any
    tool_results: list[dict]
    elapsed: float


class MainLoop:
    """
    OpenClaw Agent Main Loop
    
    驱动 Agent 的 Think → Act → Observe 循环
    """

    def __init__(
        self,
        provider,
        tool_registry,
        system_prompt: str = "",
        max_turns: int = 50,
        max_tokens_per_turn: int = 8192,
        token_budget: int = None,
        on_turn_complete: Callable[[TurnResult], None] = None,
        on_loop_complete: Callable[[LoopResult], None] = None,
        cost_tracker=None,
        tracer=None,
    ):
        """
        初始化 Main Loop
        
        Args:
            provider: LLM Provider 实例
            tool_registry: 工具注册表
            system_prompt: 系统提示词
            max_turns: 最大执行轮次
            max_tokens_per_turn: 每轮最大输出 Token 数
            token_budget: Token 预算上限（超过则强制终止）
            on_turn_complete: 每轮完成后的回调
            on_loop_complete: 循环完成后的回调
            cost_tracker: 成本追踪器（可选）
            tracer: 链路追踪器（可选）
        """
        self.provider = provider
        self.tools = tool_registry
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.max_tokens_per_turn = max_tokens_per_turn
        self.token_budget = token_budget
        self.on_turn_complete = on_turn_complete
        self.on_loop_complete = on_loop_complete
        self.cost_tracker = cost_tracker
        self.tracer = tracer
        
        # 事件系统
        self._event_handlers: dict[str, list[Callable]] = {}
    
    def on(self, event: str, handler: Callable):
        """注册事件处理器"""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)
        return self  # 支持链式调用
    
    def off(self, event: str, handler: Callable = None):
        """注销事件处理器"""
        if event not in self._event_handlers:
            return
        if handler is None:
            self._event_handlers[event] = []
        else:
            self._event_handlers[event] = [
                h for h in self._event_handlers[event] if h != handler
            ]
    
    def _emit(self, event: str, *args, **kwargs):
        """触发事件"""
        for handler in self._event_handlers.get(event, []):
            try:
                handler(*args, **kwargs)
            except Exception as e:
                logger.error(f"事件处理器 {event} 执行失败: {e}")

    async def run(self, user_message: str) -> LoopResult:
        """
        执行完整的 Agent 任务
        
        Args:
            user_message: 用户输入
            
        Returns:
            LoopResult 包含最终回答和执行统计
        """
        stats = LoopStats()
        messages = self._init_messages(user_message)
        
        try:
            for turn in range(self.max_turns):
                stats.turns = turn + 1
                logger.info(f"[Turn {stats.turns}] 开始推理...")
                
                turn_start = time.time()
                
                # ── Think：调用 LLM ──────────────────────────────
                response = await self.provider.complete(
                    messages=messages,
                    tools=self.tools.get_definitions(),
                    max_tokens=self.max_tokens_per_turn,
                )
                
                # 更新 Token 统计
                if response.usage:
                    stats.total_tokens += response.usage.total_tokens
                    # 计算费用
                    cost = 0.0
                    if self.cost_tracker:
                        self.cost_tracker.record_usage(
                            model=self.provider.model if hasattr(self.provider, 'model') else "unknown",
                            prompt_tokens=response.usage.input_tokens or 0,
                            completion_tokens=response.usage.output_tokens or 0,
                        )
                        cost = self.cost_tracker.get_total_cost()
                    # 触发 token 更新事件
                    self._emit("token_update",
                        prompt_tokens=response.usage.input_tokens or 0,
                        completion_tokens=response.usage.output_tokens or 0,
                        cost=cost,
                        total_tokens=response.usage.total_tokens or 0,
                    )
                
                # 检查 Token 预算
                if self.token_budget and stats.total_tokens > self.token_budget:
                    logger.warning(f"Token 预算超限: {stats.total_tokens} > {self.token_budget}")
                    return LoopResult(
                        status=LoopStatus.MAX_TURNS_REACHED,
                        content=self._build_budget_exceeded_message(stats),
                        stats=stats,
                    )
                
                logger.info(
                    f"[Turn {stats.turns}] LLM 响应: "
                    f"tool_calls={len(response.tool_calls)}, "
                    f"tokens={getattr(response.usage, 'total_tokens', '?')}"
                )
                
                # ── 检查终止条件 ─────────────────────────────────
                if not response.tool_calls:
                    # 没有工具调用 → Agent 认为任务完成
                    logger.info(f"[Turn {stats.turns}] 任务完成，无更多工具调用")
                    
                    result = LoopResult(
                        status=LoopStatus.COMPLETED,
                        content=response.content or "",
                        stats=stats,
                    )
                    
                    if self.on_loop_complete:
                        self.on_loop_complete(result)
                    return result
                
                # ── Act：执行工具调用 ─────────────────────────────
                # 将 Assistant 消息追加到历史
                assistant_msg = self.provider.to_assistant_message(response)
                messages.append(assistant_msg)
                
                # 触发工具调用事件
                for call in response.tool_calls:
                    self._emit("tool_call",
                        tool_name=call.name,
                        arguments=str(call.args)
                    )
                
                # 并发执行所有工具
                tool_results = await self._execute_tools_parallel(response.tool_calls)
                stats.tool_calls += len(response.tool_calls)
                
                # 触发工具结果事件
                for call, result in zip(response.tool_calls, tool_results):
                    self._emit("tool_result",
                        tool_name=call.name,
                        result=result.get("content", "")
                    )
                
                # 记录失败的工具调用
                for r in tool_results:
                    if "error" in r.get("content", "").lower():
                        stats.error_count += 1
                
                # ── Observe：将工具结果追加到历史 ─────────────────
                messages.extend(tool_results)
                
                # 触发每轮完成回调
                turn_elapsed = time.time() - turn_start
                if self.on_turn_complete:
                    self.on_turn_complete(TurnResult(
                        turn=stats.turns,
                        response=response,
                        tool_results=tool_results,
                        elapsed=turn_elapsed,
                    ))
            
            # 超过最大轮次
            logger.warning(f"超过最大轮次限制 {self.max_turns}")
            result = LoopResult(
                status=LoopStatus.MAX_TURNS_REACHED,
                content="任务超过最大执行轮次，可能存在循环。",
                stats=stats,
            )
            if self.on_loop_complete:
                self.on_loop_complete(result)
            return result
        
        except Exception as e:
            logger.error(f"Main Loop 异常: {e}", exc_info=True)
            stats.error_count += 1
            result = LoopResult(
                status=LoopStatus.ERROR,
                content=str(e),
                stats=stats,
                error=e,
            )
            if self.on_loop_complete:
                self.on_loop_complete(result)
            return result
    
    def _init_messages(self, user_message: str) -> list:
        """初始化消息历史"""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": user_message})
        return messages
    
    async def _execute_tools_parallel(self, tool_calls) -> list:
        """
        并发执行多个工具调用
        
        注意：互相独立的工具调用可以并发执行以提升效率
        互相依赖的工具调用（如 A 的输出是 B 的输入）不能并发
        """
        tasks = [
            self._execute_single_tool(call)
            for call in tool_calls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        tool_messages = []
        for call, result in zip(tool_calls, results):
            if isinstance(result, Exception):
                content = f"工具执行失败: {result}"
                logger.error(f"工具 {call.name} 执行异常: {result}")
            else:
                content = str(result) if result is not None else ""
            
            tool_messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": content,
            })
        
        return tool_messages
    
    async def _execute_single_tool(self, call) -> Any:
        """执行单个工具调用"""
        logger.info(f"执行工具: {call.name}({call.args})")
        start = time.time()
        
        result = await self.tools.dispatch(call.name, call.args)
        
        elapsed = time.time() - start
        logger.info(f"工具 {call.name} 完成，耗时 {elapsed:.2f}s")
        return result
    
    def _build_budget_exceeded_message(self, stats: LoopStats) -> str:
        """生成 Token 预算超限消息"""
        return (
            f"任务因 Token 预算超限而终止。\n"
            f"已执行 {stats.turns} 轮，"
            f"消耗 {stats.total_tokens} tokens，"
            f"调用 {stats.tool_calls} 次工具。\n"
            f"请优化任务或增加 Token 预算。"
        )


class StatefulMainLoop(MainLoop):
    """
    有状态的 Main Loop - 维护跨任务对话历史
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.persistent_messages: list[dict] = []
    
    async def run(self, user_message: str) -> LoopResult:
        """执行任务，使用持久化的对话历史"""
        # 从持久历史开始，而不是空列表
        messages = self.persistent_messages.copy()
        messages.append({"role": "user", "content": user_message})
        
        # 保存当前用户消息（用于回滚）
        original_message_count = len(messages)
        
        try:
            for turn in range(self.max_turns):
                stats = LoopStats(turns=turn + 1)
                
                response = await self.provider.complete(
                    messages=messages,
                    tools=self.tools.get_definitions(),
                    max_tokens=self.max_tokens_per_turn,
                )
                
                if response.usage:
                    stats.total_tokens = response.usage.total_tokens
                
                # 检查终止
                if not response.tool_calls:
                    # 追加成功的消息到持久历史
                    messages.append({"role": "user", "content": user_message})
                    messages.append(self.provider.to_assistant_message(response))
                    if response.content:
                        messages.append({"role": "assistant", "content": response.content})
                    self.persistent_messages = messages
                    return LoopResult(
                        status=LoopStatus.COMPLETED,
                        content=response.content or "",
                        stats=stats,
                    )
                
                # 执行工具
                messages.append(self.provider.to_assistant_message(response))
                tool_results = await self._execute_tools_parallel(response.tool_calls)
                messages.extend(tool_results)
            
            return LoopResult(
                status=LoopStatus.MAX_TURNS_REACHED,
                content="任务超过最大执行轮次",
                stats=LoopStats(turns=self.max_turns),
            )
        
        except Exception as e:
            # 出错时回滚到原始消息数
            self.persistent_messages = self.persistent_messages[:original_message_count]
            raise
