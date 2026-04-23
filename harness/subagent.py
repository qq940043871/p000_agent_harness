"""
Subagent - 任务委派与隔离系统

功能：
- Subagent 创建与生命周期管理
- 上下文隔离与消息传递
- 任务委派协议
- 结果聚合与超时处理
"""

from __future__ import annotations

import asyncio
import copy
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Protocol
from uuid import uuid4


class SubagentState(Enum):
    """Subagent 状态"""
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class DelegatedTask:
    """委派任务"""
    id: str
    task_type: str  # "exploration", "debugging", "refactor", "analysis"
    description: str
    context: dict  # 传递给 Subagent 的上下文

    # 约束条件
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_seconds: int = 300
    max_cost: float = 10.0  # 最大成本预算

    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    parent_id: str | None = None
    dependencies: list[str] = field(default_factory=list)


@dataclass
class SubagentResult:
    """Subagent 执行结果"""
    task_id: str
    subagent_id: str
    state: SubagentState

    # 执行数据
    output: str = ""
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    commands_executed: list[str] = field(default_factory=list)

    # 指标
    duration_ms: float = 0.0
    cost: float = 0.0
    tokens_used: int = 0
    tool_calls: int = 0

    # 错误信息
    error: str = ""
    warnings: list[str] = field(default_factory=list)

    # 状态
    completed_at: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SubagentConfig:
    """Subagent 配置"""
    name: str = ""
    provider: str = "claude"
    model: str = "claude-sonnet-4-20250514"

    # 上下文隔离
    isolation_level: str = "strict"  # "strict", "shared", "merged"
    inherit_context: list[str] = field(default_factory=list)  # 继承的上下文键

    # 工具限制
    allowed_tools: list[str] | None = None  # None = 全部允许
    denied_tools: list[str] = field(default_factory=list)
    max_tool_calls: int = 50

    # 行为约束
    readonly_mode: bool = False
    allowed_dirs: list[str] = field(default_factory=list)  # 允许访问的目录
    denied_dirs: list[str] = field(default_factory=list)

    # 提示词定制
    system_prompt_addon: str = ""


class Subagent(Protocol):
    """Subagent 协议"""

    async def execute(self, task: DelegatedTask) -> SubagentResult: ...
    async def cancel(self) -> None: ...
    def get_state(self) -> SubagentState: ...


class BaseSubagent:
    """
    Subagent 基类

    提供通用的 Subagent 功能，子类可以覆盖特定行为。
    """

    def __init__(
        self,
        subagent_id: str,
        config: SubagentConfig,
        parent_loop: Any = None,
    ):
        self.id = subagent_id
        self.config = config
        self.parent_loop = parent_loop

        self._state = SubagentState.CREATED
        self._current_task: DelegatedTask | None = None
        self._start_time: float = 0
        self._result: SubagentResult | None = None

        # 隔离的上下文
        self._isolated_context: dict[str, Any] = {}

    @property
    def state(self) -> SubagentState:
        return self._state

    def _transition_to(self, new_state: SubagentState) -> None:
        """状态转换"""
        old_state = self._state
        self._state = new_state
        print(f"[Subagent {self.id}] {old_state.value} -> {new_state.value}")

    async def initialize(self, task: DelegatedTask) -> None:
        """初始化 Subagent"""
        self._transition_to(SubagentState.INITIALIZING)
        self._current_task = task
        self._isolated_context = self._build_isolated_context(task)
        self._transition_to(SubagentState.RUNNING)

    def _build_isolated_context(self, task: DelegatedTask) -> dict[str, Any]:
        """构建隔离上下文"""
        context = {
            "task_id": task.id,
            "task_type": task.task_type,
            "description": task.description,
            "parent_id": task.parent_id,
        }

        # 根据隔离级别处理上下文
        if self.config.isolation_level == "strict":
            # 严格隔离：只传递必要信息
            context.update({k: task.context.get(k) for k in ["goal", "constraints"] if k in task.context})

        elif self.config.isolation_level == "shared":
            # 共享模式：传递大部分上下文
            context.update(task.context)

        elif self.config.isolation_level == "merged":
            # 合并模式：传递上下文但可被覆盖
            context.update(task.context)
            context.update(self.config.inherit_context)

        return context

    def _filter_tools(self, available_tools: list[str]) -> list[str]:
        """过滤工具列表"""
        tools = set(available_tools)

        # 移除禁止的工具
        tools -= set(self.config.denied_tools)

        # 只保留允许的工具（如果有配置）
        if self.config.allowed_tools is not None:
            tools &= set(self.config.allowed_tools)

        return list(tools)

    def _check_path_access(self, path: str) -> bool:
        """检查路径访问权限"""
        # readonly 模式下禁止写操作
        if self.config.readonly_mode:
            return False

        # 检查允许列表
        if self.config.allowed_dirs:
            allowed = any(path.startswith(d) for d in self.config.allowed_dirs)
            if not allowed:
                return False

        # 检查禁止列表
        denied = any(path.startswith(d) for d in self.config.denied_dirs)
        if denied:
            return False

        return True

    async def execute(self, task: DelegatedTask) -> SubagentResult:
        """执行任务"""
        self._result = SubagentResult(
            task_id=task.id,
            subagent_id=self.id,
            state=SubagentState.RUNNING,
        )

        self._start_time = time.time()

        try:
            await self.initialize(task)

            # 执行实际任务（子类实现）
            self._result = await self._do_execute(task)

            # 检查超时
            if self._result.duration_ms > task.timeout_seconds * 1000:
                self._transition_to(SubagentState.TIMEOUT)
                self._result.state = SubagentState.TIMEOUT
            else:
                self._transition_to(SubagentState.COMPLETED)
                self._result.state = SubagentState.COMPLETED

        except asyncio.CancelledError:
            self._transition_to(SubagentState.CANCELLED)
            self._result.state = SubagentState.CANCELLED
            self._result.error = "Task cancelled"
            raise

        except Exception as e:
            self._transition_to(SubagentState.FAILED)
            self._result.state = SubagentState.FAILED
            self._result.error = str(e)

        finally:
            self._result.completed_at = datetime.now().isoformat()

        return self._result

    async def _do_execute(self, task: DelegatedTask) -> SubagentResult:
        """实际执行逻辑（子类覆盖）"""
        raise NotImplementedError

    async def cancel(self) -> None:
        """取消执行"""
        if self._state in (SubagentState.RUNNING, SubagentState.WAITING_APPROVAL):
            self._transition_to(SubagentState.CANCELLED)


