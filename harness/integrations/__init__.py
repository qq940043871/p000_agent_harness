"""
集成模块 - Integrations

包含与外部系统的集成：
- 飞书机器人
- 审批模板
- Coding Plan (腾讯云 Coding / 火山引擎 Coding)
"""

from feishu import (
    FeishuBot,
    FeishuClient,
    FeishuConfig,
    FeishuMessage,
    AgentOpsFeishuBot,
    EventType,
)
from approval_templates import (
    ApprovalType,
    RiskLevel,
    ApprovalTemplate,
    ApprovalRequest,
    ApprovalTemplates,
    ApprovalManager,
    create_approval_interceptor,
)
from coding import (
    # 平台
    CodingPlatform,
    TencentCodingEndpoints,
    VolcEngineCodingEndpoints,
    # 配置
    CodingConfig,
    create_coding_config,
    # 工具
    CodingTools,
    CodingWebhookHandler,
    CodingToolResult,
    # Agent 集成
    CodingContext,
    CodingAgentMixin,
    register_coding_tools,
    # 枚举
    AuthType,
)

__all__ = [
    # 飞书集成
    "FeishuBot",
    "FeishuClient",
    "FeishuConfig",
    "FeishuMessage",
    "AgentOpsFeishuBot",
    "EventType",
    # 审批模板
    "ApprovalType",
    "RiskLevel",
    "ApprovalTemplate",
    "ApprovalRequest",
    "ApprovalTemplates",
    "ApprovalManager",
    "create_approval_interceptor",
    # Coding Plan 集成
    "CodingPlatform",
    "TencentCodingEndpoints",
    "VolcEngineCodingEndpoints",
    "CodingConfig",
    "create_coding_config",
    "CodingTools",
    "CodingWebhookHandler",
    "CodingToolResult",
    "CodingContext",
    "CodingAgentMixin",
    "register_coding_tools",
    "AuthType",
]
