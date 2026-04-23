"""
飞书审批模板集 - Feishu Approval Templates

包含多种审批场景模板：
- 文件操作审批
- 命令执行审批
- 外部 API 调用审批
- 敏感数据访问审批
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ApprovalType(Enum):
    """审批类型"""
    # 文件操作
    FILE_CREATE = "file_create"
    FILE_DELETE = "file_delete"
    FILE_MODIFY = "file_modify"

    # 命令执行
    COMMAND_EXECUTE = "command_execute"
    SHELL_COMMAND = "shell_command"

    # 外部交互
    EXTERNAL_API = "external_api"
    WEBHOOK_SEND = "webhook_send"

    # 敏感操作
    SECRET_ACCESS = "secret_access"
    CONFIG_CHANGE = "config_change"
    USER_DATA_ACCESS = "user_data_access"

    # 自定义
    CUSTOM = "custom"


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"        # 低风险，自动批准
    MEDIUM = "medium" # 中风险，需确认
    HIGH = "high"     # 高风险，需审批
    CRITICAL = "critical"  # 极高风险，需多重审批


@dataclass
class ApprovalTemplate:
    """审批模板"""
    type: ApprovalType
    name: str
    description: str
    risk_level: RiskLevel

    # 审批流程配置
    approvers: list[str] = field(default_factory=list)  # 审批人列表
    approval_chain: list[str] = field(default_factory=list)  # 多级审批链
    auto_approve_threshold: int = 1  # 自动批准的通过人数

    # 消息模板
    request_message_template: str = ""
    approval_message_template: str = ""
    rejection_message_template: str = ""

    # 约束条件
    max_retry_count: int = 3
    timeout_seconds: int = 300
    require_reason: bool = True

    # 上下文字段
    context_fields: list[str] = field(default_factory=list)


@dataclass
class ApprovalRequest:
    """审批请求"""
    id: str
    template_type: ApprovalType
    risk_level: RiskLevel

    # 请求信息
    requester_id: str = ""
    requester_name: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 操作详情
    action: str = ""
    target: str = ""  # 操作目标（文件路径、命令等）
    details: dict = field(default_factory=dict)

    # 审批状态
    status: str = "pending"  # pending, approved, rejected, cancelled, timeout
    approvals: list[dict] = field(default_factory=list)

    # 结果
    reason: str = ""
    resolved_at: str | None = None

    def to_message(self, template: ApprovalTemplate) -> str:
        """生成审批消息"""
        risk_emoji = {
            RiskLevel.LOW: "🟢",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.HIGH: "🟠",
            RiskLevel.CRITICAL: "🔴",
        }

        return template.request_message_template.format(
            risk_icon=risk_emoji.get(self.risk_level, "⚪"),
            requester=self.requester_name,
            action=self.action,
            target=self.target,
            details=json.dumps(self.details, ensure_ascii=False, indent=2),
            reason_prompt="请输入审批原因：" if template.require_reason else "",
        )


# ==================== 审批模板定义 ====================

class ApprovalTemplates:
    """审批模板集合"""

    @staticmethod
    def get_all() -> list[ApprovalTemplate]:
        return [
            *ApprovalTemplates.get_file_templates(),
            *ApprovalTemplates.get_command_templates(),
            *ApprovalTemplates.get_external_templates(),
            *ApprovalTemplates.get_security_templates(),
        ]

    @staticmethod
    def get_file_templates() -> list[ApprovalTemplate]:
        """文件操作审批模板"""
        return [
            ApprovalTemplate(
                type=ApprovalType.FILE_CREATE,
                name="创建文件",
                description="Agent 申请创建新文件",
                risk_level=RiskLevel.LOW,
                require_reason=False,
                request_message_template="""
🤖 **Agent 文件创建请求**

{risk_icon} 风险等级: {risk_level.value}

👤 请求者: {requester}
📄 操作: 创建文件
📁 目标: `{target}`

详情:
```
{details}
```

{risk_icon} 此操作风险较低，可直接批准。
                """,
                approval_message_template="✅ 文件创建已批准",
                rejection_message_template="❌ 文件创建已拒绝",
            ),
            ApprovalTemplate(
                type=ApprovalType.FILE_DELETE,
                name="删除文件",
                description="Agent 申请删除文件",
                risk_level=RiskLevel.HIGH,
                require_reason=True,
                context_fields=["file_size", "last_modified", "file_type"],
                request_message_template="""
