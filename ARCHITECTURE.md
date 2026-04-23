# Agent Harness 架构设计文档

## 概述

这是一个基于课程《从 0 开始构建 Agent Harness》实现的学习项目。该系统采用模块化设计，提供了完整的 Agent 运行时环境。

---

## 🎯 核心设计理念

### 1. 最小化 Harness (Minimal Harness)
- 只提供核心运行时能力
- 不预设复杂的任务编排逻辑
- 信任 LLM 的推理能力

### 2. 可观测性 (Observability)
- 完整的链路追踪
- Token 和成本统计
- 执行历史持久化

### 3. 可组合性 (Composability)
- 模块化设计
- 插件化工具系统
- 中间件拦截机制

---

## 📦 模块架构图

```
┌─────────────────────────────────────────────────────────┐
│                      Main Loop                          │
│           (Think → Act → Observe 循环引擎)              │
└────────────────────┬────────────────────────────────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
    ▼                ▼                ▼
┌─────────┐    ┌─────────┐    ┌─────────┐
│Provider │    │ Tools   │    │ Session │
│ (LLM)  │    │Registry │    │Manager  │
└─────────┘    └─────────┘    └─────────┘
    │                │                │
    └────────────────┼────────────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
    ▼                ▼                ▼
┌─────────┐    ┌─────────┐    ┌─────────┐
│Prompt   │    │Middleware│    │Tracer   │
│Builder  │    │  Chain  │    │         │
└─────────┘    └─────────┘    └─────────┘
                     │
                     ▼
            ┌──────────────┐
            │Context       │
            │Compactor     │
            └──────────────┘
```

---

## 🧩 核心模块详解

### 1. Main Loop (核心引擎)

**文件**: `harness/main_loop.py`

**职责**:
- 驱动 Think → Act → Observe 循环
- 管理执行状态和统计
- 事件系统（token 更新、工具调用等）

**核心类**:
```python
class MainLoop:
    - provider: LLM Provider
    - tool_registry: 工具注册表
    - max_turns: 最大轮次
    - token_budget: Token 预算
    
    async def run(user_message: str) -> LoopResult:
        # 1. Think: 调用 LLM
        # 2. Act: 执行工具调用（支持并发）
        # 3. Observe: 将结果追加到历史
        # 4. 检查终止条件
```

**设计亮点**:
- **事件驱动**: 通过 `on()`/`off()` 注册事件处理器
- **并发工具执行**: 独立工具调用并行执行，提升效率
- **状态机**: `LoopStatus` 清晰管理执行状态
- **统计追踪**: `LoopStats` 记录 tokens、工具调用数等

---

### 2. Provider (LLM 抽象层)

**文件**: `harness/provider/base.py`

**职责**:
- 统一不同 LLM API 的接口
- 抽象工具调用格式
- 提供 Token 使用统计

**设计模式**: **策略模式 + 工厂模式**

```python
class BaseProvider(ABC):
    @abstractmethod
    async def complete(messages, tools, max_tokens) -> LLMResponse:
        # 调用 LLM
```

**已实现 Provider**:
- `ClaudeProvider`: Anthropic Claude API
- `OpenAICompatProvider`: OpenAI 兼容 API

**设计亮点**:
- **抽象数据类**: `LLMResponse`、`ToolCall`、`Usage` 统一数据格式
- **可扩展**: 新 Provider 只需实现 `BaseProvider`
- **接口隔离**: 上层模块不依赖具体 LLM

---

### 3. Tools (工具系统)

**文件**:
- `harness/tools/base.py` - 基类定义
- `harness/tools/registry.py` - 注册表
- `harness/tools/plugins/` - 插件工具

**核心概念**:

```python
@dataclass
class ToolDefinition:
    name: str                    # 唯一标识
    description: str             # LLM 用于决策
    parameters: dict             # JSON Schema
    handler: Callable            # 执行函数
    category: str = "general"    # 分类
```

**设计模式**: **装饰器模式 + 注册表模式**

```python
# 装饰器注册
@registry.tool(description="读取文件")
async def read_file(path: str) -> str:
    ...

# 动态注册
registry.register(ToolDefinition(...))
```

**设计亮点**:
- **自动 Schema 推断**: `infer_schema()` 从函数签名生成 JSON Schema
- **分类管理**: 工具可分组，便于权限控制
- **并发支持**: `dispatch_parallel()` 支持批量并发执行
- **工具组**: `ToolGroup` 实现权限隔离
- **同步/异步兼容**: 自动检测 handler 类型

---

### 4. Session (会话管理)

**文件**: `harness/session/manager.py`

**职责**:
- 物理隔离会话数据
- 持久化对话历史
- 管理会话工件（artifacts）

**数据结构**:
```
.workbuddy/
└── sessions/
    └── {session_id}/
        ├── session.json       # 元数据
        ├── messages.jsonl     # 消息历史（JSONL 追加）
        └── artifacts/         # 生成的工件
            ├── report.txt
            └── code.py
```

