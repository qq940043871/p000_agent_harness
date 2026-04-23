# OpenClaw Agent Harness

像写操作系统一样，实现 OpenClaw 的底层 Harness。

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置 API Key

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# 或者
export OPENAI_API_KEY=sk-...
```

### 运行

```bash
# 单次任务
python main.py "帮我分析当前目录的项目结构"

# 交互模式
python main.py

# 指定工作目录
python main.py -w /path/to/project "执行的任务"
```

## 项目结构

```
10_agent_harness/
├── harness/                    # 核心框架
│   ├── __init__.py           # 模块导出
│   ├── main_loop.py           # Main Loop 引擎
│   ├── provider/              # LLM Provider
│   │   ├── base.py            # 抽象基类
│   │   ├── claude.py          # Claude 实现
│   │   ├── openai_compat.py   # OpenAI 兼容实现
│   │   └── factory.py         # Provider 工厂
│   ├── tools/                # 工具系统
│   │   ├── base.py           # 工具基类
│   │   ├── registry.py       # 工具注册表
│   │   ├── edit.py           # Edit 工具
│   │   └── plugins/          # 工具插件
│   ├── prompt/               # Prompt 构建器
│   ├── session/              # Session 管理
│   │
│   │   # ===== 第三章：上下文工程 =====
│   ├── context_compactor.py  # 上下文压缩
│   ├── memory_manager.py     # 记忆管理系统
│   │
│   │   # ===== 第四章：稳定性控制 =====
│   ├── system_reminders.py   # 行为干预
│   ├── middleware.py         # 中间件拦截
│   ├── subagent.py          # Subagent 委派系统 ⭐ NEW
│   │
│   │   # ===== 第五章：可观测性 =====
│   ├── cost_tracker.py       # 成本追踪
│   ├── tracer.py             # 链路追踪
│   ├── benchmark.py          # 性能评估
│   ├── benchmark_suite.py   # 完整测试套件 ⭐ NEW
│   │
│   └── integrations/         # 集成模块
│       ├── feishu.py         # 飞书机器人
│       ├── approval_templates.py  # 审批模板
│       ├── coding.py         # Coding Plan 集成 ⭐ NEW
│       └── __init__.py       # 统一导出
│
├── main.py                   # CLI 入口
├── config.yaml               # 配置文件
└── AGENTS.md                 # Agent 行为规范
```

## 核心模块

### 第一/二章（已完成）
- **Provider**: 支持 Claude / OpenAI / 豆包 / Qwen / DeepSeek
- **Main Loop**: ReAct 循环引擎
- **Tool Registry**: 装饰器注册、自动 Schema 推断
- **Edit Tool**: 精确匹配 + 模糊匹配三级容错

### 第三章：上下文工程 ✅ 新增
- **ContextCompactor**: 阶梯降级上下文压缩
- **MemoryManager**: 状态外部化、持久化记忆、待办管理

```python
# 使用示例
from harness import ContextCompactor, MemoryManager, create_memory_manager

# 上下文压缩
compactor = StreamingCompactor()
compressed, result = compactor.check_and_compact(
    system_prompt, tools, messages
)

# 记忆管理
memory = create_memory_manager("/path/to/workspace", session_id="s123")
memory.store("用户偏好 Python", memory_type=MemoryType.SEMANTIC, importance=8)
todos = memory.get_todos(status="pending")
```

### 第四章：稳定性控制 ✅ 新增
- **SystemReminder**: 死循环检测、行为干预
- **Middleware**: 命令拦截、审批流程、高危操作防护
- **Subagent**: 任务委派、上下文隔离、并行执行

```python
# 使用示例
from harness import SystemReminder, MiddlewareManager, DangerousCommandDetector

# 系统提醒
reminder = SystemReminder()
injection = reminder.build_reminder_prompt(turn_count=25, total_tokens=50000)

# 中间件链
middleware = MiddlewareManager()
middleware.setup_default()
middleware.set_approval_handler(ConsoleApprovalHandler())

# Subagent 委派
from harness import SubagentPool, DelegatedTask, TaskPriority

