# harness/tools/base.py
# 工具基类定义

from dataclasses import dataclass
from typing import Callable, Any, Optional
import inspect
import json


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str                    # 工具名称（唯一标识）
    description: str             # 功能描述（LLM 用于决策）
    parameters: dict             # JSON Schema 格式的参数定义
    handler: Callable            # 实际执行函数（同步或异步）
    category: str = "general"   # 工具分类（用于分组管理）
    examples: list[str] = None   # 使用示例（帮助 LLM 理解）
    
    def __post_init__(self):
        if self.examples is None:
            self.examples = []
    
    def to_llm_schema(self) -> dict:
        """转换为 LLM 可理解的工具描述格式"""
        schema = {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
        if self.examples:
            schema["examples"] = self.examples
        return schema


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    content: str
    error: Optional[str] = None
    
    @classmethod
    def ok(cls, content: str) -> "ToolResult":
        return cls(success=True, content=content)
    
    @classmethod
    def fail(cls, error: str) -> "ToolResult":
        return cls(success=False, content=f"错误: {error}", error=error)


def infer_schema(fn: Callable) -> dict:
    """
    从函数签名自动推断 JSON Schema
    
    Usage:
        schema = infer_schema(my_function)
    """
    sig = inspect.signature(fn)
    hints = fn.__annotations__
    
    properties = {}
    required = []
    
    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        
        # 类型映射
        type_hint = hints.get(param_name, str)
        json_type = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }.get(type_hint, "string")
        
        prop = {"type": json_type}
        
        # 添加描述（从 docstring 提取）
        if fn.__doc__:
            # 简单的描述提取，可以改进
            pass
        
        properties[param_name] = prop
        
        # 没有默认值 → 必填
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
        else:
            # 有默认值，添加 default
            properties[param_name]["default"] = param.default
    
    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }
