# harness/provider/openai_compat.py
# OpenAI 兼容 API Provider 实现

import json
from typing import Optional

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from .base import BaseProvider, LLMResponse, ToolCall, Usage


class OpenAICompatProvider(BaseProvider):
    """
    OpenAI 兼容 API Provider
    
    支持：OpenAI、豆包（ByteDance）、Qwen（阿里云）、
          DeepSeek、Moonshot、智谱 GLM 等
    """
    
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        **kwargs,
    ):
        """
        初始化 OpenAI 兼容 Provider
        
        Args:
            api_key: API Key
            model: 模型名称
            base_url: API 基础地址
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "请安装 openai 包: pip install openai"
            )
        
        # 构建客户端参数
        client_kwargs = {
            "api_key": api_key,
            "base_url": base_url,
        }
        self.client = AsyncOpenAI(**client_kwargs)
        self.model = model
    
    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] = None,
        max_tokens: int = 8192,
        temperature: float = 0.0,
        **kwargs,
    ) -> LLMResponse:
        """调用 OpenAI 兼容 API 获取响应"""
        params = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,  # OpenAI 格式直接接受 system 消息
        }
        
        if tools:
            params["tools"] = self._format_tools(tools)
            params["tool_choice"] = "auto"
        
        # 支持额外参数
        for key, value in kwargs.items():
            if key not in params:
                params[key] = value
        
        response = await self.client.chat.completions.create(**params)
        return self._parse_response(response)
    
    def _format_tools(self, tools: list[dict]) -> list[dict]:
        """OpenAI 工具格式"""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                }
            }
            for tool in tools
        ]
    
    def _parse_response(self, response) -> LLMResponse:
        """解析 OpenAI 格式响应"""
        message = response.choices[0].message
        
        tool_calls = []
        if message.tool_calls:
            for call in message.tool_calls:
                try:
                    args = json.loads(call.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(
                    id=call.id,
                    name=call.function.name,
                    args=args,
                ))
        
        usage = None
        if response.usage:
            usage = Usage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )
        
        return LLMResponse(
            content=message.content or "",
            tool_calls=tool_calls,
            usage=usage,
            stop_reason=response.choices[0].finish_reason,
            raw=response,
        )
    
    def format_tool_result(self, tool_call_id: str, content: str) -> dict:
        """OpenAI 工具结果格式"""
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        }
    
    def to_assistant_message(self, response: LLMResponse) -> dict:
        """OpenAI assistant 消息格式"""
        message = {"role": "assistant", "content": response.content}
        if response.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.args, ensure_ascii=False),
                    }
                }
                for call in response.tool_calls
            ]
        return message


class DoubaoProvider(OpenAICompatProvider):
    """豆包（ByteDance）Provider - 预配置"""
    
    def __init__(
        self,
        api_key: str,
        model: str = "doubao-pro-32k",
    ):
        super().__init__(
            api_key=api_key,
            model=model,
            base_url="https://ark.cn-beijing.volces.com/api/v3",
        )


class QwenProvider(OpenAICompatProvider):
    """通义千问（阿里云）Provider - 预配置"""
    
    def __init__(
        self,
        api_key: str,
        model: str = "qwen-max",
    ):
        super().__init__(
            api_key=api_key,
            model=model,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )


class DeepSeekProvider(OpenAICompatProvider):
    """DeepSeek Provider - 预配置"""
    
    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
    ):
        super().__init__(
            api_key=api_key,
            model=model,
            base_url="https://api.deepseek.com",
        )


class VolcenginePlanProvider(OpenAICompatProvider):
    """
    火山引擎 Coding Plan Provider - 预配置
    
    Coding Plan 是字节跳动推出的 AI 编程订阅套餐，
    支持多种模型（豆包 Seed Code、GLM-4、Kimi 等）。
    
    API Key 获取: https://console.volces.com/
    文档: https://www.volcengine.com/docs/82379/1928261
    
    支持的模型:
        - ark-code-latest (默认)
        - doubao-seed-code
        - glm-4.7
        - kimi-k2-thinking
        - kimi-k2.5
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "ark-code-latest",
    ):
        super().__init__(
            api_key=api_key,
            model=model,  # 直接使用模型名称，Coding Plan 会自动路由
            base_url="https://ark.cn-beijing.volces.com/api/coding/v3",
        )