**设计亮点**:
- **JSONL 格式**: 追加写入，性能好，损坏不影响全部
- **工件管理**: `save_artifact()` 持久化生成的文件
- **软链接**: 最新会话创建 `current` 软链接（Unix）
- **迭代器读取**: `iter_messages()` 内存友好
- **自动清理**: `cleanup_old_sessions()` 清理过期会话

---

### 5. Prompt Builder (提示词组装)

**文件**: `harness/prompt/builder.py`

**职责**:
- 模块化组装 System Prompt
- 加载外部规范文件
- 动态注入上下文

**设计模式**: **建造者模式**

```python
prompt = (
    PromptBuilder(workspace)
    .load_identity()           # .workbuddy/IDENTITY.md
    .load_agents_md()          # AGENTS.md
    .load_memory()             # 持久记忆
    .load_skills()             # Skills 插件
    .inject_working_directory()
    .inject_datetime()
    .build()
)
```

**设计亮点**:
- **优先级管理**: `PromptSection.priority` 控制顺序
- **条件启用**: `disable()`/`enable()` 灵活控制
- **Skills 插件化**: 从 `.workbuddy/skills/` 动态加载
- **链式调用**: 流畅的 API

---

### 6. Middleware (中间件系统)

**文件**: `harness/middleware.py`

**职责**:
- 工具调用前/后拦截
- 危险命令检测
- 人工审批流程

**执行阶段**:
```python
class MiddlewarePhase(Enum):
    PRE_TOOL_CALL    # 工具调用前
    POST_TOOL_CALL   # 工具调用后
    PRE_LLM_CALL     # LLM 调用前
    POST_LLM_CALL    # LLM 调用后
    PRE_RESPONSE     # 返回前
    POST_RESPONSE    # 返回后
```

**内置中间件**:
- `DangerousCommandDetector`: 危险命令检测
- `RateLimitMiddleware`: 速率限制
- `ContentFilterMiddleware`: 敏感内容过滤
- `LoggingMiddleware`: 日志记录

**设计模式**: **责任链模式**

```python
chain = MiddlewareChain()
chain.add(LoggingMiddleware())
chain.add(RateLimitMiddleware())
chain.add(DangerousCommandDetector())

result = await chain.execute(ctx)
if not result.allowed:
    # 拦截
```

**设计亮点**:
- **多阶段拦截**: 覆盖完整执行流程
- **审批集成**: `ApprovalHandler` 支持飞书/控制台审批
- **短路逻辑**: 一旦拦截立即返回
- **可组合**: 中间件顺序灵活配置

---

### 7. Tracer (链路追踪)

**文件**: `harness/tracer.py`

**职责**:
- 记录完整执行链路
- 性能分析
- 失败路径复盘

**数据结构**:
```python
@dataclass
class Span:
    span_id: str
    trace_id: str
    parent_id: str | None
    span_type: SpanType  # LLM_CALL, TOOL_CALL, ERROR, etc.
    start_time: str
    end_time: str
    duration_ms: float
    input/output: Any
    children: list[Span]  # 嵌套 Span
```

**设计模式**: **OpenTelemetry 兼容**

**使用方式**:
```python
tracer = Tracer(storage_path=".workbuddy/traces")
trace_id = tracer.start_trace(session_id, user_message)

with tracer.span("Tool:read_file", SpanType.TOOL_CALL):
    result = await read_file(path)

trace = tracer.end_trace()
report = tracer.generate_report(trace)
```

**设计亮点**:
- **父子 Span**: 支持嵌套调用
- **持久化追踪**: JSON 格式保存到磁盘
- **性能分析**: `analyze_trace()` 找出最慢操作
- **错误定位**: 完整记录错误上下文
- **OTel 兼容**: `OpenTelemetryExporter` 导出标准格式

---

### 8. Context Compactor (上下文压缩)

**文件**: `harness/context_compactor.py`

**职责**:
- 监控 Token 使用情况
- 阶梯降级压缩策略
- 保留关键信息

**压缩策略**:
```python
class CompactionStrategy(Enum):
    NONE      # 不压缩
    TRUNCATE  # 直接截断
    SUMMARY   # 生成摘要
    MIXED     # 混合策略（推荐）
```

**阶梯降级优先级**:
1. **SYSTEM**: System Prompt - 永不压缩
2. **AGENTS**: AGENTS.md 等规范
3. **TOOL_DEFS**: 工具定义
4. **RECENT**: 最近 N 轮对话
5. **MIDDLE**: 中间消息 → 摘要
6. **OLD**: 早期消息 → 丢弃

**设计亮点**:
- **Token 估算**: `SimpleTokenCounter` 中英文混合估算
- **Tiktoken 支持**: 可选精确计数
- **自动触发**: `StreamingCompactor` 持续监控自动压缩
- **渐进式压缩**: 避免一次性丢失过多信息

---

## 🔄 数据流程图

