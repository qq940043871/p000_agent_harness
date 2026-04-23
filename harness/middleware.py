"""
Middleware - 中间件拦截系统

功能：
- 命令拦截与审查
- 高危操作人工审批
- 请求/响应拦截
- 飞书审批流程集成
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


class MiddlewarePhase(Enum):
    """中间件执行阶段"""
    PRE_TOOL_CALL = auto()      # 工具调用前
    POST_TOOL_CALL = auto()     # 工具调用后
    PRE_LLM_CALL = auto()       # LLM 调用前
    POST_LLM_CALL = auto()      # LLM 调用后
    PRE_RESPONSE = auto()       # 返回响应前
    POST_RESPONSE = auto()      # 返回响应后


@dataclass
class InterceptContext:
    """拦截上下文"""
    phase: MiddlewarePhase
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: str = ""
    turn_count: int = 0
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: Any = None
    llm_messages: list[dict] | None = None
    llm_response: str | None = None
    user_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class InterceptResult:
    """拦截结果"""
    allowed: bool = True                    # 是否允许继续
    modified: bool = False                  # 是否被修改
    modified_value: Any = None              # 修改后的值
    reason: str = ""                        # 原因
    suggestions: list[str] = field(default_factory=list)
    requires_approval: bool = False         # 是否需要人工审批
    approval_id: str | None = None          # 审批 ID


class Middleware(ABC):
    """中间件基类"""

    def __init__(self, name: str | None = None):
        self.name = name or self.__class__.__name__

    @abstractmethod
    async def intercept(self, ctx: InterceptContext) -> InterceptResult:
        """执行拦截逻辑"""
        pass

    def should_run(self, ctx: InterceptContext) -> bool:
        """判断是否应该运行"""
        return True


# ==================== 危险命令检测器 ====================

@dataclass
class DangerousCommand:
    """危险命令定义"""
    pattern: str | re.Pattern
    severity: int                          # 1-5
    description: str
    requires_approval: bool = True
    approval_level: str = "manual"          # auto, manual, admin


class DangerousCommandDetector(Middleware):
    """
    危险命令检测器

    检测并拦截潜在的破坏性命令。
    """

    def __init__(self):
        super().__init__("DangerousCommandDetector")

        # 预定义危险命令
        self._dangerous_commands: list[DangerousCommand] = [
            # 文件操作
            DangerousCommand(
                pattern=r"rm\s+-rf\s+/|del\s+/[A-Z]:\\|rmdir\s+/",
                severity=5,
                description="根目录删除命令",
                requires_approval=True,
                approval_level="admin",
            ),
            DangerousCommand(
                pattern=r"rm\s+-rf\s+\*\s*$|del\s+/S\s+/Q\s+\*|rm\s+-rf\s+\.",
                severity=4,
                description="批量删除命令",
                requires_approval=True,
                approval_level="manual",
            ),
            DangerousCommand(
                pattern=r"chmod\s+-R\s+777\s+/|icacls.*Full\s+Control",
                severity=3,
                description="权限提升命令",
                requires_approval=True,
            ),

            # 系统操作
            DangerousCommand(
                pattern=r"shutdown|reboot|init\s+0|systemctl\s+stop",
                severity=5,
                description="系统关机/重启命令",
                requires_approval=True,
                approval_level="admin",
            ),
            DangerousCommand(
                pattern=r"kill\s+-9\s+1|killall\s+-9\s+systemd",
                severity=5,
                description="杀死系统进程",
                requires_approval=True,
                approval_level="admin",
            ),

            # 网络操作
            DangerousCommand(
                pattern=r"iptables\s+-F|ufw\s+disable|netsh\s+advfirewall\s+off",
                severity=4,
                description="关闭防火墙",
                requires_approval=True,
                approval_level="admin",
            ),
            DangerousCommand(
                pattern=r":\(\)\{\s*:\|:\s&\s*\}\;:|curl\s+.*\|sh|wget.*\|sh",
                severity=5,
                description="远程代码执行",
                requires_approval=True,
                approval_level="admin",
            ),

            # 数据操作
            DangerousCommand(
                pattern=r"drop\s+database|truncate\s+table|delete\s+from\s+\w+\s+where",
                severity=4,
                description="数据库删除操作",
                requires_approval=True,
            ),
            DangerousCommand(
                pattern=r"format\s+[A-Z]:|mkfs\.",
                severity=5,
                description="格式化命令",
                requires_approval=True,
                approval_level="admin",
            ),

            # 敏感信息
            DangerousCommand(
                pattern=r"eval.*\$\(|exec.*\$\(|os\.system\(",
                severity=4,
                description="动态代码执行",
                requires_approval=True,
            ),
        ]

    def add_command(
        self,
        pattern: str,
        severity: int,
        description: str,
        requires_approval: bool = True,
    ) -> None:
        """添加危险命令规则"""
        self._dangerous_commands.append(DangerousCommand(
            pattern=re.compile(pattern) if isinstance(pattern, str) else pattern,
            severity=severity,
            description=description,
            requires_approval=requires_approval,
        ))

    async def intercept(self, ctx: InterceptContext) -> InterceptResult:
        """检测危险命令"""
        # 只检查工具调用
        if ctx.phase != MiddlewarePhase.PRE_TOOL_CALL:
            return InterceptResult()

        if not ctx.tool_args:
            return InterceptResult()

        # 检查工具参数
        args_str = str(ctx.tool_args)

        for cmd in self._dangerous_commands:
            pattern = cmd.pattern if isinstance(cmd.pattern, re.Pattern) else re.compile(cmd.pattern)

            if pattern.search(args_str):
                return InterceptResult(
                    allowed=False,
                    modified=False,
                    reason=f"危险命令检测: {cmd.description}",
                    requires_approval=cmd.requires_approval,
                    suggestions=[
                        f"命令 '{cmd.description}' 被拦截",
                        "如果必须执行，请联系管理员获取审批",
                        "建议：使用更安全的替代方案",
                    ]
                )

        return InterceptResult()


# ==================== 审批系统 ====================

@dataclass
class ApprovalRequest:
    """审批请求"""
    id: str
    requester: str
    action: str
    details: dict[str, Any]
    severity: int
    status: str = "pending"          # pending, approved, rejected
    requested_at: str = field(default_factory=lambda: datetime.now().isoformat())
    resolved_at: str | None = None
    resolved_by: str | None = None
    comment: str = ""


class ApprovalHandler(ABC):
    """审批处理器基类"""

    @abstractmethod
    async def request_approval(
        self,
        action: str,
        details: dict[str, Any],
        severity: int,
    ) -> str:
        """
        请求审批

        Returns:
            审批请求 ID
        """
        pass

    @abstractmethod
    async def check_approval(self, approval_id: str) -> bool:
        """
        检查审批状态

        Returns:
            是否已批准
        """
        pass


class ConsoleApprovalHandler(ApprovalHandler):
    """控制台审批处理器（测试用）"""

    def __init__(self):
        self._pending_requests: dict[str, ApprovalRequest] = {}

    async def request_approval(
        self,
        action: str,
        details: dict[str, Any],
        severity: int,
    ) -> str:
        import uuid
        request_id = f"approval_{uuid.uuid4().hex[:8]}"

        request = ApprovalRequest(
            id=request_id,
            requester="agent",
            action=action,
            details=details,
            severity=severity,
        )

        self._pending_requests[request_id] = request

        print(f"\n{'='*60}")
        print(f"⚠️  审批请求 #{request_id}")
        print(f"动作: {action}")
        print(f"详情: {details}")
        print(f"严重级别: {'🔴' * severity}")
        print(f"{'='*60}")
        print("请在下方输入 'approve' 或 'reject':")

        return request_id

    async def check_approval(self, approval_id: str) -> bool:
        # 在实际实现中，这里应该轮询或等待通知
        # 简化版本：检查内存中的结果
        if approval_id in self._pending_requests:
            request = self._pending_requests[approval_id]
            return request.status == "approved"
        return False

    def approve(self, approval_id: str, comment: str = "") -> bool:
        """批准请求（供外部调用）"""
        if approval_id in self._pending_requests:
            request = self._pending_requests[approval_id]
            request.status = "approved"
            request.resolved_at = datetime.now().isoformat()
            request.comment = comment
            return True
        return False

    def reject(self, approval_id: str, comment: str = "") -> bool:
        """拒绝请求（供外部调用）"""
        if approval_id in self._pending_requests:
            request = self._pending_requests[approval_id]
            request.status = "rejected"
            request.resolved_at = datetime.now().isoformat()
            request.comment = comment
            return True
        return False


class FeishuApprovalHandler(ApprovalHandler):
    """
    飞书审批处理器

    集成飞书审批流程。
    """

    def __init__(
        self,
        feishu_client: Any = None,
        approval_template_id: str = "",
    ):
        self.client = feishu_client
        self.template_id = approval_template_id
        self._cache: dict[str, ApprovalRequest] = {}

    async def request_approval(
        self,
        action: str,
        details: dict[str, Any],
        severity: int,
    ) -> str:
        import uuid
        request_id = f"feishu_{uuid.uuid4().hex[:8]}"

        request = ApprovalRequest(
            id=request_id,
            requester="agent",
            action=action,
            details=details,
            severity=severity,
        )

        self._cache[request_id] = request

        # 实际实现中，这里会调用飞书审批 API
        # await self.client.approval.create(...)

        print(f"飞书审批请求已创建: #{request_id}")

        return request_id

    async def check_approval(self, approval_id: str) -> bool:
        # 实际实现中，这里会查询飞书审批状态
        if approval_id in self._cache:
            return self._cache[approval_id].status == "approved"
        return False


# ==================== 中间件链 ====================

class MiddlewareChain:
    """
    中间件链

    按顺序执行多个中间件，支持短路逻辑。
    """

    def __init__(self):
        self._middlewares: list[tuple[Middleware, list[MiddlewarePhase]]] = []

    def add(
        self,
        middleware: Middleware,
        phases: list[MiddlewarePhase] | None = None,
    ) -> "MiddlewareChain":
        """添加中间件"""
        self._middlewares.append((middleware, phases or list(MiddlewarePhase)))
        return self

    async def execute(self, ctx: InterceptContext) -> InterceptResult:
        """
        执行中间件链

        Returns:
            最后一个拦截结果
        """
        last_result = InterceptResult()

        for middleware, phases in self._middlewares:
            # 检查是否应该在当前阶段运行
            if ctx.phase not in phases:
                continue

            if not middleware.should_run(ctx):
                continue

            # 执行中间件
            result = await middleware.intercept(ctx)

            if not result.allowed:
                return result

            if result.modified:
                last_result = result

        return last_result


# ==================== 内置中间件 ===============


class RateLimitMiddleware(Middleware):
    """速率限制中间件"""

    def __init__(self, max_calls_per_minute: int = 60):
        super().__init__("RateLimit")
        self.max_calls = max_calls_per_minute
        self._calls: list[datetime] = []

    async def intercept(self, ctx: InterceptContext) -> InterceptResult:
        """检查速率限制"""
        from datetime import timedelta

        now = datetime.now()
        cutoff = now - timedelta(minutes=1)

        # 清理过期记录
        self._calls = [t for t in self._calls if t > cutoff]

        if len(self._calls) >= self.max_calls:
            return InterceptResult(
                allowed=False,
                reason=f"速率限制: 每分钟最多 {self.max_calls} 次调用",
                suggestions=["请稍后再试"],
            )

        self._calls.append(now)
        return InterceptResult()


class ContentFilterMiddleware(Middleware):
    """内容过滤中间件"""

    def __init__(self, blocked_patterns: list[str] | None = None):
        super().__init__("ContentFilter")
        self.blocked_patterns = blocked_patterns or [
            r"password\s*[=:]\s*\S+",
            r"api[_-]?key\s*[=:]\s*\S+",
            r"secret\s*[=:]\s*\S+",
            r"token\s*[=:]\s*\S+",
        ]

    async def intercept(self, ctx: InterceptContext) -> InterceptResult:
        """过滤敏感内容"""
        if ctx.tool_args:
            args_str = str(ctx.tool_args)
            for pattern in self.blocked_patterns:
                if re.search(pattern, args_str, re.IGNORECASE):
                    return InterceptResult(
                        allowed=False,
                        reason="检测到敏感信息",
                        suggestions=["请使用环境变量或配置文件管理敏感信息"],
                    )

        return InterceptResult()


class LoggingMiddleware(Middleware):
    """日志中间件"""

    def __init__(self, logger: Callable[[str], None] | None = None):
        super().__init__("Logging")
        self.logger = logger or print

    async def intercept(self, ctx: InterceptContext) -> InterceptResult:
        """记录日志"""
        log_entry = f"[{ctx.phase.name}] {ctx.tool_name or 'N/A'}: {ctx.tool_args}"
        self.logger(log_entry)
        return InterceptResult()


# ==================== Middleware Manager ====================

class MiddlewareManager:
    """
    中间件管理器

    统一管理所有中间件的执行。
    """

    def __init__(self):
        self.chain = MiddlewareChain()
        self.approval_handler: ApprovalHandler | None = None
        self._pending_approvals: dict[str, bool] = {}

    def setup_default(self) -> "MiddlewareManager":
        """设置默认中间件链"""
        # 按顺序添加
        self.chain.add(LoggingMiddleware())
        self.chain.add(RateLimitMiddleware())
        self.chain.add(ContentFilterMiddleware())
        self.chain.add(DangerousCommandDetector())
        return self

    def set_approval_handler(self, handler: ApprovalHandler) -> None:
        """设置审批处理器"""
        self.approval_handler = handler

    async def process(
        self,
        phase: MiddlewarePhase,
        **context_kwargs,
    ) -> InterceptResult:
        """处理中间件链"""
        ctx = InterceptContext(phase=phase, **context_kwargs)
        result = await self.chain.execute(ctx)

        # 如果需要审批
        if result.requires_approval and self.approval_handler:
            approval_id = await self.approval_handler.request_approval(
                action=result.reason,
                details=context_kwargs,
                severity=3,
            )
            result.approval_id = approval_id

        return result

    async def pre_tool_call(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        **kwargs,
    ) -> InterceptResult:
        """工具调用前拦截"""
        return await self.process(
            MiddlewarePhase.PRE_TOOL_CALL,
            tool_name=tool_name,
            tool_args=tool_args,
            **kwargs,
        )

    async def post_tool_call(
        self,
        tool_name: str,
        tool_result: Any,
        **kwargs,
    ) -> InterceptResult:
        """工具调用后拦截"""
        return await self.process(
            MiddlewarePhase.POST_TOOL_CALL,
            tool_name=tool_name,
            tool_result=tool_result,
            **kwargs,
        )
