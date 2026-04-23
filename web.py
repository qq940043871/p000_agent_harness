#!/usr/bin/env python3
"""
Agent Harness - Web 用户界面 (WEB UI)
基于 FastAPI + Vue.js 实现，支持实时流式输出

@author: OpenClaw Team
@date: 2026-04-22
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from harness import MainLoop, ToolRegistry, create_provider
from harness.cost_tracker import CostTracker
from harness.memory_manager import create_memory_manager
from harness.tracer import Tracer
import yaml


# ============================================================================
# FastAPI 应用
# ============================================================================

app = FastAPI(title="Agent Harness", version="1.0.0", description="OpenClaw Web UI")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件目录
BASE_DIR = Path(__file__).parent
web_dir = BASE_DIR / "web"
web_dir.mkdir(exist_ok=True)
static_dir = web_dir / "static"
static_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ============================================================================
# 配置加载
# ============================================================================


def load_config() -> dict:
    """加载配置文件（优先从 web.py 所在目录）"""
    config_file = BASE_DIR / "config.yaml"
    if config_file.exists():
        try:
            import yaml
            with open(config_file, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[WARN] 加载配置文件失败: {e}")
    return {}


def load_experts() -> list:
    """加载专家配置"""
    experts_file = BASE_DIR / "experts.yaml"
    if experts_file.exists():
        try:
            with open(experts_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data.get("experts", [])
        except Exception as e:
            print(f"[WARN] 加载专家配置失败: {e}")
    return []


# 全局专家列表
EXPERTS = load_experts()


# ============================================================================
# 会话管理
# ============================================================================


class SessionManager:
    """Web 会话管理器"""

    def __init__(self):
        self.sessions: dict[str, dict] = {}

    def create_session(self, config: dict, workspace_id: str = "default", workspace_path: str = "") -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "id": session_id,
            "config": config,
            "workspace_id": workspace_id,
            "workspace_path": workspace_path,
            "conversation": [],
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "cost": 0.0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "turns": 0,
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[dict]:
        """获取会话"""
        session = self.sessions.get(session_id)
        if session:
            session["last_activity"] = datetime.now().isoformat()
        return session

    def update_session(self, session_id: str, **kwargs):
        """更新会话"""
        if session_id in self.sessions:
            self.sessions[session_id].update(kwargs)

    def delete_session(self, session_id: str):
        """删除会话"""
        self.sessions.pop(session_id, None)

    def list_sessions(self) -> list[dict]:
        """列出所有会话"""
        return [
            {
                "id": s["id"],
                "workspace_id": s.get("workspace_id", "default"),
                "workspace_name": self._get_workspace_name(s.get("workspace_id", "default")),
                "created_at": s["created_at"],
                "last_activity": s["last_activity"],
                "message_count": len(s["conversation"]),
                "cost": s["cost"],
            }
            for s in self.sessions.values()
        ]
    
    def _get_workspace_name(self, workspace_id: str) -> str:
        """获取工作空间名称"""
        workspaces = load_workspaces()
        for ws in workspaces:
            if ws["id"] == workspace_id:
                return ws["name"]
        return "未知工作空间"


session_manager = SessionManager()


# ============================================================================
# WebSocket 连接管理器
# ============================================================================


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        self.active_connections.pop(session_id, None)

    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)


manager = ConnectionManager()


# ============================================================================
# API 路由
# ============================================================================


@app.get("/", response_class=HTMLResponse)
async def root():
    """主页"""
    return FileResponse(str(web_dir / "index.html"))


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok", "version": "1.0.0"}


# ============================================================================
# 工作空间管理
# ============================================================================

WORKSPACES_FILE = BASE_DIR / "workspaces.json"


def load_workspaces() -> list[dict]:
    """加载工作空间列表"""
    if WORKSPACES_FILE.exists():
        try:
            with open(WORKSPACES_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # 返回默认工作空间
    default_ws = {
        "id": "default",
        "name": "默认工作空间",
        "path": str(Path.cwd()),
        "description": "项目根目录",
        "created_at": datetime.now().isoformat(),
    }
    return [default_ws]


def save_workspaces(workspaces: list[dict]):
    """保存工作空间列表"""
    with open(WORKSPACES_FILE, "w", encoding="utf-8") as f:
        json.dump(workspaces, f, ensure_ascii=False, indent=2)


@app.get("/api/workspaces")
async def list_workspaces():
    """列出所有工作空间"""
    return load_workspaces()


@app.post("/api/workspaces")
async def create_workspace(request: Request):
    """创建新工作空间"""
    body = await request.json()
    name = body.get("name", "新工作空间")
    path = body.get("path", "")
    description = body.get("description", "")
    
    # 验证路径是否存在
    if path and Path(path).exists():
        workspaces = load_workspaces()
        new_ws = {
            "id": str(uuid.uuid4()),
            "name": name,
            "path": str(Path(path).resolve()),
            "description": description,
            "created_at": datetime.now().isoformat(),
        }
        workspaces.append(new_ws)
        save_workspaces(workspaces)
        return new_ws
    else:
        raise HTTPException(status_code=400, detail="路径不存在或无效")


@app.delete("/api/workspaces/{workspace_id}")
async def delete_workspace(workspace_id: str):
    """删除工作空间"""
    if workspace_id == "default":
        raise HTTPException(status_code=400, detail="不能删除默认工作空间")
    
    workspaces = load_workspaces()
    workspaces = [ws for ws in workspaces if ws["id"] != workspace_id]
    save_workspaces(workspaces)
    return {"status": "ok"}


@app.put("/api/workspaces/{workspace_id}")
async def update_workspace(workspace_id: str, request: Request):
    """更新工作空间"""
    body = await request.json()
    workspaces = load_workspaces()
    
    for ws in workspaces:
        if ws["id"] == workspace_id:
            ws["name"] = body.get("name", ws["name"])
            ws["description"] = body.get("description", ws["description"])
            save_workspaces(workspaces)
            return ws
    
    raise HTTPException(status_code=404, detail="工作空间不存在")


# ============================================================================
# 专家管理
# ============================================================================


@app.get("/api/experts")
async def list_experts():
    """列出所有专家（不含系统提示词）"""
    return [
        {
            "id": e["id"],
            "name": e["name"],
            "icon": e["icon"],
            "description": e["description"],
        }
        for e in EXPERTS
    ]


@app.get("/api/experts/{expert_id}/system-prompt")
async def get_expert_system_prompt(expert_id: str):
    """获取专家的系统提示词"""
    for e in EXPERTS:
        if e["id"] == expert_id:
            return {"system_prompt": e["system_prompt"]}
    raise HTTPException(status_code=404, detail="专家不存在")


# ============================================================================
# 会话管理
# ============================================================================


@app.post("/api/sessions")
async def create_session(request: Request):
    """创建新会话"""
    body = await request.json()
    config = body.get("config", {})
    workspace_id = body.get("workspace_id", "default")
    workspace_path = body.get("workspace_path", "")
    
    session_id = session_manager.create_session(config, workspace_id, workspace_path)
    return {"session_id": session_id}


@app.get("/api/sessions")
async def list_sessions():
    """列出所有会话"""
    return session_manager.list_sessions()


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """获取会话详情"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    session_manager.delete_session(session_id)
    return {"status": "ok"}


