"""
飞书集成模块 - Feishu/Lark Integration

功能：
- 飞书机器人事件流处理
- 消息接收与回复
- 审批流程集成
- AgentOps 助手
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable
from starlette.datastructures import Headers


class EventType(Enum):
    """飞书事件类型"""
    MESSAGE_RECEIVE = "im.message.receive_v1"
    MESSAGE_REPLY = "im.message.reply_v1"
    APPROVAL_CREATE = "approval.v4.instance.create"
    APPROVAL_APPROVE = "approval.v4.instance.approve"
    APPROVAL_REJECT = "approval.v4.instance.reject"


@dataclass
class FeishuMessage:
    """飞书消息"""
    msg_id: str = ""
    msg_type: str = ""
    content: str = ""
    chat_id: str = ""
    sender_id: str = ""
    sender_name: str = ""
    create_time: str = ""

    # 消息内容解析
    @property
    def text(self) -> str:
        """获取文本内容"""
        try:
            data = json.loads(self.content)
            return data.get("text", "")
        except (json.JSONDecodeError, TypeError):
            return self.content

    @property
    def is_at(self) -> bool:
        """是否@机器人"""
        try:
            data = json.loads(self.content)
            mentions = data.get("mentions", [])
            return any(m.get("key") == "@_user_1" for m in mentions)
        except (json.JSONDecodeError, TypeError):
            return False


@dataclass
class FeishuConfig:
    """飞书配置"""
    app_id: str = ""
    app_secret: str = ""
    verification_token: str = ""
    encrypt_key: str = ""

    # Webhook 配置
    webhook_url: str = ""

    # 长连接配置
    use_long_conn: bool = True

    # 审批配置
    approval_template_id: str = ""


class FeishuClient:
    """
    飞书 API 客户端

    支持：
    - 消息发送
    - 审批流程
    - 长连接 WebSocket
    """

    def __init__(self, config: FeishuConfig):
        self.config = config
        self._tenant_access_token: str | None = None
        self._token_expires_at: float = 0

    async def get_access_token(self) -> str:
        """获取 tenant_access_token"""
        if self._tenant_access_token and time.time() < self._token_expires_at:
            return self._tenant_access_token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        data = {
            "app_id": self.config.app_id,
            "app_secret": self.config.app_secret,
        }

        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data)
            result = response.json()

            if result.get("code") != 0:
                raise Exception(f"获取 token 失败: {result}")

            self._tenant_access_token = result["tenant_access_token"]
            self._token_expires_at = time.time() + result.get("expire", 7200) - 300

            return self._tenant_access_token

    async def send_message(
        self,
        receive_id: str,
        msg_type: str = "text",
        content: dict | str = None,
    ) -> dict:
        """发送消息"""
        if content is None:
            content = {}
        if isinstance(content, str):
            content = {"text": content}

        token = await self.get_access_token()

        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        params = {"receive_id": receive_id}

        payload = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": json.dumps(content) if isinstance(content, dict) else content,
        }

        import httpx
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, params=params, json=payload, headers=headers)
            return response.json()

    async def reply_message(
        self,
        message_id: str,
        msg_type: str = "text",
        content: dict | str = None,
    ) -> dict:
        """回复消息"""
        if content is None:
            content = {}
        if isinstance(content, str):
            content = {"text": content}

        token = await self.get_access_token()

        url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"

        payload = {
            "msg_type": msg_type,
            "content": json.dumps(content) if isinstance(content, dict) else content,
        }

        import httpx
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            return response.json()


class FeishuBot:
    """
    飞书机器人

    处理飞书事件和消息。
    """

    def __init__(
        self,
        config: FeishuConfig,
        agent_executor: Callable | None = None,
    ):
        self.client = FeishuClient(config)
        self.config = config
        self.agent_executor = agent_executor

        # 事件处理器
        self._handlers: dict[EventType, Callable] = {}

        # 会话管理
        self._sessions: dict[str, dict] = {}

    def on_message(self, handler: Callable[[FeishuMessage], Any]):
        """注册消息处理器"""
        self._handlers[EventType.MESSAGE_RECEIVE] = handler

    def on_approval(self, handler: Callable[[dict], Any]):
        """注册审批处理器"""
        self._handlers[EventType.APPROVAL_CREATE] = handler

    async def handle_event(self, event_data: dict) -> dict:
        """处理飞书事件"""
        event_type = event_data.get("type", "")

        # 查找处理器
        try:
            handler = self._handlers.get(EventType(event_type))
        except ValueError:
            return {"code": 0, "msg": "event type not handled"}

        if not handler:
            return {"code": 0, "msg": "no handler"}

        # 处理事件
        try:
            if event_type == EventType.MESSAGE_RECEIVE.value:
                message = self._parse_message(event_data)
                result = await handler(message)
            else:
                result = await handler(event_data.get("event", {}))

            return {"code": 0, "msg": "success", "data": result}

        except Exception as e:
            return {"code": 1, "msg": str(e)}

    def _parse_message(self, event_data: dict) -> FeishuMessage:
        """解析消息"""
        event = event_data.get("event", {})

        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {})
        sender_id_str = sender_id.get("open_id", sender_id.get("user_id", ""))

        return FeishuMessage(
            msg_id=event.get("message", {}).get("message_id", ""),
            msg_type=event.get("message", {}).get("msg_type", ""),
            content=event.get("message", {}).get("content", "{}"),
            chat_id=event.get("message", {}).get("chat_id", ""),
            sender_id=sender_id_str,
            sender_name=sender.get("sender_name", ""),
            create_time=event.get("message", {}).get("create_time", ""),
        )

    async def process_message(self, message: FeishuMessage) -> str:
        """处理用户消息"""
        # 获取或创建会话
        session_id = message.chat_id
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "created_at": datetime.now().isoformat(),
                "turns": 0,
            }

        self._sessions[session_id]["turns"] += 1

        # 调用 Agent
        if self.agent_executor:
            result = await self.agent_executor(message.text)
            return result.get("output", str(result))

        return "您好，我是 AgentOps 助手。请问有什么可以帮助您的？"

    def verify_webhook(self, timestamp: str, nonce: str, signature: str) -> bool:
        """验证 Webhook 签名"""
        if not self.config.encrypt_key:
            return True

        # 构建签名
        string_to_sign = f"{timestamp}{nonce}{self.config.encrypt_key}"
        sign = hashlib.sha256(string_to_sign.encode()).hexdigest()

        return sign == signature


class AgentOpsFeishuBot(FeishuBot):
    """
    AgentOps 飞书机器人

    专门用于 Agent 操作和审批流程。
    """

    def __init__(self, config: FeishuConfig, harness: Any = None):
        super().__init__(config)
        self.harness = harness

        # 审批队列
        self._pending_approvals: dict[str, dict] = {}

    async def handle_agentops_command(self, message: FeishuMessage) -> str:
        """处理 AgentOps 命令"""
        text = message.text.strip()

        # 命令解析
        if text.startswith("/help"):
            return self._get_help_text()

        elif text.startswith("/status"):
            return await self._get_status_text()

        elif text.startswith("/approve "):
            return await self._handle_approve(text)

        elif text.startswith("/reject "):
            return await self._handle_reject(text)

        elif text.startswith("/logs "):
            return await self._get_logs(text)

        elif text.startswith("/cost"):
            return await self._get_cost_report()

        else:
            # 转发给 Agent
            return await self.process_message(message)

    def _get_help_text(self) -> str:
        """获取帮助文本"""
        return """