🔴 **⚠️ Agent 文件删除请求 - 高风险操作**

{risk_icon} 风险等级: {risk_level.value}

👤 请求者: {requester}
🗑️ 操作: 删除文件
📁 目标: `{target}`

⚠️ **警告**: 此操作不可逆！

文件信息:
```
{details}
```

请仔细确认后再批准。
{reason_prompt}
                """,
                approval_message_template="✅ 文件删除已批准",
                rejection_message_template="❌ 文件删除已拒绝",
            ),
            ApprovalTemplate(
                type=ApprovalType.FILE_MODIFY,
                name="修改文件",
                description="Agent 申请修改现有文件",
                risk_level=RiskLevel.MEDIUM,
                require_reason=True,
                request_message_template="""
🟡 **Agent 文件修改请求**

{risk_icon} 风险等级: {risk_level.value}

👤 请求者: {requester}
✏️ 操作: 修改文件
📁 目标: `{target}`

修改详情:
```
{details}
```

{reason_prompt}
                """,
                approval_message_template="✅ 文件修改已批准",
                rejection_message_template="❌ 文件修改已拒绝",
            ),
        ]

    @staticmethod
    def get_command_templates() -> list[ApprovalTemplate]:
        """命令执行审批模板"""
        return [
            ApprovalTemplate(
                type=ApprovalType.COMMAND_EXECUTE,
                name="执行命令",
                description="Agent 申请执行系统命令",
                risk_level=RiskLevel.HIGH,
                require_reason=True,
                context_fields=["command_type", "working_dir"],
                request_message_template="""
🟠 **⚠️ Agent 命令执行请求**

{risk_icon} 风险等级: {risk_level.value}

👤 请求者: {requester}
💻 操作: 执行命令
🎯 目标: `{target}`

⚠️ **警告**: 将执行系统命令！

命令详情:
```
{details}
```

{reason_prompt}
                """,
                approval_message_template="✅ 命令执行已批准",
                rejection_message_template="❌ 命令执行已拒绝",
            ),
            ApprovalTemplate(
                type=ApprovalType.SHELL_COMMAND,
                name="Shell 命令",
                description="Agent 申请执行 Shell 命令",
                risk_level=RiskLevel.CRITICAL,
                approval_chain=["admin", "security"],
                auto_approve_threshold=2,
                request_message_template="""
🔴 **🚨 Agent Shell 命令请求 - 极高风险**

{risk_icon} 风险等级: {risk_level.value}

👤 请求者: {requester}
🖥️ 操作: 执行 Shell 命令
🎯 命令: `{target}`

🚨 **极度危险**: 将直接执行 Shell 命令！

命令详情:
```
{details}
```

⚠️ 需要多人审批确认
{reason_prompt}
                """,
                approval_message_template="✅ Shell 命令已批准",
                rejection_message_template="❌ Shell 命令已拒绝",
            ),
        ]

    @staticmethod
    def get_external_templates() -> list[ApprovalTemplate]:
        """外部交互审批模板"""
        return [
            ApprovalTemplate(
                type=ApprovalType.EXTERNAL_API,
                name="外部 API 调用",
                description="Agent 申请调用外部 API",
                risk_level=RiskLevel.MEDIUM,
                require_reason=True,
                context_fields=["api_endpoint", "http_method", "headers"],
                request_message_template="""
🟡 **Agent 外部 API 调用请求**

{risk_icon} 风险等级: {risk_level.value}

👤 请求者: {requester}
🌐 操作: 调用外部 API
🔗 端点: `{target}`

API 详情:
```
{details}
```

{reason_prompt}
                """,
                approval_message_template="✅ API 调用已批准",
                rejection_message_template="❌ API 调用已拒绝",
            ),
            ApprovalTemplate(
                type=ApprovalType.WEBHOOK_SEND,
                name="发送 Webhook",
                description="Agent 申请发送 Webhook 请求",
                risk_level=RiskLevel.MEDIUM,
                require_reason=True,
                context_fields=["webhook_url", "http_method", "payload"],
                request_message_template="""
🟡 **Agent Webhook 发送请求**

{risk_icon} 风险等级: {risk_level.value}

👤 请求者: {requester}
📨 操作: 发送 Webhook
🔗 URL: `{target}`