class ExplorationSubagent(BaseSubagent):
    """探索型 Subagent - 用于文件探索和代码分析"""

    async def _do_execute(self, task: DelegatedTask) -> SubagentResult:
        """执行探索任务"""
        result = self._result
        goal = self._isolated_context.get("goal", "探索项目结构")

        # 模拟探索过程
        await asyncio.sleep(0.1)  # 实际会是真实的 Agent 调用

        result.output = f"探索完成: {goal}"
        result.files_created = []
        result.files_modified = []
        result.duration_ms = time.time() - self._start_time
        result.metadata = {
            "files_scanned": 0,
            "structure_analyzed": True,
        }

        return result


class DebuggingSubagent(BaseSubagent):
    """调试型 Subagent - 用于 Bug 定位和修复"""

    async def _do_execute(self, task: DelegatedTask) -> SubagentResult:
        """执行调试任务"""
        result = self._result
        error_info = task.context.get("error_info", "")
        target_file = task.context.get("target_file", "")

        result.output = f"调试完成: {target_file}"
        result.metadata = {
            "error_analyzed": error_info,
            "fix_applied": True,
        }

        return result


class SubagentPool:
    """
    Subagent 池 - 管理多个 Subagent 实例

    功能：
    - 并发执行多个 Subagent
    - 资源限制（最大并发数）
    - 任务队列管理
    """

    def __init__(
        self,
        max_concurrent: int = 3,
        default_config: SubagentConfig | None = None,
    ):
        self.max_concurrent = max_concurrent
        self.default_config = default_config or SubagentConfig()

        # 活跃的 Subagent
        self._active_subagents: dict[str, Subagent] = {}

        # 任务队列
        self._task_queue: asyncio.Queue[DelegatedTask] = asyncio.Queue()
        self._results: dict[str, SubagentResult] = {}

        # 统计
        self._total_executed = 0
        self._total_failed = 0

    def create_subagent(
        self,
        task_type: str,
        config: SubagentConfig | None = None,
    ) -> BaseSubagent:
        """创建 Subagent"""
        subagent_id = f"sub_{uuid4().hex[:8]}"
        cfg = config or copy.deepcopy(self.default_config)

        # 根据任务类型选择 Subagent
        if task_type == "exploration":
            subagent = ExplorationSubagent(subagent_id, cfg)
        elif task_type == "debugging":
            subagent = DebuggingSubagent(subagent_id, cfg)
        else:
            subagent = BaseSubagent(subagent_id, cfg)

        self._active_subagents[subagent_id] = subagent
        return subagent

    async def delegate_task(
        self,
        task: DelegatedTask,
        subagent_type: str = "base",
    ) -> SubagentResult:
        """委派任务"""
        subagent = self.create_subagent(subagent_type)
        return await subagent.execute(task)

    async def delegate_tasks_parallel(
        self,
        tasks: list[DelegatedTask],
        subagent_type: str = "base",
    ) -> list[SubagentResult]:
        """并行委派多个任务"""
        # 创建 Subagent
        subagents = [
            self.create_subagent(subagent_type)
            for _ in tasks
        ]

        # 并发执行
        results = await asyncio.gather(
            *[subagent.execute(task) for subagent, task in zip(subagents, tasks)],
            return_exceptions=True,
        )

        # 处理结果
        processed_results: list[SubagentResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # 创建错误结果
                error_result = SubagentResult(
                    task_id=tasks[i].id,
                    subagent_id=subagents[i].id,
                    state=SubagentState.FAILED,
                    error=str(result),
                )
                processed_results.append(error_result)
            else:
                processed_results.append(result)

        return processed_results

    async def delegate_with_dependencies(
        self,
        task_graph: dict[str, list[str]],  # task_id -> dependency_ids
        task_configs: dict[str, dict],  # task_id -> config
    ) -> dict[str, SubagentResult]:
        """
        按依赖顺序委派任务

        Args:
            task_graph: 任务依赖图
            task_configs: 任务配置
        """
        # 计算入度
        in_degree = {task_id: len(deps) for task_id, deps in task_graph.items()}
        ready_queue = [t for t, d in in_degree.items() if d == 0]

        results: dict[str, SubagentResult] = {}
        completed = set()

        while ready_queue:
            # 并行执行所有就绪任务
            batch_tasks = []
            for task_id in ready_queue:
                task = DelegatedTask(
                    id=task_id,
                    task_type=task_configs[task_id].get("type", "base"),
                    description=task_configs[task_id].get("description", ""),
                    context=task_configs[task_id].get("context", {}),
                    dependencies=list(task_graph[task_id]),
                )
                batch_tasks.append(task)

            # 执行批次
            batch_results = await self.delegate_tasks_parallel(batch_tasks)

            # 收集结果
            for task_id, result in zip(ready_queue, batch_results):
                results[task_id] = result
                completed.add(task_id)

                # 更新依赖
                for other_task, deps in task_graph.items():
                    if task_id in deps:
                        in_degree[other_task] -= 1
                        if in_degree[other_task] == 0:
                            ready_queue.append(other_task)

            # 移除已完成的
            ready_queue = [t for t in ready_queue if t not in completed]

        return results

    def cancel_all(self) -> None:
        """取消所有 Subagent"""
        for subagent in self._active_subagents.values():
            asyncio.create_task(subagent.cancel())

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "active_count": len([s for s in self._active_subagents.values()
                               if s.state == SubagentState.RUNNING]),
            "total_executed": self._total_executed,
            "total_failed": self._total_failed,
        }