🤖 **AgentOps 助手命令**

可用命令：
- `/help` - 显示此帮助
- `/status` - 查看 Agent 状态
- `/approve <审批ID>` - 批准操作
- `/reject <审批ID> <原因>` - 拒绝操作
- `/logs <任务ID>` - 查看任务日志
- `/cost` - 查看成本报告

也可以直接发送消息，我会转交给 Agent 处理。
        """.strip()

    async def _get_status_text(self) -> str:
        """获取状态文本"""
        if not self.harness:
            return "Agent 未连接"

        stats = {
            "session_count": len(self._sessions),
            "pending_approvals": len(self._pending_approvals),
            "total_turns": sum(s["turns"] for s in self._sessions.values()),
        }

        return f"""
📊 **AgentOps 状态**

- 活跃会话: {stats['session_count']}
- 待审批: {stats['pending_approvals']}
- 总对话轮次: {stats['total_turns']}

Agent 状态: ✅ 运行中
        """.strip()

    async def _handle_approve(self, command: str) -> str:
        """处理批准命令"""
        approval_id = command.replace("/approve", "").strip()

        if approval_id not in self._pending_approvals:
            return f"❌ 未找到审批请求: {approval_id}"

        approval = self._pending_approvals[approval_id]
        approval["status"] = "approved"
        approval["resolved_at"] = datetime.now().isoformat()

        return f"✅ 已批准审批请求: {approval_id}\n原因: {approval.get('reason', 'N/A')}"

    async def _handle_reject(self, command: str) -> str:
        """处理拒绝命令"""
        parts = command.replace("/reject", "").strip().split(" ", 1)
        approval_id = parts[0]
        reason = parts[1] if len(parts) > 1 else "未提供原因"

        if approval_id not in self._pending_approvals:
            return f"❌ 未找到审批请求: {approval_id}"

        approval = self._pending_approvals[approval_id]
        approval["status"] = "rejected"
        approval["resolved_at"] = datetime.now().isoformat()
        approval["reject_reason"] = reason

        return f"❌ 已拒绝审批请求: {approval_id}\n原因: {reason}"

    async def _get_logs(self, command: str) -> str:
        """获取日志"""
        # 简化实现
        return "📋 日志功能开发中..."

    async def _get_cost_report(self) -> str:
        """获取成本报告"""
        if not self.harness:
            return "无法获取成本报告"

        # 假设 harness 有 cost_tracker
        tracker = getattr(self.harness, "cost_tracker", None)
        if tracker:
            return tracker.generate_report()

        return "成本追踪器未初始化"


# ==================== Starlette Webhook Handler ====================

from starlette.requests import Request
from starlette.responses import JSONResponse


async def feishu_webhook_handler(request: Request, bot: FeishuBot) -> JSONResponse:
    """
    飞书 Webhook 处理器

    用于 FastAPI/Starlette 应用。
    """
    body = await request.json()

    # 验证签名
    timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
    nonce = request.headers.get("X-Lark-Request-Nonce", "")
    signature = request.headers.get("X-Lark-Signature", "")

    if not bot.verify_webhook(timestamp, nonce, signature):
        return JSONResponse({"code": 1, "msg": "signature verification failed"})

    # 处理事件
    result = await bot.handle_event(body)

    return JSONResponse(result)


# ==================== FastAPI 集成示例 ====================

def create_feishu_app(
    config: FeishuConfig,
    harness: Any = None,
) -> Any:
    """创建 FastAPI 应用（可选依赖）"""
    try:
        from fastapi import FastAPI
    except ImportError:
        print("请安装 fastapi: pip install fastapi")
        return None

    app = FastAPI(title="AgentOps Feishu Bot")
    bot = AgentOpsFeishuBot(config, harness)

    @app.post("/webhook/feishu")
    async def webhook(request: Request):
        return await feishu_webhook_handler(request, bot)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
