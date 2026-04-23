# harness/provider/claude.py
# Claude API Provider 实现

import json
from typing import Optional

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from .base import BaseProvider, LLMResponse, ToolCall, Usage


class ClaudeProvider(BaseProvider):
    """Anthropic Claude API Provider"""
    
    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-4-5",
        base_url: str = None,
        thinking_enabled: bool = False,
        thinking_budget_tokens: int = 10000,
    ):
        """
        初始化 Claude Provider
        
        Args:
            api_key: Anthropic API Key
            model: 模型名称（claude-opus-4-5 / claude-sonnet-4-5 / claude-haiku-4）
            base_url: 可选的代理地址
            thinking_enabled: 是否启用 Extended Thinking
            thinking_budget_tokens: thinking 模式的 token 预算
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "请安装 anthropic 包: pip install anthropic"
            )
        
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model
        self.thinking_enabled = thinking_enabled
        self.thinking_budget_tokens = thinking_budget_tokens
    
    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] = None,
        max_tokens: int = 8192,
        temperature: float = 0.0,
        **kwargs,
    ) -> LLMResponse:
        """调用 Claude API 获取响应"""
        # 分离 system prompt
        system = ""
        filtered_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                filtered_messages.append(self._normalize_message(msg))
        
        # 构建请求参数
        params = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": filtered_messages,
            "temperature": temperature,
        }
        
        if system:
            params["system"] = system
        
        if tools:
            params["tools"] = self._format_tools(tools)
        
        # Extended Thinking 支持
        if self.thinking_enabled:
            params["thinking"] = {
                "type": "enabled",
                "budget_tokens": self.thinking_budget_tokens,
            }
        
        response = await self.client.messages.create(**params)
        return self._parse_response(response)
    
    def _normalize_message(self, msg: dict) -> dict:
        """
        标准化消息格式以适配 Claude API
        Claude 不支持 role=tool 的独立消息，工具结果需要嵌入 user 消息
        """
        normalized = {"role": msg["role"], "content": msg["content"]}
        return normalized
    
    def _format_tools(self, tools: list[dict]) -> list[dict]:
        """将通用工具定义转换为 Claude 格式"""
        claude_tools = []
        for tool in tools:
            claude_tools.append({
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
            })
        return claude_tools
    
    def _parse_response(self, response) -> LLMResponse:
        """解析 Claude 响应为统一格式"""
        content = ""
        tool_calls = []
        
        # 处理 thinking block（如果存在）
        thinking_content = ""
        for block in response.content:
            if block.type == "thinking":
                thinking_content = block.thinking
            elif block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    args=block.input if isinstance(block.input, dict) else {},
                ))
        
        # 如果有 thinking 内容，添加到 content 前面
        if thinking_content:
            content = f"[慢思考过程]\n{thinking_content}\n\n[最终回答]\n{content}"
        
        usage = None
        if response.usage:
            usage = Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
        
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=usage,
            stop_reason=response.stop_reason,
            raw=response,
        )
    
    def format_tool_result(self, tool_call_id: str, content: str) -> dict:
        """Claude 工具结果格式"""
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": content,
                }
            ],
        }
    
    def to_assistant_message(self, response: LLMResponse) -> dict:
        """Claude assistant 消息格式（包含 tool_use block）"""
        content_blocks = []
        if response.content:
            content_blocks.append({"type": "text", "text": response.content})
        for call in response.tool_calls:
            content_blocks.append({
                "type": "tool_use",
                "id": call.id,
                "name": call.name,
                "input": call.args,
            })
        return {"role": "assistant", "content": content_blocks}
    
    def supports_thinking(self) -> bool:
        """Claude 支持 Extended Thinking"""
        return True