class TaskCoordinator:
    """
    任务协调器 - 管理主 Agent 与 Subagent 之间的交互

    功能：
    - 任务分解
    - 结果聚合
    - 上下文回传
    """

    def __init__(self, pool: SubagentPool):
        self.pool = pool
        self._decomposition_rules: dict[str, Callable] = {}

    def register_decomposition(
        self,
        task_pattern: str,
        handler: Callable[[str], list[DelegatedTask]],
    ) -> None:
        """注册任务分解规则"""
        self._decomposition_rules[task_pattern] = handler

    def decompose_task(self, user_input: str) -> list[DelegatedTask]:
        """
        分解用户任务为子任务

        策略：
        1. 关键词匹配
        2. 语义相似度
        3. 规则模板
        """
        tasks = []

        # 探索类任务
        if any(kw in user_input for kw in ["探索", "分析", "查看", "列出"]):
            tasks.append(DelegatedTask(
                id=f"task_{uuid4().hex[:8]}",
                task_type="exploration",
                description=f"探索: {user_input}",
                context={"goal": user_input},
            ))

        # 调试类任务
        if any(kw in user_input for kw in ["修复", "Bug", "错误", "调试"]):
            tasks.append(DelegatedTask(
                id=f"task_{uuid4().hex[:8]}",
                task_type="debugging",
                description=f"调试: {user_input}",
                context={"error_info": user_input},
            ))

        # 默认回退
        if not tasks:
            tasks.append(DelegatedTask(
                id=f"task_{uuid4().hex[:8]}",
                task_type="base",
                description=user_input,
                context={"goal": user_input},
            ))

        return tasks

    async def coordinate(
        self,
        user_input: str,
        subagent_type: str = "base",
    ) -> dict[str, Any]:
        """协调执行"""
        # 分解任务
        sub_tasks = self.decompose_task(user_input)

        # 判断是否可以并行
        if len(sub_tasks) > 1:
            results = await self.pool.delegate_tasks_parallel(sub_tasks, subagent_type)
        else:
            results = [await self.pool.delegate_task(sub_tasks[0], subagent_type)]

        # 聚合结果
        return self.aggregate_results(results)

    def aggregate_results(self, results: list[SubagentResult]) -> dict[str, Any]:
        """聚合多个 Subagent 的结果"""
        # 收集所有输出
        outputs = [r.output for r in results if r.output]
        files_created = []
        files_modified = []

        for r in results:
            files_created.extend(r.files_created)
            files_modified.extend(r.files_modified)

        # 计算总成本和耗时
        total_cost = sum(r.cost for r in results)
        total_duration = sum(r.duration_ms for r in results)

        # 收集警告
        warnings = []
        for r in results:
            warnings.extend(r.warnings)

        return {
            "success": all(r.state == SubagentState.COMPLETED for r in results),
            "output": "\n\n".join(outputs) if outputs else "No output",
            "files_created": list(set(files_created)),
            "files_modified": list(set(files_modified)),
            "total_cost": total_cost,
            "total_duration_ms": total_duration,
            "warnings": warnings,
            "subagent_count": len(results),
            "subagent_results": [
                {
                    "id": r.subagent_id,
                    "state": r.state.value,
                    "duration_ms": r.duration_ms,
                }
                for r in results
            ],
        }
