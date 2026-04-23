"""
Benchmark 测试套件 - 完整的测试用例集

包含：
- 文件操作基准测试
- 代码生成基准测试
- 调试修复基准测试
- 多轮对话基准测试
- 性能压力测试
- 成本效率测试
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

# 导入 Benchmark 核心
from benchmark import (
    BenchmarkResult,
    BenchmarkTask,
    BenchmarkReport,
    HarnessBenchmark,
)


# ==================== 测试用例集 ====================

class FileOperationBenchmarks:
    """文件操作基准测试集"""

    @staticmethod
    def get_all() -> list[BenchmarkTask]:
        return [
            *FileOperationBenchmarks.get_list_read(),
            *FileOperationBenchmarks.get_edit_operations(),
        ]

    @staticmethod
    def get_list_read() -> list[BenchmarkTask]:
        """列表和读取操作测试"""
        return [
            BenchmarkTask(
                id="file_list_001",
                name="列出 Python 文件",
                description="遍历项目目录，列出所有 Python 源文件",
                input="列出项目中所有的 .py 文件，按目录分组",
                expected_output=None,
                timeout=30,
                max_tokens=8000,
            ),
            BenchmarkTask(
                id="file_list_002",
                name="列出配置文件",
                description="查找项目中的配置文件",
                input="找出项目中所有的配置文件（如 .json, .yaml, .toml, .ini）",
                expected_output=None,
                timeout=25,
                max_tokens=6000,
            ),
            BenchmarkTask(
                id="file_read_001",
                name="读取核心文件",
                description="读取并分析核心代码文件",
                input="读取 main.py，分析其主要功能和模块依赖",
                expected_output=None,
                timeout=20,
                max_tokens=5000,
            ),
            BenchmarkTask(
                id="file_read_002",
                name="批量读取相关文件",
                description="读取多个相关文件进行分析",
                input="读取同目录下所有模块的 __init__.py，分析模块结构",
                expected_output=None,
                timeout=30,
                max_tokens=8000,
            ),
            BenchmarkTask(
                id="file_search_001",
                name="搜索代码片段",
                description="在项目中搜索特定代码模式",
                input="找出所有使用 async/await 的函数定义",
                expected_output=None,
                timeout=45,
                max_tokens=15000,
            ),
        ]

    @staticmethod
    def get_edit_operations() -> list[BenchmarkTask]:
        """编辑操作测试"""
        return [
            BenchmarkTask(
                id="file_edit_001",
                name="添加函数",
                description="在现有文件中添加新函数",
                input="在 utils.py 中添加一个函数 calculate_md5(text: str) -> str，用于计算字符串的 MD5 哈希值",
                expected_output=None,
                timeout=30,
                max_tokens=10000,
            ),
            BenchmarkTask(
                id="file_edit_002",
                name="修改函数",
                description="修改现有函数",
                input="修改 process_data 函数，添加参数 validation: bool = True",
                expected_output=None,
                timeout=25,
                max_tokens=8000,
            ),
            BenchmarkTask(
                id="file_edit_003",
                name="重构代码",
                description="重构现有代码结构",
                input="将 calculate_total 函数中的重复计算逻辑提取为独立函数",
                expected_output=None,
                timeout=45,
                max_tokens=15000,
            ),
            BenchmarkTask(
                id="file_create_001",
                name="创建新文件",
                description="创建新的代码文件",
                input="创建 tests/test_example.py，包含 unittest.TestCase 基类的示例测试",
                expected_output=None,
                timeout=30,
                max_tokens=10000,
            ),
        ]


class CodeGenerationBenchmarks:
    """代码生成基准测试集"""

    @staticmethod
    def get_all() -> list[BenchmarkTask]:
        return [
            *CodeGenerationBenchmarks.get_algorithm_tasks(),
            *CodeGenerationBenchmarks.get_class_tasks(),
            *CodeGenerationBenchmarks.get_api_tasks(),
        ]

    @staticmethod
    def get_algorithm_tasks() -> list[BenchmarkTask]:
        """算法代码生成"""
        return [
            BenchmarkTask(
                id="code_algo_001",
                name="排序算法",
                description="生成排序算法实现",
                input="实现一个归并排序函数 merge_sort(arr: list) -> list，要求时间复杂度 O(n log n)",
                expected_output=None,
                timeout=30,
                max_tokens=10000,
            ),
            BenchmarkTask(
                id="code_algo_002",
                name="二叉树遍历",
                description="生成二叉树遍历代码",
                input="实现二叉树的前序、中序、后序遍历（递归和迭代版本）",
                expected_output=None,
                timeout=35,
                max_tokens=12000,
            ),
            BenchmarkTask(
                id="code_algo_003",
                name="动态规划",
                description="生成动态规划解决方案",
                input="实现斐波那契数列的第 N 项计算，分别用递归和动态规划实现，对比性能",
                expected_output=None,
                timeout=30,
                max_tokens=10000,
            ),
            BenchmarkTask(
                id="code_algo_004",
                name="图算法",
                description="生成图算法实现",
                input="实现 Dijkstra 最短路径算法",
                expected_output=None,
                timeout=40,
                max_tokens=15000,
            ),
        ]

    @staticmethod
    def get_class_tasks() -> list[BenchmarkTask]:
        """类和面向对象代码生成"""
        return [
            BenchmarkTask(
                id="code_class_001",
                name="数据类",
                description="生成数据类实现",
                input="创建一个 User 数据类，包含 id, name, email, created_at 属性，以及 __repr__ 和 to_dict 方法",
                expected_output=None,
                timeout=25,
                max_tokens=8000,
            ),
            BenchmarkTask(
                id="code_class_002",
                name="单例模式",
                description="生成单例模式实现",
                input="实现线程安全的单例模式，使用双重检查锁定",
                expected_output=None,
                timeout=30,
                max_tokens=10000,
            ),
            BenchmarkTask(
                id="code_class_003",
                name="工厂模式",
                description="生成工厂模式实现",
                input="实现一个抽象工厂模式，用于创建不同类型的数据库连接（MySQL, PostgreSQL, SQLite）",
                expected_output=None,
                timeout=40,
                max_tokens=15000,
            ),
        ]

    @staticmethod
    def get_api_tasks() -> list[BenchmarkTask]:
        """API 和接口代码生成"""
        return [
            BenchmarkTask(
                id="code_api_001",
                name="REST API 端点",
                description="生成 REST API 端点",
                input="用 FastAPI 实现一个简单的用户管理 API，包含 GET /users, POST /users, GET /users/{id} 三个端点",
                expected_output=None,
                timeout=45,
                max_tokens=15000,
            ),
            BenchmarkTask(
                id="code_api_002",
                name="中间件",
                description="生成中间件实现",
                input="实现一个日志中间件，记录请求的方法、路径、耗时和响应状态码",
                expected_output=None,
                timeout=35,
                max_tokens=12000,
            ),
        ]


class DebuggingBenchmarks:
    """调试和修复基准测试集"""

    @staticmethod
    def get_all() -> list[BenchmarkTask]:
        return [
            *DebuggingBenchmarks.get_bug_fixes(),
            *DebuggingBenchmarks.get_error_analysis(),
        ]

    @staticmethod
    def get_bug_fixes() -> list[BenchmarkTask]:
        """Bug 修复测试"""
        return [
            BenchmarkTask(
                id="debug_fix_001",
                name="修复空指针",
                description="修复可能的空指针异常",
                input="修复 user_profile.py 中的空指针问题，用户可能在没有登录的情况下访问个人资料",
                expected_output=None,
                timeout=30,
                max_tokens=10000,
            ),
            BenchmarkTask(
                id="debug_fix_002",
                name="修复竞态条件",
                description="修复多线程竞态条件",
                input="修复 counter.py 中的计数器竞态条件问题，确保并发访问时的准确性",
                expected_output=None,
                timeout=35,
                max_tokens=12000,
            ),
            BenchmarkTask(
                id="debug_fix_003",
                name="修复内存泄漏",
                description="定位和修复内存泄漏",
                input="分析 cache_manager.py，查找可能导致内存泄漏的地方并修复",
                expected_output=None,
                timeout=40,
                max_tokens=15000,
            ),
            BenchmarkTask(
                id="debug_fix_004",
                name="修复死循环",
                description="修复导致死循环的代码",
                input="process_batch 函数在某些情况下会陷入死循环，找出并修复",
                expected_output=None,
                timeout=30,
                max_tokens=10000,
            ),
        ]

    @staticmethod
    def get_error_analysis() -> list[BenchmarkTask]:
        """错误分析测试"""
        return [
            BenchmarkTask(
                id="debug_analyze_001",
                name="分析异常堆栈",
                description="分析错误堆栈并定位问题",
                input="分析以下错误：IndexError: list index out of range at line 42 in data_processor.py",
                expected_output=None,
                timeout=25,
                max_tokens=8000,
            ),
            BenchmarkTask(
                id="debug_analyze_002",
                name="性能瓶颈分析",
                description="分析性能瓶颈",
                input="分析 api_handler.py，找出可能导致 API 响应慢的原因",
                expected_output=None,
                timeout=35,
                max_tokens=12000,
            ),
        ]


class MultiTurnBenchmarks:
    """多轮对话基准测试集"""

    @staticmethod
    def get_all() -> list[BenchmarkTask]:
        return [
            MultiTurnBenchmarks.create_task(
                id="multi_001",
                name="需求澄清对话",
                description="多轮澄清需求的对话",
                steps=[
                    "用户：创建一个用户注册功能",
                    "Agent：需要确认几个问题：1) 使用哪种认证方式？ 2) 需要邮箱验证吗？ 3) 用户名有什么限制？",
                    "用户：使用 JWT 认证，需要邮箱验证，用户名 3-20 位",
                    "Agent：好的，实现中还有什么特殊要求吗？比如密码复杂度？",
                    "用户：密码至少 8 位，需包含大小写和数字",
                ],
                expected_output=None,
                timeout=60,
            ),
            MultiTurnBenchmarks.create_task(
                id="multi_002",
                name="调试追踪对话",
                description="多轮调试追踪",
                steps=[
                    "用户：应用启动失败",
                    "Agent：错误信息是什么？",
                    "用户：ConnectionRefusedError: [Errno 111] Connection refused",
                    "Agent：这通常是数据库连接问题。请确认：1) 数据库服务是否启动？ 2) 端口是否正确？",
                    "用户：数据库在 localhost:5432，我检查了配置文件也是 5432",
                    "Agent：请运行 'netstat -an | grep 5432' 确认端口监听状态",
                    "用户：端口没有监听",
                    "Agent：数据库服务可能未启动，请运行 'service postgresql start' 启动服务",
                ],
                expected_output=None,
                timeout=90,
            ),
            MultiTurnBenchmarks.create_task(
                id="multi_003",
                name="重构迭代对话",
                description="多轮重构迭代",
                steps=[
                    "用户：我想要一个爬虫程序",
                    "Agent：好的，请提供：1) 爬取哪个网站？ 2) 需要爬取哪些数据？ 3) 有反爬限制吗？",
                    "用户：爬取豆瓣电影 Top250，收集电影名、评分、评价人数",
                    "Agent：明白。使用 requests + BeautifulSoup 实现，可以吗？",
                    "用户：好的，但要注意遵守 robots.txt",
                    "Agent：好的，实现中会添加 robots.txt 检查和适当的请求间隔",
                ],
                expected_output=None,
                timeout=75,
            ),
        ]

    @staticmethod
    def create_task(
        id: str,
        name: str,
        description: str,
        steps: list[str],
        expected_output: str | None,
        timeout: int,
    ) -> BenchmarkTask:
        """创建多轮对话测试任务"""
        return BenchmarkTask(
            id=id,
            name=name,
            description=description,
            input="\n".join(steps),
            expected_output=expected_output,
            timeout=timeout,
            max_tokens=20000,
        )


class ToolCallBenchmarks:
    """工具调用基准测试集"""

    @staticmethod
    def get_all() -> list[BenchmarkTask]:
        return [
            *ToolCallBenchmarks.get_parallel_calls(),
            *ToolCallBenchmarks.get_sequential_calls(),
            *ToolCallBenchmarks.get_mixed_calls(),
        ]

    @staticmethod
    def get_parallel_calls() -> list[BenchmarkTask]:
        """并行工具调用测试"""
        return [
            BenchmarkTask(
                id="tool_parallel_001",
                name="同时读取多个文件",
                description="测试并行读取不相关文件",
                input="同时读取 config.json, users.json, products.json 三个文件，汇总其中的配置信息",
                expected_output=None,
                timeout=30,
                max_tokens=10000,
            ),
            BenchmarkTask(
                id="tool_parallel_002",
                name="批量创建文件",
                description="测试并行创建多个文件",
                input="创建 src/__init__.py, src/models/__init__.py, src/views/__init__.py 三个空包初始化文件",
                expected_output=None,
                timeout=25,
                max_tokens=8000,
            ),
        ]

    @staticmethod
    def get_sequential_calls() -> list[BenchmarkTask]:
        """顺序工具调用测试"""
        return [
            BenchmarkTask(
                id="tool_seq_001",
                name="读取后修改",
                description="读取文件后进行修改",
                input="1) 读取 data.json  2) 添加新字段 version: '1.0.0'  3) 保存回 data.json",
                expected_output=None,
                timeout=30,
                max_tokens=10000,
            ),
            BenchmarkTask(
                id="tool_seq_002",
                name="搜索后编辑",
                description="搜索后进行编辑",
                input="1) 搜索所有包含 TODO 的文件  2) 将第一个 TODO 替换为具体的实现计划",
                expected_output=None,
                timeout=35,
                max_tokens=12000,
            ),
        ]

    @staticmethod
    def get_mixed_calls() -> list[BenchmarkTask]:
        """混合工具调用测试"""
        return [
            BenchmarkTask(
                id="tool_mixed_001",
                name="复杂工作流",
                description="测试复杂的多工具组合",
                input="完成以下任务：1) 创建 backup 目录  2) 列出 src 目录下所有 Python 文件  3) 将这些文件复制到 backup 目录",
                expected_output=None,
                timeout=45,
                max_tokens=15000,
            ),
        ]


class ContextWindowBenchmarks:
    """上下文窗口基准测试集"""

    @staticmethod
    def get_all() -> list[BenchmarkTask]:
        return [
            *ContextWindowBenchmarks.get_long_context(),
            *ContextWindowBenchmarks.get_compaction(),
        ]

    @staticmethod
    def get_long_context() -> list[BenchmarkTask]:
        """长上下文测试"""
        # 生成大量代码作为上下文
        large_code_context = "# " + "x" * 5000  # 模拟长上下文

        return [
            BenchmarkTask(
                id="context_long_001",
                name="处理长文件",
                description="处理超过 1000 行的单个文件",
                input=f"分析以下代码中的主要函数和类：\n{large_code_context}",
                expected_output=None,
                timeout=45,
                max_tokens=50000,
            ),
        ]

    @staticmethod
    def get_compaction() -> list[BenchmarkTask]:
        """上下文压缩测试"""
        return [
            BenchmarkTask(
                id="context_compact_001",
                name="多文件摘要",
                description="处理多个文件并生成摘要",
                input="阅读 src/ 目录下所有 .py 文件，为每个文件生成一句话摘要，最终输出一份项目结构文档",
                expected_output=None,
                timeout=60,
                max_tokens=80000,
            ),
        ]


# ==================== 测试运行器 ====================

@dataclass
class BenchmarkSuiteConfig:
    """测试套件配置"""
    name: str = "Default Suite"
    description: str = ""

    # 测试类别开关
    file_ops: bool = True
    code_gen: bool = True
    debugging: bool = True
    multi_turn: bool = False
    tool_calls: bool = True
    context_window: bool = False

    # 运行参数
    max_concurrent: int = 3
    fail_fast: bool = False
    retry_count: int = 0

    # 输出配置
    output_format: str = "markdown"  # markdown, json, html
    output_path: str | None = None


class BenchmarkRunner:
    """基准测试运行器"""

    def __init__(
        self,
        benchmark: HarnessBenchmark,
        config: BenchmarkSuiteConfig | None = None,
    ):
        self.benchmark = benchmark
        self.config = config or BenchmarkSuiteConfig()

        # 测试结果
        self.results: list[BenchmarkResult] = []
        self.suite_results: dict[str, list[BenchmarkResult]] = {}

    def get_all_tasks(self) -> list[tuple[str, list[BenchmarkTask]]]:
        """获取所有测试任务"""
        tasks: list[tuple[str, list[BenchmarkTask]]] = []

        if self.config.file_ops:
            tasks.append(("文件操作", FileOperationBenchmarks.get_all()))

        if self.config.code_gen:
            tasks.append(("代码生成", CodeGenerationBenchmarks.get_all()))

        if self.config.debugging:
            tasks.append(("调试修复", DebuggingBenchmarks.get_all()))

        if self.config.multi_turn:
            tasks.append(("多轮对话", MultiTurnBenchmarks.get_all()))

        if self.config.tool_calls:
            tasks.append(("工具调用", ToolCallBenchmarks.get_all()))

        if self.config.context_window:
            tasks.append(("上下文窗口", ContextWindowBenchmarks.get_all()))

        return tasks

    async def run_full_suite(
        self,
        agent_executor: callable | None = None,
    ) -> BenchmarkReport:
        """运行完整测试套件"""
        all_tasks = self.get_all_tasks()

        total_tasks = sum(len(tasks) for _, tasks in all_tasks)
        print(f"\n{'='*60}")
        print(f"开始运行测试套件: {self.config.name}")
        print(f"共 {len(all_tasks)} 个测试类别，{total_tasks} 个测试用例")
        print(f"{'='*60}\n")

        for category, tasks in all_tasks:
            print(f"\n📂 {category} ({len(tasks)} 个测试)")

            category_results = []
            for task in tasks:
                print(f"  ⏳ {task.name}...", end=" ")

                try:
                    result = await self.benchmark.run_task(
                        task,
                        agent_executor or self._mock_executor,
                    )

                    status = "✅" if result.success else ("⏱️" if result.timeout else "❌")
                    print(f"{status} ({result.duration_ms:.0f}ms)")

                    if result.error:
                        print(f"      错误: {result.error[:100]}")

                    category_results.append(result)
                    self.results.append(result)

                    # 失败快速停止
                    if self.config.fail_fast and not result.success:
                        print(f"      ⚠️ 失败快速停止")
                        break

                except Exception as e:
                    print(f"  ❌ 异常: {e}")

            self.suite_results[category] = category_results

        return self._generate_suite_report()

    async def _mock_executor(self, input_text: str) -> dict:
        """模拟 Agent 执行器（用于测试）"""
        await asyncio.sleep(random.uniform(0.1, 0.5))

        tokens = random.randint(500, 3000)
        return {
            "output": f"[Mock output for: {input_text[:50]}...]",
            "prompt_tokens": tokens,
            "completion_tokens": tokens // 2,
            "total_tokens": tokens * 3 // 2,
            "cost": tokens * 0.00001,
            "llm_calls": random.randint(1, 3),
            "tool_calls": random.randint(0, 5),
        }

    def _generate_suite_report(self) -> BenchmarkReport:
        """生成套件报告"""
        report = self.benchmark._generate_report(self.results)

        # 添加类别统计
        category_stats = {}
        for category, results in self.suite_results.items():
            if results:
                category_stats[category] = {
                    "total": len(results),
                    "success": sum(1 for r in results if r.success),
                    "failed": sum(1 for r in results if not r.success),
                    "avg_duration": sum(r.duration_ms for r in results) / len(results),
                }

        report.metadata["category_stats"] = category_stats
        report.name = self.config.name

        return report

    def generate_suite_markdown_report(self, report: BenchmarkReport) -> str:
        """生成 Markdown 格式的套件报告"""
        lines = [
            f"# 📊 {report.name} - 完整测试报告",
            "",
            f"**执行时间**: {report.created_at}",
            f"**基准测试 ID**: `{report.benchmark_id}`",
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
        ]

        # 类别统计
        category_stats = report.metadata.get("category_stats", {})
        if category_stats:
            lines.extend([
                "## 📂 分类统计",
                "",
                "| 类别 | 总数 | 成功 | 失败 | 平均耗时 |",
                "|------|------|------|------|----------|",
            ])

            for category, stats in category_stats.items():
                lines.append(
                    f"| {category} | {stats['total']} | "
                    f"{stats['success']} | {stats['failed']} | "
                    f"{stats['avg_duration']:.0f}ms |"
                )
            lines.append("")

        # 性能统计
        lines.extend([
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
            "| # | 任务 | 类别 | 状态 | 耗时 | Tokens |",
            "|---|------|------|------|------|--------|",
        ])

        for i, r in enumerate(report.results, 1):
            status = "✅" if r.success else ("⏱️" if r.timeout else "❌")

            # 查找类别
            category = "N/A"
            for cat, results in self.suite_results.items():
                if r in results:
                    category = cat
                    break

            lines.append(
                f"| {i} | {r.task_name} | {category} | {status} | "
                f"{r.duration_ms:.0f}ms | {r.total_tokens:,} |"
            )

        return "\n".join(lines)


# ==================== 测试配置预设 ====================

class BenchmarkPresets:
    """基准测试预设配置"""

    @staticmethod
    def quick() -> BenchmarkSuiteConfig:
        """快速测试（5分钟）"""
        return BenchmarkSuiteConfig(
            name="快速测试",
            description="快速验证核心功能",
            file_ops=True,
            code_gen=True,
            debugging=False,
            multi_turn=False,
            tool_calls=True,
            context_window=False,
            fail_fast=True,
        )

    @staticmethod
    def standard() -> BenchmarkSuiteConfig:
        """标准测试（15分钟）"""
        return BenchmarkSuiteConfig(
            name="标准测试",
            description="覆盖主要功能模块",
            file_ops=True,
            code_gen=True,
            debugging=True,
            multi_turn=True,
            tool_calls=True,
            context_window=True,
            fail_fast=False,
        )

    @staticmethod
    def comprehensive() -> BenchmarkSuiteConfig:
        """完整测试（30分钟+）"""
        return BenchmarkSuiteConfig(
            name="完整测试",
            description="全面覆盖所有功能",
            file_ops=True,
            code_gen=True,
            debugging=True,
            multi_turn=True,
            tool_calls=True,
            context_window=True,
            fail_fast=False,
            retry_count=1,
        )

    @staticmethod
    def ci() -> BenchmarkSuiteConfig:
        """CI 集成测试"""
        return BenchmarkSuiteConfig(
            name="CI 测试",
            description="CI 环境中运行",
            file_ops=True,
            code_gen=True,
            debugging=False,
            multi_turn=False,
            tool_calls=True,
            context_window=False,
            fail_fast=True,
            max_concurrent=5,
        )


# ==================== 主函数 ====================

async def main():
    """主函数 - 运行基准测试"""
    import argparse

    parser = argparse.ArgumentParser(description="Harness 基准测试套件")
    parser.add_argument("--preset", choices=["quick", "standard", "comprehensive", "ci"],
                       default="quick", help="测试预设")
    parser.add_argument("--output", help="输出文件路径")
    parser.add_argument("--no-mock", action="store_true", help="使用真实 Agent")

    args = parser.parse_args()

    # 获取预设
    preset_map = {
        "quick": BenchmarkPresets.quick,
        "standard": BenchmarkPresets.standard,
        "comprehensive": BenchmarkPresets.comprehensive,
        "ci": BenchmarkPresets.ci,
    }

    config = preset_map[args.preset]()

    # 创建基准测试实例
    benchmark = HarnessBenchmark(name=config.name)
    runner = BenchmarkRunner(benchmark, config)

    # 运行测试
    report = await runner.run_full_suite()

    # 生成报告
    report_content = runner.generate_suite_markdown_report(report)
    print("\n" + "="*60)
    print(report_content)
    print("="*60)

    # 保存报告
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(f"\n报告已保存到: {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
