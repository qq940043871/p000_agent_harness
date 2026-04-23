# harness/__init__.py
# OpenClaw Agent Harness - 核心模块

from .message import (
    Message,
    MessageRole,
    ToolCall,
    Conversation,
)

from .main_loop import MainLoop, StatefulMainLoop, LoopResult, LoopStatus, LoopStats
from .provider import (
    BaseProvider,
    LLMResponse,
    ToolCall,
    Usage,
    ClaudeProvider,
    OpenAICompatProvider,
    create_provider,
    load_provider_from_config,
    load_provider_from_yaml,
)
from .tools import (
    ToolRegistry,
    ToolDefinition,
    ToolResult,
    ToolNotFoundError,
    ToolExecutionError,
    EditTool,
)
from .prompt import PromptBuilder, PromptSection, build_system_prompt
from .session import Session, SessionManager, SessionStatus

# 第三章：上下文工程
from .context_compactor import (
    ContextCompactor,
    StreamingCompactor,
    CompactionConfig,
    CompactionStrategy,
    CompactionLevel,
    CompactionResult,
    format_compaction_warning,
)
from .memory_manager import (
    MemoryManager,
    MemoryEntry,
    MemoryType,
    TodoItem,
    create_memory_manager,
)

# 第四章：稳定性控制
from .system_reminders import (
    SystemReminder,
    LoopDetector,
    LoopDetectionConfig,
    LoopWarning,
    LoopType,
    ReminderStrategy,
    ConservativeStrategy,
    AggressiveStrategy,
    AdaptiveStrategy,
    format_loop_intervention,
)
from .middleware import (
    Middleware,
    MiddlewareChain,
    MiddlewarePhase,
    InterceptContext,
    InterceptResult,
    MiddlewareManager,
    DangerousCommandDetector,
    RateLimitMiddleware,
    ContentFilterMiddleware,
    LoggingMiddleware,
    ApprovalHandler,
    ConsoleApprovalHandler,
    FeishuApprovalHandler,
)

# 第五章：可观测性
from .cost_tracker import (
    CostTracker,
    TokenUsage,
    CostRecord,
    TurnCost,
    MODEL_PRICING,
    track_cost,
)
from .tracer import (
    Tracer,
    Trace,
    Span,
    SpanType,
    SpanStatus,
    OpenTelemetryExporter,
)
from .benchmark import (
    HarnessBenchmark,
    BenchmarkTask,
    BenchmarkResult,
    BenchmarkReport,
    StandardBenchmarks,
)

# 扩展测试套件
try:
    from .benchmark_suite import (
        FileOperationBenchmarks,
        CodeGenerationBenchmarks,
        DebuggingBenchmarks,
        MultiTurnBenchmarks,
        ToolCallBenchmarks,
        ContextWindowBenchmarks,
        BenchmarkSuiteConfig,
        BenchmarkRunner,
        BenchmarkPresets,
    )
except ImportError:
    pass

# Subagent 委派系统
from .subagent import (
    SubagentState,
    TaskPriority,
    DelegatedTask,
    SubagentResult,
    SubagentConfig,
    BaseSubagent,
    ExplorationSubagent,
    DebuggingSubagent,
    SubagentPool,
    TaskCoordinator,
)

# integrations
try:
    from .integrations.feishu import (
        FeishuBot,
        FeishuClient,
        FeishuConfig,
        FeishuMessage,
        AgentOpsFeishuBot,
        EventType,
    )
except ImportError:
    pass

try:
    from .integrations.coding import (
        CodingConfig,
        CodingTools,
        CodingWebhookHandler,
        CodingContext,
        CodingAgentMixin,
        register_coding_tools,
    )
except ImportError:
    pass

__version__ = "0.2.0"
__all__ = [
    # Message
    "Message",
    "MessageRole",
    "Conversation",
    # Main Loop
    "MainLoop",
    "StatefulMainLoop",
    "LoopResult",
    "LoopStatus",
    "LoopStats",
    # Provider
    "BaseProvider",
    "LLMResponse",
    "ToolCall",
    "Usage",
    "ClaudeProvider",
    "OpenAICompatProvider",
    "create_provider",
    "load_provider_from_config",
    "load_provider_from_yaml",
    # Tools
    "ToolRegistry",
    "ToolDefinition",
    "ToolResult",
    "ToolNotFoundError",
    "ToolExecutionError",
    "EditTool",
    # Prompt
    "PromptBuilder",
    "PromptSection",
    "build_system_prompt",
    # Session
    "Session",
    "SessionManager",
    "SessionStatus",
    # Context Compaction
    "ContextCompactor",
    "StreamingCompactor",
    "CompactionConfig",
    "CompactionStrategy",
    "CompactionLevel",
    "CompactionResult",
    "format_compaction_warning",
    # Memory Manager
    "MemoryManager",
    "MemoryEntry",
    "MemoryType",
    "TodoItem",
    "create_memory_manager",
    # System Reminders
    "SystemReminder",
    "LoopDetector",
    "LoopDetectionConfig",
    "LoopWarning",
    "LoopType",
    "ReminderStrategy",
    "ConservativeStrategy",
    "AggressiveStrategy",
    "AdaptiveStrategy",
    "format_loop_intervention",
    # Middleware
    "Middleware",
    "MiddlewareChain",
    "MiddlewarePhase",
    "InterceptContext",
    "InterceptResult",
    "MiddlewareManager",
    "DangerousCommandDetector",
    "RateLimitMiddleware",
    "ContentFilterMiddleware",
    "LoggingMiddleware",
    "ApprovalHandler",
    "ConsoleApprovalHandler",
    "FeishuApprovalHandler",
    # Cost Tracker
    "CostTracker",
    "TokenUsage",
    "CostRecord",
    "TurnCost",
    "MODEL_PRICING",
    "track_cost",
    # Tracer
    "Tracer",
    "Trace",
    "Span",
    "SpanType",
    "SpanStatus",
    "OpenTelemetryExporter",
    # Benchmark
    "HarnessBenchmark",
    "BenchmarkTask",
    "BenchmarkResult",
    "BenchmarkReport",
    "StandardBenchmarks",
    # Benchmark Suite
    "FileOperationBenchmarks",
    "CodeGenerationBenchmarks",
    "DebuggingBenchmarks",
    "MultiTurnBenchmarks",
    "ToolCallBenchmarks",
    "ContextWindowBenchmarks",
    "BenchmarkSuiteConfig",
    "BenchmarkRunner",
    "BenchmarkPresets",
    # Subagent
    "SubagentState",
    "TaskPriority",
    "DelegatedTask",
    "SubagentResult",
    "SubagentConfig",
    "BaseSubagent",
    "ExplorationSubagent",
    "DebuggingSubagent",
    "SubagentPool",
    "TaskCoordinator",
    # Coding Plan 集成
    "CodingConfig",
    "CodingTools",
    "CodingWebhookHandler",
    "CodingContext",
    "CodingAgentMixin",
    "register_coding_tools",
]