Webhook 详情:
```
{details}
```

{reason_prompt}
                """,
                approval_message_template="✅ Webhook 已发送",
                rejection_message_template="❌ Webhook 发送已拒绝",
            ),
        ]

    @staticmethod
    def get_security_templates() -> list[ApprovalTemplate]:
        """安全敏感操作审批模板"""
        return [
            ApprovalTemplate(
                type=ApprovalType.SECRET_ACCESS,
                name="访问密钥",
                description="Agent 申请访问敏感密钥",
                risk_level=RiskLevel.CRITICAL,
                approval_chain=["security", "admin"],
                auto_approve_threshold=2,
                require_reason=True,
                request_message_template="""
🔴 **🚨 Agent 密钥访问请求 - 极高风险**

{risk_icon} 风险等级: {risk_level.value}

👤 请求者: {requester}
🔐 操作: 访问敏感密钥
🔑 目标: `{target}`

⚠️ **警告**: 将访问敏感配置信息！

详情:
```
{details}
```

⚠️ 需要安全团队审批
{reason_prompt}
                """,
                approval_message_template="✅ 密钥访问已批准",
                rejection_message_template="❌ 密钥访问已拒绝",
            ),
            ApprovalTemplate(
                type=ApprovalType.CONFIG_CHANGE,
                name="配置修改",
                description="Agent 申请修改系统配置",
                risk_level=RiskLevel.HIGH,
                require_reason=True,
                context_fields=["config_key", "old_value", "new_value"],
                request_message_template="""
🟠 **⚠️ Agent 配置修改请求**

{risk_icon} 风险等级: {risk_level.value}

👤 请求者: {requester}
⚙️ 操作: 修改配置
🔧 目标: `{target}`

⚠️ 警告: 配置修改可能影响系统行为！

详情:
```
{details}
```

{reason_prompt}
                """,
                approval_message_template="✅ 配置修改已批准",
                rejection_message_template="❌ 配置修改已拒绝",
            ),
            ApprovalTemplate(
                type=ApprovalType.USER_DATA_ACCESS,
                name="用户数据访问",
                description="Agent 申请访问用户数据",
                risk_level=RiskLevel.HIGH,
                require_reason=True,
                context_fields=["data_type", "user_id", "access_reason"],
                request_message_template="""
🟠 **⚠️ Agent 用户数据访问请求**

{risk_icon} 风险等级: {risk_level.value}

👤 请求者: {requester}
👥 操作: 访问用户数据
📊 目标: `{target}`

⚠️ 警告: 将访问用户隐私数据！

详情:
```
{details}
```