pool = SubagentPool(max_concurrent=3)
task = DelegatedTask(
    id="task_001",
    task_type="exploration",
    description="探索项目结构",
    context={"goal": "分析项目"},
    priority=TaskPriority.HIGH,
)
result = await pool.delegate_task(task)
```

### 第五章：可观测性 ✅ 新增
- **CostTracker**: Token 消耗、成本计算、预算控制
- **Tracer**: 完整执行链路记录、失败复盘
- **Benchmark**: 自动化性能评估

```python
# 使用示例
from harness import CostTracker, Tracer, HarnessBenchmark

# 成本追踪
tracker = CostTracker(budget=10.0)  # $10 预算
tracker.start_session("sess_001")
tracker.record_usage(prompt_tokens=1000, completion_tokens=500)
print(tracker.generate_report())

# 链路追踪
tracer = Tracer("/path/to/traces")
trace_id = tracer.start_trace("sess_001", "用户消息")
with tracer.span("tool_call", SpanType.TOOL_CALL):
    # 执行工具
    pass
trace = tracer.end_trace()
print(tracer.generate_report(trace))

# 性能评估
benchmark = HarnessBenchmark()
report = await benchmark.run_benchmark()
print(benchmark.generate_markdown_report(report))

# 完整测试套件
from harness import (
    BenchmarkRunner,
    BenchmarkPresets,
    BenchmarkSuiteConfig,
    FileOperationBenchmarks,
    CodeGenerationBenchmarks,
    DebuggingBenchmarks,
)

runner = BenchmarkRunner(benchmark, BenchmarkPresets.standard())
report = await runner.run_full_suite()
print(runner.generate_suite_markdown_report(report))
```

### 第六章：飞书集成 ✅ 新增
- **FeishuBot**: 消息接收、审批流程、AgentOps 助手
- **ApprovalTemplates**: 10+ 审批场景模板

```python
# 使用示例
from harness import AgentOpsFeishuBot, FeishuConfig

config = FeishuConfig(
    app_id="cli_xxx",
    app_secret="xxx",
    approval_template_id="xxx",
)

bot = AgentOpsFeishuBot(config, harness=harness)

@bot.on_message
async def handle(msg: FeishuMessage):
    return await bot.handle_agentops_command(msg)

# 审批模板使用
from harness.integrations.approval_templates import (
    ApprovalType,
    ApprovalManager,
    ApprovalTemplates,
)

manager = ApprovalManager()
request = manager.create_request(
    ApprovalType.COMMAND_EXECUTE,
    requester_id="agent_001",
    requester_name="AI Agent",
    action="执行命令",
    target="rm -rf /tmp/*",
)
```

## 文档

详细文档请参考各章节的 Markdown 文件：

- [第 01 节：架构演进](./chapter01/01_架构演进.md)
- [第 02 节：核心心脏](./chapter01/02_核心心脏.md)
- [第 03 节：慢思考与自省](./chapter01/03_慢思考与自省.md)
- [第 04 节：大脑接入](./chapter01/04_大脑接入.md)
- [第 05 节：动作延伸](./chapter02/05_动作延伸.md)
- [第 06 节：大道至简](./chapter02/06_大道至简.md)
- [第 07 节：容错艺术](./chapter02/07_容错艺术.md)
- [第 08 节：并发提效](./chapter02/08_并发提效.md)
- [第 09 节：飞书集成](./chapter02/09_飞书集成.md)
- [第 10 节：提示词组装](./chapter03/10_提示词组装.md)
- [第 11 节：会话管理](./chapter03/11_会话管理.md)
- [第 12 节：突破内存](./chapter03/12_突破内存.md)
- [第 13 节：记忆沉淀](./chapter03/13_记忆沉淀.md)
- [第 14 节：错误自愈](./chapter03/14_错误自愈.md)
- [第 15 节：行为干预](./chapter04/15_行为干预.md)
- [第 16 节：防御纵深](./chapter04/16_防御纵深.md)
- [第 17 节：任务委派](./chapter04/17_任务委派.md)
- [第 18 节：成本追踪](./chapter05/18_成本追踪.md)
- [第 19 节：洞察黑盒](./chapter05/19_洞察黑盒.md)
- [第 20 节：科学度量](./chapter05/20_科学度量.md)
- [第 21 节：实战一](./chapter06/21_实战一.md)
- [第 22 节：实战二](./chapter06/22_实战二.md)

## 许可证

MIT License
