"""
Message - 消息类型定义

定义 Agent 对话中使用的消息结构。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any


class MessageRole(str, Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    DEVELOPER = "developer"

    # 兼容性别名
    HUMAN = "human"
    AI = "assistant"


@dataclass
class Message:
    """
    通用消息结构

    用于表示 Agent 对话中的单条消息。
    """
    role: str | MessageRole
    content: str | None = None
    name: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        # 确保 role 是字符串
        if isinstance(self.role, MessageRole):
            self.role = self.role.value

    @classmethod
    def user(cls, content: str, **kwargs) -> Message:
        """创建用户消息"""
        return cls(role=MessageRole.USER, content=content, **kwargs)

    @classmethod
    def assistant(cls, content: str, **kwargs) -> Message:
        """创建助手消息"""
        return cls(role=MessageRole.ASSISTANT, content=content, **kwargs)

    @classmethod
    def system(cls, content: str, **kwargs) -> Message:
        """创建系统消息"""
        return cls(role=MessageRole.SYSTEM, content=content, **kwargs)

    @classmethod
    def tool(cls, content: str, tool_call_id: str, tool_name: str | None = None, **kwargs) -> Message:
        """创建工具结果消息"""
        return cls(
            role=MessageRole.TOOL,
            content=content,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            **kwargs
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            "role": self.role,
            "content": self.content,
        }
        if self.name:
            result["name"] = self.name
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        if self.tool_name:
            result["name"] = self.tool_name
        return result

    def to_openai_format(self) -> dict:
        """转换为 OpenAI API 格式"""
        return self.to_dict()

    def to_anthropic_format(self) -> dict:
        """转换为 Anthropic API 格式"""
        result = {
            "role": self.role,
            "content": self.content,
        }
        if self.name:
            result["author"] = self.name
        return result

    @classmethod
    def from_dict(cls, data: dict) -> Message:
        """从字典创建"""
        return cls(
            role=data.get("role", "assistant"),
            content=data.get("content"),
            name=data.get("name"),
            tool_call_id=data.get("tool_call_id"),
            tool_name=data.get("tool_name"),
            metadata=data.get("metadata", {}),
        )

    def __str__(self) -> str:
        role_display = self.role.upper()
        content_preview = (self.content or "")[:50]
        if len(self.content or "") > 50:
            content_preview += "..."
        return f"[{role_display}] {content_preview}"


@dataclass
class ToolCall:
    """工具调用"""
    id: str
    name: str
    arguments: dict[str, Any]
    result: Any = None
    error: str | None = None
    duration_ms: float | None = None

    @classmethod
    def from_message(cls, msg: Message) -> ToolCall | None:
        """从消息中提取工具调用"""
        if msg.role != MessageRole.TOOL:
            return None

        return cls(
            id=msg.tool_call_id or msg.metadata.get("tool_call_id", ""),
            name=msg.tool_name or msg.metadata.get("tool_name", "unknown"),
            arguments=json.loads(msg.content) if msg.content else {},
            result=msg.content,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


@dataclass
class Conversation:
    """
    对话上下文

    管理一组消息和元数据。
    """
    id: str | None = None
    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add(self, message: Message) -> None:
        """添加消息"""
        self.messages.append(message)
        self.updated_at = datetime.now()

    def add_user(self, content: str, **kwargs) -> Message:
        """添加用户消息"""
        msg = Message.user(content, **kwargs)
        self.add(msg)
        return msg

    def add_assistant(self, content: str, **kwargs) -> Message:
        """添加助手消息"""
        msg = Message.assistant(content, **kwargs)
        self.add(msg)
        return msg

    def add_system(self, content: str, **kwargs) -> Message:
        """添加系统消息"""
        msg = Message.system(content, **kwargs)
        self.add(msg)
        return msg

    def add_tool(self, content: str, tool_call_id: str, tool_name: str | None = None, **kwargs) -> Message:
        """添加工具结果消息"""
        msg = Message.tool(content, tool_call_id, tool_name, **kwargs)
        self.add(msg)
        return msg

    def get_recent(self, n: int = 10) -> list[Message]:
        """获取最近 N 条消息"""
        return self.messages[-n:]

    def count_tokens(self, counter=None) -> int:
        """估算 Token 数量"""
        if counter is None:
            # 简单估算
            total = 0
            for msg in self.messages:
                total += len(msg.content or "") // 4
            return total

        return sum(counter.count(msg.content or "") for msg in self.messages)

    def clear(self) -> None:
        """清空消息"""
        self.messages.clear()
        self.updated_at = datetime.now()

    def to_list(self) -> list[dict]:
        """转换为列表格式"""
        return [msg.to_dict() for msg in self.messages]

    @classmethod
    def from_list(cls, data: list[dict]) -> Conversation:
        """从列表创建"""
        conv = cls()
        for item in data:
            conv.add(Message.from_dict(item))
        return conv


__all__ = [
    "Message",
    "MessageRole",
    "ToolCall",
    "Conversation",
]
