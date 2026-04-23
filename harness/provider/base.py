# harness/provider/base.py
# Provider 抽象基类 - 定义统一的 LLM 接口契约

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class ToolCall:
    """工具调用请求"""
    id: str
    name: str
    args: dict


@dataclass
class Usage:
    """Token 使用统计"""
    input_tokens: int
    output_tokens: int
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LLMResponse:
    """统一的 LLM 响应格式"""
    content: str                          # 文本内容
    tool_calls: list[ToolCall]            # 工具调用请求（可为空）
    usage: Optional[Usage] = None         # Token 消耗
    stop_reason: str = "end_turn"        # 停止原因
    raw: Any = None                      # 原始响应（调试用）
    
    def to_assistant_message(self) -> dict:
        """转换为 messages 数组中的 assistant 消息"""
        raise NotImplementedError


class BaseProvider(ABC):
    """LLM Provider 抽象基类"""
    
    @abstractmethod
    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] = None,
        max_tokens: int = 8192,
        temperature: float = 0.0,
        **kwargs,
    ) -> LLMResponse:
        """
        调用 LLM 获取响应
        
        Args:
            messages: 对话历史（统一格式）
            tools: 工具定义列表
            max_tokens: 最大输出 Token 数
            temperature: 采样温度
            
        Returns:
            统一格式的 LLMResponse
        """
        ...
    
    @abstractmethod
    def format_tool_result(
        self,
        tool_call_id: str,
        content: str,
    ) -> dict:
        """
        将工具执行结果格式化为 messages 中的消息
        不同 API 的 tool result 格式不同
        """
        ...
    
    @abstractmethod
    def to_assistant_message(self, response: LLMResponse) -> dict:
        """将 LLMResponse 转换为 assistant 消息格式"""
        ...
    
    def supports_thinking(self) -> bool:
        """
        是否支持 Extended Thinking 模式
        重写此方法以支持 Claude 的 thinking 扩展
        """
        return False