{reason_prompt}
                """,
                approval_message_template="✅ 用户数据访问已批准",
                rejection_message_template="❌ 用户数据访问已拒绝",
            ),
        ]


# ==================== 审批管理器 ====================

class ApprovalManager:
    """审批管理器"""

    def __init__(self):
        self._templates: dict[ApprovalType, ApprovalTemplate] = {}
        self._pending_requests: dict[str, ApprovalRequest] = {}
        self._approval_history: list[ApprovalRequest] = []

        # 加载模板
        for template in ApprovalTemplates.get_all():
            self._templates[template.type] = template

    def get_template(self, approval_type: ApprovalType) -> ApprovalTemplate | None:
        """获取审批模板"""
        return self._templates.get(approval_type)

    def create_request(
        self,
        approval_type: ApprovalType,
        requester_id: str,
        requester_name: str,
        action: str,
        target: str,
        details: dict | None = None,
    ) -> ApprovalRequest:
        """创建审批请求"""
        template = self.get_template(approval_type)
        if not template:
            raise ValueError(f"Unknown approval type: {approval_type}")

        import uuid
        request_id = f"approval_{uuid.uuid4().hex[:12]}"

        request = ApprovalRequest(
            id=request_id,
            template_type=approval_type,
            risk_level=template.risk_level,
            requester_id=requester_id,
            requester_name=requester_name,
            action=action,
            target=target,
            details=details or {},
        )

        self._pending_requests[request_id] = request
        return request

    def approve(
        self,
        request_id: str,
        approver_id: str,
        approver_name: str,
        reason: str = "",
    ) -> bool:
        """审批通过"""
        if request_id not in self._pending_requests:
            return False

        request = self._pending_requests[request_id]
        template = self.get_template(request.template_type)

        # 记录审批
        request.approvals.append({
            "approver_id": approver_id,
            "approver_name": approver_name,
            "decision": "approved",
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        })

        # 检查是否通过
        if len(request.approvals) >= template.auto_approve_threshold:
            request.status = "approved"
            request.resolved_at = datetime.now().isoformat()
            request.reason = reason
            self._move_to_history(request)
            return True

        return False

    def reject(
        self,
        request_id: str,
        approver_id: str,
        approver_name: str,
        reason: str,
    ) -> bool:
        """审批拒绝"""
        if request_id not in self._pending_requests:
            return False

        request = self._pending_requests[request_id]

        # 记录拒绝
        request.approvals.append({
            "approver_id": approver_id,
            "approver_name": approver_name,
            "decision": "rejected",
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        })

        request.status = "rejected"
        request.resolved_at = datetime.now().isoformat()
        request.reason = reason
        self._move_to_history(request)
        return True

    def cancel(self, request_id: str) -> bool:
        """取消审批请求"""
        if request_id not in self._pending_requests:
            return False

        request = self._pending_requests[request_id]
        request.status = "cancelled"
        request.resolved_at = datetime.now().isoformat()
        self._move_to_history(request)
        return True

    def get_pending(self) -> list[ApprovalRequest]:
        """获取待审批请求"""
        return [
            r for r in self._pending_requests.values()
            if r.status == "pending"
        ]

    def get_by_requester(self, requester_id: str) -> list[ApprovalRequest]:
        """获取指定用户的审批请求"""
        return [
            r for r in self._pending_requests.values()
            if r.requester_id == requester_id
        ]

    def _move_to_history(self, request: ApprovalRequest) -> None:
        """移至历史记录"""
        if request.id in self._pending_requests:
            del self._pending_requests[request.id]
        self._approval_history.append(request)

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "pending_count": len(self.get_pending()),
            "total_history": len(self._approval_history),
            "approved_count": sum(1 for r in self._approval_history if r.status == "approved"),
            "rejected_count": sum(1 for r in self._approval_history if r.status == "rejected"),
        }


# ==================== 审批中间件集成 ====================

def create_approval_interceptor(
    approval_manager: ApprovalManager,
    feishu_client: Any = None,
) -> tuple[callable, callable]:
    """
    创建审批拦截器

    返回一个可调用对象，用于拦截需要审批的操作
    """
    import asyncio
    pending_approvals: dict[str, asyncio.Event] = {}

    async def intercept(
        operation_type: ApprovalType,
        requester_id: str,
        requester_name: str,
        action: str,
        target: str,
        details: dict | None = None,
    ) -> tuple[bool, str]:
        """
        拦截操作并等待审批

        Returns:
            (approved, reason)
        """
        # 创建审批请求
        request = approval_manager.create_request(
            operation_type,
            requester_id,
            requester_name,
            action,
            target,
            details,
        )

        # 发送到飞书（如果有配置）
        if feishu_client:
            template = approval_manager.get_template(operation_type)
            message = request.to_message(template)
            await feishu_client.send_message(
                receive_id=template.approvers[0] if template.approvers else "",
                content={"text": message},
            )

        # 等待审批结果
        event = asyncio.Event()
        pending_approvals[request.id] = event

        try:
            await asyncio.wait_for(
                event.wait(),
                timeout=300,
            )
        except asyncio.TimeoutError:
            request.status = "timeout"
            return False, "审批超时"

        finally:
            pending_approvals.pop(request.id, None)

        return request.status == "approved", request.reason

    async def notify_approval(
        request_id: str,
        approved: bool,
        approver_name: str,
        reason: str = "",
    ) -> None:
        """通知审批结果"""
        if request_id in pending_approvals:
            if approved:
                approval_manager.approve(
                    request_id,
                    approver_id="unknown",
                    approver_name=approver_name,
                    reason=reason,
                )
            else:
                approval_manager.reject(
                    request_id,
                    approver_id="unknown",
                    approver_name=approver_name,
                    reason=reason,
                )
            pending_approvals[request_id].set()

    return intercept, notify_approval


# 导出
__all__ = [
    "ApprovalType",
    "RiskLevel",
    "ApprovalTemplate",
    "ApprovalRequest",
    "ApprovalTemplates",
    "ApprovalManager",
    "create_approval_interceptor",
]