@app.get("/api/sessions/{session_id}/conversation")
async def get_conversation(session_id: str):
    """获取会话历史"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session["conversation"]


@app.post("/api/sessions/{session_id}/run")
async def run_agent(session_id: str, request: Request):
    """运行 Agent（非流式）"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    body = await request.json()
    prompt = body.get("prompt", "")
    workspace = body.get("workspace", str(Path.cwd()))
    system_prompt = body.get("system_prompt")

    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    try:
        result = await _run_agent_async(session, prompt, workspace, system_prompt)
        return {"result": result, "session": session}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket 端点 - 支持流式输出"""
    await manager.connect(session_id, websocket)

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")


            if action == "run":
                prompt = data.get("prompt", "")
                workspace = data.get("workspace", str(Path.cwd()))
                system_prompt = data.get("system_prompt")

                await manager.send_message(session_id, {
                    "type": "status",
                    "status": "running",
                    "message": "Agent 运行中..."
                })

                try:
                    result = await _run_agent_stream(session_id, prompt, workspace, system_prompt)
                except Exception as e:
                    await manager.send_message(session_id, {
                        "type": "error",
                        "message": str(e)
                    })

            elif action == "stop":
                # 停止逻辑
                await manager.send_message(session_id, {
                    "type": "status",
                    "status": "stopped",
                    "message": "Agent 已停止"
                })

    except WebSocketDisconnect:
        manager.disconnect(session_id)


# ============================================================================
# Agent 运行逻辑
# ============================================================================


async def _run_agent_async(session: dict, prompt: str, workspace: str, system_prompt: str = None) -> str:
    """异步运行 Agent"""
    from harness.tools.plugins import register_all_tools

    config = session["config"]
    yaml_config = load_config()

    # 创建组件
    provider_type = config.get("provider_type", "claude")
    
    # API Key 优先级：前端传入 > config.yaml > 环境变量
    api_key = config.get("api_key", "")
    if not api_key:
        # 尝试从 config.yaml 获取
        provider_key = provider_type.replace("-", "_")
        provider_key_dash = provider_type.replace("_", "-")
        provider_config = yaml_config.get("providers", {}).get(provider_key, {}) or \
                         yaml_config.get("providers", {}).get(provider_key_dash, {})
        api_key = provider_config.get("api_key", "")
        if not api_key:
            # 尝试环境变量
            env_vars = {
                "volcengine_plan": "VOLCANO_ENGINE_API_KEY",
                "volcengine-plan": "VOLCANO_ENGINE_API_KEY",
                "doubao": "DOUBAO_API_KEY",
                "claude": "ANTHROPIC_API_KEY",
                "openai": "OPENAI_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "qwen": "DASHSCOPE_API_KEY",
            }
            env_var = env_vars.get(provider_type)
            if env_var:
                api_key = os.environ.get(env_var, "")
    
    # 从 config.yaml 获取 model
    model = config.get("model", "")
    if not model:
        provider_key = provider_type.replace("-", "_")
        provider_key_dash = provider_type.replace("_", "-")
        provider_config = yaml_config.get("providers", {}).get(provider_key, {}) or \
                         yaml_config.get("providers", {}).get(provider_key_dash, {})
        model = provider_config.get("model", "")
    
    provider_kwargs = {
        "provider_type": provider_type,
        "api_key": api_key,
        "model": model,
    }
    
    # 只有 deepseek 和 openai 支持 base_url
    if provider_type in ("deepseek", "openai", "openai_compat"):
        base_url = config.get("base_url") or yaml_config.get("providers", {}).get(provider_type, {}).get("base_url", "")
        if base_url:
            provider_kwargs["base_url"] = base_url
    
    # 只有 claude 支持 model_kwargs
    if provider_type == "claude" and config.get("model_kwargs"):
        provider_kwargs["model_kwargs"] = config["model_kwargs"]
    
    provider = create_provider(**provider_kwargs)

    registry = ToolRegistry()
    register_all_tools(registry, workspace)

    # 可选组件
    cost_tracker = CostTracker()
    tracer = Tracer()
    memory = create_memory_manager(workspace)

    # 创建 MainLoop
    main_loop = MainLoop(
        provider=provider,
        tool_registry=registry,
        cost_tracker=cost_tracker,
        tracer=tracer,
        max_turns=config.get("max_turns", 50),
        system_prompt=system_prompt,
    )

    # 运行
    result = await main_loop.run(prompt)

    # 更新会话
    stats = cost_tracker.get_stats()
    session_manager.update_session(
        session["id"],
        conversation=session["conversation"] + [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": result.content},
        ],
        cost=stats["total_cost"],
        prompt_tokens=stats["total_prompt_tokens"],
        completion_tokens=stats["total_completion_tokens"],
    )

    # 返回可 JSON 序列化的结果
    return {
        "content": result.content,
        "status": result.status.value if hasattr(result.status, 'value') else str(result.status),
        "stats": result.stats.to_dict() if hasattr(result.stats, 'to_dict') else {},
    }


async def _run_agent_stream(session_id: str, prompt: str, workspace: str, system_prompt: str = None):
    """流式运行 Agent"""
    from harness.tools.plugins import register_all_tools

    session = session_manager.get_session(session_id)
    if not session:
        raise ValueError("Session not found")

    config = session["config"]
    yaml_config = load_config()

    # 创建组件
    provider_type = config.get("provider_type", "claude")
    
    # API Key 优先级：前端传入 > config.yaml > 环境变量
    api_key = config.get("api_key", "")
    if not api_key:
        # 尝试从 config.yaml 获取
        provider_key = provider_type.replace("-", "_")
        provider_key_dash = provider_type.replace("_", "-")
        provider_config = yaml_config.get("providers", {}).get(provider_key, {}) or \
                         yaml_config.get("providers", {}).get(provider_key_dash, {})
        api_key = provider_config.get("api_key", "")
        if not api_key:
            # 尝试环境变量
            env_vars = {
                "volcengine_plan": "VOLCANO_ENGINE_API_KEY",
                "volcengine-plan": "VOLCANO_ENGINE_API_KEY",
                "doubao": "DOUBAO_API_KEY",
                "claude": "ANTHROPIC_API_KEY",
                "openai": "OPENAI_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "qwen": "DASHSCOPE_API_KEY",
            }
            env_var = env_vars.get(provider_type)
            if env_var:
                api_key = os.environ.get(env_var, "")
    
    # 从 config.yaml 获取 model
    model = config.get("model", "")
    if not model:
        provider_key = provider_type.replace("-", "_")
        provider_key_dash = provider_type.replace("_", "-")
        provider_config = yaml_config.get("providers", {}).get(provider_key, {}) or \
                         yaml_config.get("providers", {}).get(provider_key_dash, {})
        model = provider_config.get("model", "")
    
    provider_kwargs = {
        "provider_type": provider_type,
        "api_key": api_key,
        "model": model,
    }
    
    # 只有 deepseek 和 openai 支持 base_url
    if provider_type in ("deepseek", "openai", "openai_compat"):
        base_url = config.get("base_url") or yaml_config.get("providers", {}).get(provider_type, {}).get("base_url", "")
        if base_url:
            provider_kwargs["base_url"] = base_url
    
    # 只有 claude 支持 model_kwargs
    if provider_type == "claude" and config.get("model_kwargs"):
        provider_kwargs["model_kwargs"] = config["model_kwargs"]
    
    provider = create_provider(**provider_kwargs)

    registry = ToolRegistry()
    register_all_tools(registry, workspace)

    # 可选组件
    cost_tracker = CostTracker()
    tracer = Tracer()

    # 创建 MainLoop
    main_loop = MainLoop(
        provider=provider,
        tool_registry=registry,
        cost_tracker=cost_tracker,
        tracer=tracer,
        max_turns=config.get("max_turns", 50),
        system_prompt=system_prompt,
    )

    # 设置回调 - 发送流式更新
    def on_thinking(content: str):
        asyncio.create_task(manager.send_message(session_id, {
            "type": "thinking",
            "content": content,
        }))

    def on_tool_call(tool_name: str, arguments: str):
        asyncio.create_task(manager.send_message(session_id, {
            "type": "tool_call",
            "tool": tool_name,
            "arguments": arguments,
        }))

    def on_tool_result(tool_name: str, result: str):
        asyncio.create_task(manager.send_message(session_id, {
            "type": "tool_result",
            "tool": tool_name,
            "result": result[:500] if len(result) > 500 else result,
        }))

    def on_token_update(prompt_tokens: int, completion_tokens: int, cost: float, total_tokens: int = 0):
        asyncio.create_task(manager.send_message(session_id, {
            "type": "token_update",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost": cost,
            "total_tokens": total_tokens,
        }))

    main_loop.on("thinking", on_thinking)
    main_loop.on("tool_call", on_tool_call)
    main_loop.on("tool_result", on_tool_result)
    main_loop.on("token_update", on_token_update)

    # 运行
    result = await main_loop.run(prompt)

    # 发送最终结果
    stats = cost_tracker.get_stats()
    await manager.send_message(session_id, {
        "type": "finished",
        "result": result.content,
        "status": result.status.value if hasattr(result.status, 'value') else str(result.status),
        "stats": stats,
    })

    # 更新会话
    session_manager.update_session(
        session_id,
        conversation=session["conversation"] + [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": result.content},
        ],
        cost=stats["total_cost"],
        prompt_tokens=stats["total_prompt_tokens"],
        completion_tokens=stats["total_completion_tokens"],
    )


# ============================================================================
# 入口
# ============================================================================


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """启动服务器"""
    uvicorn.run(
        "web:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port=port)
