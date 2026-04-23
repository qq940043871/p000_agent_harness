"""
Benchmark - Harness 性能评估系统

功能：
- 自动化测试脚本
- 性能指标收集
- 对比分析
- 评估报告生成
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4


@dataclass
class BenchmarkTask:
    """基准测试任务"""
    id: str
    name: str
    description: str
    input: str
    expected_output: str | None = None
    timeout: int = 60  # 秒
    max_tokens: int = 50000


@dataclass
class BenchmarkResult:
    """基准测试结果"""
    task_id: str
    task_name: str

    # 执行结果
    success: bool = False
    completed: bool = False
    timeout: bool = False

    # 时间指标
    duration_ms: float = 0.0
    llm_calls: int = 0
    tool_calls: int = 0

    # Token 指标
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0

    # 质量指标
    output: str = ""
    error: str = ""

    # 元数据
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkReport:
    """基准测试报告"""
    benchmark_id: str
    name: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 汇总统计
    total_tasks: int = 0
    completed_tasks: int = 0
    success_tasks: int = 0
    failed_tasks: int = 0
    timeout_tasks: int = 0

    # 时间统计
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    min_duration_ms: float = 0.0
    max_duration_ms: float = 0.0

    # Token 统计
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_tokens_per_task: float = 0.0
    avg_cost_per_task: float = 0.0

    # 详细结果
    results: list[BenchmarkResult] = field(default_factory=list)

    # 对比数据
    previous_report: dict | None = None
    improvement: dict[str, float] = field(default_factory=dict)


class HarnessBenchmark:
    """
    Harness 基准测试框架

    用于自动化评估 Harness 引擎的性能。
    """

    # 预设测试任务
    DEFAULT_TASKS: list[BenchmarkTask] = [
        BenchmarkTask(
            id="task_001",
            name="文件探索",
            description="探索项目结构，列出所有 Python 文件",
            input="列出项目中的所有 Python 文件",
            expected_output=None,
            timeout=30,
        ),
        BenchmarkTask(
            id="task_002",
            name="代码修复",
            description="修复一个已知的 Bug",
            input="找到并修复代码中的错误",
            expected_output=None,
            timeout=60,
        ),
        BenchmarkTask(
            id="task_003",
            name="文档生成",
            description="为代码生成文档",
            input="为 main.py 生成文档",
            expected_output=None,
            timeout=45,
        ),
        BenchmarkTask(
            id="task_004",
            name="重构任务",
            description="重构一段代码",
            input="重构 Calculator 类，使其更简洁",
            expected_output=None,
            timeout=60,
        ),
        BenchmarkTask(
            id="task_005",
            name="测试编写",
            description="为功能编写测试",
            input="为 UserService 编写单元测试",
            expected_output=None,
            timeout=60,
        ),
    ]

    def __init__(
        self,
        name: str = "Harness Benchmark",
        storage_path: str | Path | None = None,
    ):
        self.name = name
        self.benchmark_id = str(uuid4())[:16]
        self.storage_path = Path(storage_path) if storage_path else None

        if self.storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)

    def create_task(
        self,
        name: str,
        description: str,
        input: str,
        expected_output: str | None = None,
        timeout: int = 60,
    ) -> BenchmarkTask:
        """创建测试任务"""
        task_id = f"task_{len(self.DEFAULT_TASKS) + 1:03d}"
        return BenchmarkTask(
            id=task_id,
            name=name,
            description=description,
            input=input,
            expected_output=expected_output,
            timeout=timeout,
        )

    async def run_task(
        self,
        task: BenchmarkTask,
        agent_executor: Callable[[str], dict],
    ) -> BenchmarkResult:
        """运行单个测试任务"""
        result = BenchmarkResult(
            task_id=task.id,
            task_name=task.name,
        )

        start_time = time.time()

        try:
            response = await self._execute_with_timeout(
                agent_executor,
                task.input,
                task.timeout,
            )

            result.duration_ms = (time.time() - start_time) * 1000
            result.completed = True
            result.success = True
            result.output = response.get("output", "")

            result.prompt_tokens = response.get("prompt_tokens", 0)
            result.completion_tokens = response.get("completion_tokens", 0)
            result.total_tokens = response.get("total_tokens", 0)
            result.cost = response.get("cost", 0.0)
            result.llm_calls = response.get("llm_calls", 1)
            result.tool_calls = response.get("tool_calls", 0)

        except TimeoutError:
            result.timeout = True
            result.duration_ms = task.timeout * 1000
            result.error = f"任务超时（{task.timeout}秒）"

        except Exception as e:
            result.success = False
            result.duration_ms = (time.time() - start_time) * 1000
            result.error = str(e)

        return result

    async def _execute_with_timeout(
        self,
        executor: Callable,
        *args,
        timeout: int = 60,
    ) -> dict:
        """带超时的执行"""
        import asyncio

        try:
            result = await asyncio.wait_for(
                executor(*args),
                timeout=timeout,
            )
            return result
        except asyncio.TimeoutError:
            raise TimeoutError()

    async def run_benchmark(
        self,
        tasks: list[BenchmarkTask] | None = None,
        agent_executor: Callable[[str], dict] | None = None,
    ) -> BenchmarkReport:
        """运行完整基准测试"""
        tasks = tasks or self.DEFAULT_TASKS
        results: list[BenchmarkResult] = []

        for task in tasks:
            print(f"执行任务: {task.name}...")

            if agent_executor:
                result = await self.run_task(task, agent_executor)
            else:
                result = self._simulate_task(task)

            results.append(result)

            status = "✅" if result.success else ("⏱️" if result.timeout else "❌")
            print(f"  {status} {result.task_name} - {result.duration_ms:.0f}ms")

        report = self._generate_report(results)

        if self.storage_path:
            self._save_report(report)

        return report

    def _simulate_task(self, task: BenchmarkTask) -> BenchmarkResult:
        """模拟任务执行（用于测试）"""
        import random

        duration = random.uniform(100, 2000)
        tokens = random.randint(500, 5000)

        return BenchmarkResult(
            task_id=task.id,
            task_name=task.name,
            success=random.random() > 0.2,
            completed=True,
            duration_ms=duration,
            llm_calls=random.randint(1, 5),
            tool_calls=random.randint(0, 10),
            prompt_tokens=tokens,
            completion_tokens=tokens // 2,
            total_tokens=tokens * 3 // 2,
            cost=tokens * 0.00001,
            output="[模拟输出]",
        )

    def _generate_report(self, results: list[BenchmarkResult]) -> BenchmarkReport:
        """生成测试报告"""
        completed = [r for r in results if r.completed]
        success = [r for r in results if r.success]
        failed = [r for r in results if not r.success and not r.timeout]
        timeouts = [r for r in results if r.timeout]

        durations = [r.duration_ms for r in completed]
        total_tokens_list = [r.total_tokens for r in completed]
        costs = [r.cost for r in completed]

        return BenchmarkReport(
            benchmark_id=self.benchmark_id,
            name=self.name,
            total_tasks=len(results),
            completed_tasks=len(completed),
            success_tasks=len(success),
            failed_tasks=len(failed),
            timeout_tasks=len(timeouts),
            total_duration_ms=sum(durations),
            avg_duration_ms=sum(durations) / len(durations) if durations else 0,
            min_duration_ms=min(durations) if durations else 0,
            max_duration_ms=max(durations) if durations else 0,
            total_tokens=sum(total_tokens_list),
            total_cost=sum(costs),
            avg_tokens_per_task=sum(total_tokens_list) / len(total_tokens_list) if total_tokens_list else 0,
            avg_cost_per_task=sum(costs) / len(costs) if costs else 0,
            results=results,
        )

    def _save_report(self, report: BenchmarkReport) -> None:
        """保存报告"""
        if not self.storage_path:
            return

        path = self.storage_path / f"benchmark_{report.benchmark_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report.__dict__, f, ensure_ascii=False, indent=2)

    def load_report(self, benchmark_id: str) -> BenchmarkReport | None:
        """加载报告"""
        if not self.storage_path:
            return None

        path = self.storage_path / f"benchmark_{benchmark_id}.json"
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return BenchmarkReport(**data)

    def generate_markdown_report(self, report: BenchmarkReport) -> str:
        """生成 Markdown 格式报告"""
        lines = [
            f"# 📊 {report.name}",
            "",
            f"**基准测试 ID**: `{report.benchmark_id}`",
            f"**执行时间**: {report.created_at}",
            "",
            "---",
            "",
            "## 📈 总体统计",
            "",
            "| 指标 | 数值 |",
            "|------|------|",
            f"| 总任务数 | {report.total_tasks} |",
            f"| ✅ 成功 | {report.success_tasks} |",
            f"| ❌ 失败 | {report.failed_tasks} |",
            f"| ⏱️ 超时 | {report.timeout_tasks} |",
            f"| 成功率 | {report.success_tasks / report.total_tasks * 100:.1f}% |",
            "",
            "## ⏱️ 性能指标",
            "",
            f"- **总耗时**: {report.total_duration_ms:.0f} ms",
            f"- **平均耗时**: {report.avg_duration_ms:.0f} ms",
            f"- **最快**: {report.min_duration_ms:.0f} ms",
            f"- **最慢**: {report.max_duration_ms:.0f} ms",
            "",
            "## 💰 成本指标",
            "",
            f"- **总 Token**: {report.total_tokens:,}",
            f"- **总成本**: ${report.total_cost:.6f}",
            f"- **平均 Token/任务**: {report.avg_tokens_per_task:.0f}",
            f"- **平均成本/任务**: ${report.avg_cost_per_task:.6f}",
            "",
            "## 📋 详细结果",
            "",
            "| 任务 | 状态 | 耗时 | Tokens | 成本 |",
            "|------|------|------|--------|------|",
        ]

        for r in report.results:
            status = "✅" if r.success else ("⏱️" if r.timeout else "❌")
            lines.append(
                f"| {r.task_name} | {status} | "
                f"{r.duration_ms:.0f}ms | {r.total_tokens:,} | "
                f"${r.cost:.6f} |"
            )

        return "\n".join(lines)


class StandardBenchmarks:
    """标准基准测试集"""

    @staticmethod
    def get_quality_benchmark() -> list[BenchmarkTask]:
        """质量评估基准测试"""
        return [
            BenchmarkTask(
                id="quality_001",
                name="代码正确性",
                description="生成的代码能正确运行",
                input="写一个函数计算斐波那契数列第N项",
                timeout=30,
            ),
            BenchmarkTask(
                id="quality_002",
                name="错误处理",
                description="代码包含适当的错误处理",
                input="写一个安全的文件读取函数",
                timeout=30,
            ),
        ]

    @staticmethod
    def get_efficiency_benchmark() -> list[BenchmarkTask]:
        """效率评估基准测试"""
        return [
            BenchmarkTask(
                id="efficiency_001",
                name="快速响应",
                description="简单任务应在5秒内完成",
                input="解释什么是闭包",
                timeout=10,
            ),
        ]
