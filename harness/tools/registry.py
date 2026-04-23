# harness/tools/registry.py
# 工具注册表 - 动态注册、分发、并发执行

import asyncio
import inspect
import logging
from typing import Any, Callable, Optional
from functools import wraps

from .base import ToolDefinition, infer_schema

logger = logging.getLogger(__name__)


class ToolNotFoundError(Exception):
    """工具不存在"""
    pass


class ToolArgumentError(Exception):
    """工具参数错误"""
    pass


class ToolExecutionError(Exception):
    """工具执行失败"""
    pass


class ToolRegistry:
    """
    工具注册表
    
    支持：
    - 装饰器注册
    - 动态注册
    - 分类管理
    - 并发执行
    """

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    # ── 注册方式一：装饰器 ─────────────────────────────────────

    def tool(
        self,
        name: str = None,
        description: str = None,
        category: str = "general",
        examples: list[str] = None,
    ):
        """
        装饰器：将函数注册为工具
        
        Usage:
            @registry.tool(description="读取文件内容")
            async def read_file(path: str) -> str:
                with open(path) as f:
                    return f.read()
        """
        def decorator(fn: Callable) -> Callable:
            tool_name = name or fn.__name__
            tool_desc = description or (fn.__doc__ or "").strip().split("\n")[0]
            schema = infer_schema(fn)
            
            self.register(ToolDefinition(
                name=tool_name,
                description=tool_desc,
                parameters=schema,
                handler=fn,
                category=category,
                examples=examples or [],
            ))
            return fn
        return decorator

    # ── 注册方式二：动态注册 ───────────────────────────────────

    def register(self, tool: ToolDefinition):
        """动态注册工具"""
        if tool.name in self._tools:
            logger.warning(f"覆盖已存在的工具: {tool.name}")
        self._tools[tool.name] = tool
        logger.info(f"注册工具: {tool.name} [{tool.category}]")

    def unregister(self, name: str) -> bool:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"注销工具: {name}")
            return True
        return False

    # ── 查询 ─────────────────────────────────────────────────

    def get(self, name: str) -> Optional[ToolDefinition]:
        """获取工具定义"""
        return self._tools.get(name)

    def get_definitions(self, category: str = None) -> list[dict]:
        """
        获取工具定义列表（传给 LLM 的格式）
        
        Args:
            category: 如果指定，只返回该分类的工具
        """
        tools = self._tools.values()
        if category:
            tools = [t for t in tools if t.category == category]
        return [t.to_llm_schema() for t in tools]

    def list_tools(self) -> list[str]:
        """列出所有工具名称"""
        return list(self._tools.keys())
    
    def list_by_category(self) -> dict[str, list[str]]:
        """按分类列出所有工具"""
        result = {}
        for tool in self._tools.values():
            if tool.category not in result:
                result[tool.category] = []
            result[tool.category].append(tool.name)
        return result

    # ── 分发执行 ─────────────────────────────────────────────

    async def dispatch(self, name: str, args: dict) -> Any:
        """
        根据名称分发并执行工具
        
        Args:
            name: 工具名称
            args: 工具参数（来自 LLM 的 tool_call.args）
            
        Returns:
            工具执行结果（字符串或可序列化对象）
        """
        if name not in self._tools:
            available = ", ".join(self.list_tools())
            raise ToolNotFoundError(
                f"工具 '{name}' 不存在。可用工具: {available}"
            )

        tool = self._tools[name]

        try:
            # 过滤掉不存在的参数
            valid_args = {k: v for k, v in args.items() if k in tool.parameters.get("properties", {})}
            
            # 支持同步和异步函数
            if inspect.iscoroutinefunction(tool.handler):
                result = await tool.handler(**valid_args)
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: tool.handler(**valid_args)
                )
            return result

        except TypeError as e:
            raise ToolArgumentError(f"工具 '{name}' 参数错误: {e}")
        except Exception as e:
            logger.error(f"工具 '{name}' 执行失败: {e}", exc_info=True)
            raise ToolExecutionError(f"工具 '{name}' 执行失败: {e}")
    
    async def dispatch_safe(self, name: str, args: dict) -> tuple[bool, Any]:
        """
        安全分发执行（捕获所有异常）
        
        Returns:
            (success, result_or_error)
        """
        try:
            result = await self.dispatch(name, args)
            return True, result
        except Exception as e:
            return False, str(e)

    # ── 批量执行 ─────────────────────────────────────────────

    async def dispatch_parallel(
        self,
        calls: list[tuple[str, dict]],
        max_concurrent: int = 10,
    ) -> list[tuple[bool, Any]]:
        """
        并发执行多个工具调用
        
        Args:
            calls: [(tool_name, args), ...] 的列表
            max_concurrent: 最大并发数
            
        Returns:
            [(success, result_or_error), ...]
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def dispatch_with_limit(name: str, args: dict):
            async with semaphore:
                return await self.dispatch_safe(name, args)
        
        tasks = [dispatch_with_limit(name, args) for name, args in calls]
        return await asyncio.gather(*tasks)

    # ── 工具组 ───────────────────────────────────────────────

    def create_group(self, name: str, tool_names: list[str]) -> "ToolGroup":
        """创建工具组"""
        return ToolGroup(self, name, tool_names)


class ToolGroup:
    """工具组 - 一组相关工具的组合"""

    def __init__(self, registry: ToolRegistry, name: str, tool_names: list[str]):
        self.registry = registry
        self.name = name
        self.tool_names = tool_names

    def get_definitions(self) -> list[dict]:
        """获取组内所有工具的定义"""
        return [
            self.registry.get(name).to_llm_schema()
            for name in self.tool_names
            if self.registry.get(name)
        ]

    async def dispatch(self, name: str, args: dict) -> Any:
        """分发执行（只允许组内工具）"""
        if name not in self.tool_names:
            raise ToolNotFoundError(f"工具 '{name}' 不在组 '{self.name}' 中")
        return await self.registry.dispatch(name, args)