```
用户输入
    │
    ▼
┌─────────────────────────────────────┐
│ 1. Prompt Builder 组装 System Prompt│
│    - 加载身份、规范、记忆           │
│    - 注入工作目录、时间             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 2. Main Loop 初始化                  │
│    - 创建 LoopStats                 │
│    - 初始化消息列表                 │
└──────────────┬──────────────────────┘
               │
               ▼
    ┌──────────────────────────┐
    │ 3. Think (LLM 调用)      │
    │    ├─ Provider.complete()│
    │    ├─ Token 统计         │
    │    └─ 检查预算           │
    └──────────────┬───────────┘
                   │
            ┌──────┴──────┐
            │ 无工具调用? │──是──► 返回结果
            └──────┬──────┘
                   │否
                   ▼
    ┌──────────────────────────┐
    │ 4. Act (工具执行)         │
    │    ├─ Middleware 拦截    │
    │    ├─ 并发执行工具        │
    │    └─ 收集结果            │
    └──────────────┬───────────┘
                   │
                   ▼
    ┌──────────────────────────┐
    │ 5. Observe (结果追加)     │
    │    ├─ 追加到消息历史     │
    │    ├─ Session 持久化     │
    │    └─ Tracer 记录        │
    └──────────────┬───────────┘
                   │
    ┌──────────────▼───────────┐
    │ 6. Context Compaction     │
    │    ├─ 估算 Token 使用     │
    │    └─ 必要时压缩         │
    └──────────────┬───────────┘
                   │
            ┌──────┴──────┐
            │ 达到轮次?  │──是──► 终止
            └──────┬──────┘
                   │否
                   ▼
            ┌───────────┐
            │ 回到步骤3 │
            └───────────┘
```

---

## 🛡️ 安全设计

### 1. 中间件拦截
- 危险命令正则匹配
- 敏感信息过滤（密码、API Key）
- 速率限制

### 2. 人工审批
- 控制台审批（测试用）
- 飞书审批集成
- 多级审批级别（manual/admin）

### 3. 物理隔离
- 每个 Session 独立目录
- 无跨 Session 数据访问

---

## 📊 可观测性设计

### 1. 成本追踪
- 按模型计费
- Token 消耗统计
- 实时回调通知

### 2. 链路追踪
- 完整执行链路
- 性能瓶颈分析
- 错误路径复盘

### 3. 会话历史
- JSONL 持久化
- 可查询、可回放
- 工件管理

---

## 🚀 性能优化

### 1. 并发工具执行
- `asyncio.gather()` 并行执行
- `Semaphore` 控制并发数

### 2. 内存友好
- 迭代器读取消息
- JSONL 流式写入
- 按需压缩上下文

### 3. Token 控制
- 预算预警
- 渐进式压缩
- 摘要生成用小模型

---

## 📝 使用示例

### 基础使用

```python
from harness.main_loop import MainLoop
from harness.provider.factory import create_provider
from harness.tools.registry import ToolRegistry
from harness.prompt.builder import PromptBuilder

# 1. 初始化组件
provider = create_provider("claude", api_key="...")
registry = ToolRegistry()
builder = PromptBuilder(workspace=".")

# 2. 注册工具
@registry.tool(description="读取文件")
async def read_file(path: str) -> str:
    with open(path) as f:
        return f.read()

# 3. 组装 Prompt
system_prompt = builder.load_agents_md().inject_datetime().build()

# 4. 创建 Main Loop
loop = MainLoop(
    provider=provider,
    tool_registry=registry,
    system_prompt=system_prompt,
    max_turns=50,
)

# 5. 注册事件
loop.on("token_update", lambda tokens, cost: print(f"Token: {tokens}, Cost: ${cost:.4f}"))
loop.on("tool_call", lambda name, args: print(f"Calling: {name}({args})"))

# 6. 执行
result = await loop.run("帮我分析当前项目结构")

print(f"Status: {result.status}")
print(f"Content: {result.content}")
print(f"Stats: {result.stats.to_dict()}")
```

### 带中间件和追踪

```python
from harness.middleware import MiddlewareManager, DangerousCommandDetector
from harness.tracer import Tracer

# 中间件
middleware = MiddlewareManager().setup_default()
middleware.chain.add(DangerousCommandDetector())

# 追踪
tracer = Tracer(storage_path=".workbuddy/traces")
trace_id = tracer.start_trace(session_id="session_123", user_message=user_input)

# Main Loop
loop = MainLoop(
    provider=provider,
    tool_registry=registry,
    tracer=tracer,
    cost_tracker=cost_tracker,
)

result = await loop.run(user_input)

# 结束追踪
trace = tracer.end_trace()
print(tracer.generate_report(trace))
```

---

## 🎓 学习建议

### 入门路径
1. **Main Loop**: 理解核心循环逻辑
2. **Provider**: 学习抽象层设计
3. **Tools**: 实现简单工具
4. **Session**: 理解持久化

### 进阶路径
1. **Middleware**: 自定义拦截器
2. **Tracer**: 分析执行链路
3. **Context Compactor**: 优化内存使用
4. **Subagent**: 任务委派模式

---

## 📚 参考

- 原课程: 《从 0 开始构建 Agent Harness》
- OpenClaw 团队
