"""
Coding Plan 集成模块 - 支持腾讯云 Coding 和火山引擎 Coding

支持平台:
- 腾讯云 Coding (coding.cn)
- 火山引擎 Coding ( volcengine.com/coding)

支持功能:
- 代码仓库操作（克隆、提交、拉取、推送）
- 项目管理（创建仓库、获取项目列表）
- CI/CD 流水线触发与状态查询
- Webhook 事件处理
- 代码审查（MR/PR）操作

官方文档:
- 腾讯云: https://help.coding.net/docs/api/open
- 火山引擎: https://www.volcengine.com/docs/coding/1163702
"""

import asyncio
import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional
from urllib.parse import urlencode

import httpx


# ============== 平台类型 ==============

class CodingPlatform(Enum):
    """支持的 Coding 平台"""
    TENCENT = "tencent"      # 腾讯云 Coding (coding.cn)
    VOLCENGINE = "volcengine"  # 火山引擎 Coding ( volcengine.com)


@dataclass
class VolcEngineCodingEndpoints:
    """火山引擎 Coding API 端点"""
    # 基础 API
    BASE = "https://volcengine.coding.cn"
    API_BASE = "https://volcengine.coding.cn/open-api"
    
    # OAuth
    OAUTH_AUTHORIZE = "https://volcengine.coding.cn/oauth/authorize"
    OAUTH_TOKEN = "https://volcengine.coding.cn/oauth/access_token"
    
    # 用户
    USER = "/v1/user"


@dataclass  
class TencentCodingEndpoints:
    """腾讯云 Coding API 端点"""
    BASE = "https://{team}.coding.cn"
    API_BASE = "https://{team}.coding.cn/open-api"


# ============== 配置与认证 ==============

@dataclass
class CodingConfig:
    """Coding Plan 配置"""
    # 个人访问令牌（推荐使用）或 OAuth Token
    token: str
    # Coding 团队名称，如 "my-team"
    team: str
    # 平台类型
    platform: CodingPlatform = CodingPlatform.TENCENT
    # API 基础地址（默认使用腾讯云 Coding）
    base_url: str = ""
    # 超时时间（秒）
    timeout: int = 30
    # 是否验证 Webhook 签名
    verify_signature: bool = True
    # Webhook 签名密钥
    webhook_secret: Optional[str] = None

    def __post_init__(self):
        # 根据平台设置默认 base_url
        if not self.base_url:
            if self.platform == CodingPlatform.VOLCENGINE:
                self.base_url = VolcEngineCodingEndpoints.BASE
            else:
                self.base_url = TencentCodingEndpoints.BASE.format(team=self.team)
        
        # 火山引擎需要特殊处理 team
        if self.platform == CodingPlatform.VOLCENGINE:
            self.team = "volcengine"  # 火山引擎固定团队名

    def get_api_base(self) -> str:
        """获取 API 基础地址"""
        if self.platform == CodingPlatform.VOLCENGINE:
            return VolcEngineCodingEndpoints.API_BASE
        return TencentCodingEndpoints.API_BASE.format(team=self.team)
    
    def get_headers(self, auth_type: AuthType = AuthType.PERSONAL_TOKEN) -> dict:
        """生成请求头"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if auth_type == AuthType.PERSONAL_TOKEN:
            # 腾讯云使用 token 前缀，火山引擎使用 Bearer
            if self.platform == CodingPlatform.VOLCENGINE:
                headers["Authorization"] = f"Bearer {self.token}"
            else:
                headers["Authorization"] = f"token {self.token}"
        elif auth_type == AuthType.OAUTH:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers


class AuthType(Enum):
    """认证类型"""
    PERSONAL_TOKEN = "personal_token"  # 个人访问令牌
    OAUTH = "oauth"  # OAuth Token
    WEBHOOK = "webhook"  # Webhook 验证


# ============== 工具定义 ==============

@dataclass
class CodingToolResult:
    """Coding 操作结果"""
    success: bool
    data: Any = None
    error: str = ""
    operation: str = ""
    duration_ms: float = 0


class CodingTools:
    """Coding Plan 工具集，供 Agent 调用"""

    def __init__(self, config: CodingConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=config.timeout)
        self._setup_api_paths()

    def _setup_api_paths(self):
        """根据平台设置 API 路径前缀"""
        if self.config.platform == CodingPlatform.VOLCENGINE:
            # 火山引擎使用 /api/v1 前缀
            self._api_prefix = "/api/v1"
        else:
            # 腾讯云使用 /open-api/v1 前缀
            self._api_prefix = "/open-api/v1"

    async def close(self):
        await self.client.aclose()

    def _get_headers(self, auth_type: AuthType = AuthType.PERSONAL_TOKEN) -> dict:
        """生成请求头"""
        return self.config.get_headers(auth_type)

    def _build_path(self, path: str) -> str:
        """构建完整的 API 路径"""
        # 火山引擎需要特殊处理
        if self.config.platform == CodingPlatform.VOLCENGINE:
            # 火山引擎的路径格式
            if path.startswith("/api/v1"):
                return path
            if path.startswith("/open-api"):
                return path.replace("/open-api", "/api/v1")
            return f"/api/v1{path}"
        else:
            # 腾讯云保持原样
            if path.startswith("/open-api/v1"):
                return path
            if path.startswith("/api/v1"):
                return path.replace("/api/v1", "/open-api/v1")
            return f"/open-api/v1{path}"

    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        """统一请求方法"""
        full_path = self._build_path(path)
        url = f"{self.config.get_api_base()}{full_path}"
        headers = self._get_headers()

        response = await self.client.request(
            method=method,
            url=url,
            headers=headers,
            json=data,
            params=params,
        )

        if response.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"Coding API error: {response.status_code}",
                request=response.request,
                response=response,
            )

        return response.json()

    # ============== Git 操作 ==============

    async def clone_repo(
        self,
        repo_name: str,
        project_name: Optional[str] = None,
        branch: str = "master",
    ) -> CodingToolResult:
        """克隆仓库（返回仓库 URL）"""
        start = time.time()
        try:
            project = project_name or self.config.team
            # 获取仓库信息
            repo_info = await self._request(
                "GET",
                f"/api/v1/projects/{project}/repos/{repo_name}",
                params={"RefName": branch},
            )

            clone_url = repo_info.get("data", {}).get("httpsUrl", "")

            return CodingToolResult(
                success=True,
                data={
                    "clone_url": clone_url,
                    "repo_name": repo_name,
                    "branch": branch,
                    "web_url": repo_info.get("data", {}).get("webUrl", ""),
                },
                operation="clone_repo",
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return CodingToolResult(
                success=False,
                error=str(e),
                operation="clone_repo",
                duration_ms=(time.time() - start) * 1000,
            )

    async def get_file_content(
        self,
        repo_name: str,
        file_path: str,
        ref: str = "master",
        project_name: Optional[str] = None,
    ) -> CodingToolResult:
        """获取文件内容"""
        start = time.time()
        try:
            project = project_name or self.config.team
            content = await self._request(
                "GET",
                f"/api/v1/projects/{project}/repos/{repo_name}/files/{file_path}",
                params={"ref": ref},
            )

            # 文件内容可能是 base64 编码的
            file_data = content.get("data", {})
            file_content = file_data.get("content", "")

            # 如果是 base64 编码，尝试解码
            try:
                decoded = base64.b64decode(file_content).decode("utf-8")
                file_content = decoded
            except Exception:
                pass  # 可能不是 base64，直接使用原文

            return CodingToolResult(
                success=True,
                data={
                    "content": file_content,
                    "path": file_path,
                    "sha": file_data.get("sha"),
                    "size": file_data.get("size", len(file_content)),
                },
                operation="get_file",
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return CodingToolResult(
                success=False,
                error=str(e),
                operation="get_file",
                duration_ms=(time.time() - start) * 1000,
            )

    async def create_or_update_file(
        self,
        repo_name: str,
        file_path: str,
        content: str,
        message: str,
        branch: str = "master",
        project_name: Optional[str] = None,
    ) -> CodingToolResult:
        """创建或更新文件"""
        start = time.time()
        try:
            project = project_name or self.config.team

            # 编码内容
            encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")

            data = await self._request(
                "POST",
                f"/api/v1/projects/{project}/repos/{repo_name}/files/{file_path}",
                data={
                    "content": encoded_content,
                    "message": message,
                    "branch": branch,
                },
            )

            return CodingToolResult(
                success=True,
                data={
                    "file_path": file_path,
                    "branch": branch,
                    "commit_sha": data.get("data", {}).get("commitId"),
                },
                operation="update_file",
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return CodingToolResult(
                success=False,
                error=str(e),
                operation="update_file",
                duration_ms=(time.time() - start) * 1000,
            )

    async def create_commit(
        self,
        repo_name: str,
        message: str,
        actions: list,
        branch: str = "master",
        project_name: Optional[str] = None,
    ) -> CodingToolResult:
        """
        创建提交

        actions 格式:
        [
            {"action": "create|update|delete", "filePath": "path/to/file", "content": "..."}
        ]
        """
        start = time.time()
        try:
            project = project_name or self.config.team

            # 处理文件内容编码
            for action in actions:
                if action.get("content") and action.get("action") != "delete":
                    action["content"] = base64.b64encode(
                        action["content"].encode("utf-8")
                    ).decode("utf-8")

            data = await self._request(
                "POST",
                f"/api/v1/projects/{project}/repos/{repo_name}/commits",
                data={
                    "message": message,
                    "branch": branch,
                    "actions": actions,
                },
            )

            return CodingToolResult(
                success=True,
                data={
                    "commit_sha": data.get("data", {}).get("commitId"),
                    "branch": branch,
                    "message": message,
                },
                operation="create_commit",
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return CodingToolResult(
                success=False,
                error=str(e),
                operation="create_commit",
                duration_ms=(time.time() - start) * 1000,
            )

    # ============== 项目操作 ==============

    async def list_projects(self, page: int = 1, page_size: int = 20) -> CodingToolResult:
        """获取项目列表"""
        start = time.time()
        try:
            data = await self._request(
                "GET",
                "/api/v1/user/projects",
                params={"page": page, "pageSize": page_size},
            )

            projects = data.get("data", {}).get("list", [])

            return CodingToolResult(
                success=True,
                data={
                    "projects": [
                        {
                            "id": p.get("id"),
                            "name": p.get("name"),
                            "display_name": p.get("displayName"),
                            "description": p.get("description"),
                            "web_url": p.get("webUrl"),
                            "git_url": p.get("httpsUrl"),
                        }
                        for p in projects
                    ],
                    "total": data.get("data", {}).get("total"),
                    "page": page,
                },
                operation="list_projects",
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return CodingToolResult(
                success=False,
                error=str(e),
                operation="list_projects",
                duration_ms=(time.time() - start) * 1000,
            )

    async def create_project(
        self,
        name: str,
        display_name: str,
        description: str = "",
        is_private: bool = True,
    ) -> CodingToolResult:
        """创建项目"""
        start = time.time()
        try:
            data = await self._request(
                "POST",
                "/api/v1/user/projects",
                data={
                    "name": name,
                    "displayName": display_name,
                    "description": description,
                    "visibility": "private" if is_private else "public",
                },
            )

            return CodingToolResult(
                success=True,
                data={
                    "id": data.get("data", {}).get("id"),
                    "name": name,
                    "web_url": data.get("data", {}).get("webUrl"),
                },
                operation="create_project",
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return CodingToolResult(
                success=False,
                error=str(e),
                operation="create_project",
                duration_ms=(time.time() - start) * 1000,
            )

    # ============== CI/CD 操作 ==============

    async def trigger_pipeline(
        self,
        project_name: str,
        pipeline_id: int,
        branch: Optional[str] = None,
        variables: Optional[dict] = None,
    ) -> CodingToolResult:
        """触发流水线"""
        start = time.time()
        try:
            data = await self._request(
                "POST",
                f"/api/v1/projects/{project_name}/pipelines/{pipeline_id}/run",
                data={
                    "branch": branch,
                    "variables": variables or {},
                },
            )

            return CodingToolResult(
                success=True,
                data={
                    "pipeline_id": pipeline_id,
                    "run_id": data.get("data", {}).get("id"),
                    "status": "triggered",
                },
                operation="trigger_pipeline",
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return CodingToolResult(
                success=False,
                error=str(e),
                operation="trigger_pipeline",
                duration_ms=(time.time() - start) * 1000,
            )

    async def get_pipeline_status(
        self,
        project_name: str,
        pipeline_id: int,
        run_id: int,
    ) -> CodingToolResult:
        """获取流水线状态"""
        start = time.time()
        try:
            data = await self._request(
                "GET",
                f"/api/v1/projects/{project_name}/pipelines/{pipeline_id}/runs/{run_id}",
            )

            run_info = data.get("data", {})

            return CodingToolResult(
                success=True,
                data={
                    "run_id": run_id,
                    "status": run_info.get("status"),
                    "stages": run_info.get("stages", []),
                    "duration": run_info.get("duration"),
                    "triggered_by": run_info.get("triggeredBy"),
                    "created_at": run_info.get("createdAt"),
                },
                operation="get_pipeline_status",
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return CodingToolResult(
                success=False,
                error=str(e),
                operation="get_pipeline_status",
                duration_ms=(time.time() - start) * 1000,
            )

    # ============== MR/PR 操作 ==============

    async def create_mr(
        self,
        repo_name: str,
        source_branch: str,
        target_branch: str = "master",
        title: str = "",
        description: str = "",
        project_name: Optional[str] = None,
    ) -> CodingToolResult:
        """创建合并请求"""
        start = time.time()
        try:
            project = project_name or self.config.team

            data = await self._request(
                "POST",
                f"/api/v1/projects/{project}/repos/{repo_name}/merge_requests",
                data={
                    "sourceBranch": source_branch,
                    "targetBranch": target_branch,
                    "title": title,
                    "description": description,
                },
            )

            return CodingToolResult(
                success=True,
                data={
                    "mr_id": data.get("data", {}).get("id"),
                    "title": title,
                    "source_branch": source_branch,
                    "target_branch": target_branch,
                    "web_url": data.get("data", {}).get("url"),
                },
                operation="create_mr",
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return CodingToolResult(
                success=False,
                error=str(e),
                operation="create_mr",
                duration_ms=(time.time() - start) * 1000,
            )

    async def list_mrs(
        self,
        repo_name: str,
        state: str = "open",
        project_name: Optional[str] = None,
    ) -> CodingToolResult:
        """获取合并请求列表"""
        start = time.time()
        try:
            project = project_name or self.config.team

            data = await self._request(
                "GET",
                f"/api/v1/projects/{project}/repos/{repo_name}/merge_requests",
                params={"state": state},
            )

            mrs = data.get("data", {}).get("list", [])

            return CodingToolResult(
                success=True,
                data={
                    "merge_requests": [
                        {
                            "id": mr.get("id"),
                            "title": mr.get("title"),
                            "source_branch": mr.get("sourceBranch"),
                            "target_branch": mr.get("targetBranch"),
                            "state": mr.get("state"),
                            "author": mr.get("author", {}).get("name"),
                            "web_url": mr.get("url"),
                        }
                        for mr in mrs
                    ],
                    "total": len(mrs),
                },
                operation="list_mrs",
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return CodingToolResult(
                success=False,
                error=str(e),
                operation="list_mrs",
                duration_ms=(time.time() - start) * 1000,
            )


# ============== Webhook 处理 ==============

class CodingWebhookHandler:
    """Coding Webhook 事件处理器"""

    EVENT_TYPES = {
        "git.push": "代码推送",
        "git.merge.request": "合并请求",
        "git.merge.request.merged": "合并完成",
        "pipeline.start": "流水线开始",
        "pipeline.finish": "流水线完成",
        "project.member.added": "成员加入",
    }

    def __init__(self, secret: Optional[str] = None):
        self.secret = secret

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """验证 Webhook 签名"""
        if not self.secret:
            return True

        expected = hmac.new(
            self.secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(f"sha256={expected}", signature)

    def parse_event(self, payload: dict, event_type: str) -> dict:
        """解析 Webhook 事件"""
        event_info = {
            "event_type": event_type,
            "event_name": self.EVENT_TYPES.get(event_type, "未知事件"),
            "timestamp": payload.get("triggeredAt", time.time()),
            "data": {},
        }

        # 根据事件类型解析不同数据
        if event_type == "git.push":
            event_info["data"] = {
                "user": payload.get("user", {}).get("name"),
                "repo": payload.get("repository", {}).get("name"),
                "branch": payload.get("ref", "").split("/")[-1],
                "commits": payload.get("commits", []),
                "commit_count": payload.get("totalCommitsCount", 0),
            }

        elif event_type in ("git.merge.request", "git.merge.request.merged"):
            event_info["data"] = {
                "mr_id": payload.get("mergeRequest", {}).get("id"),
                "title": payload.get("mergeRequest", {}).get("title"),
                "source_branch": payload.get("mergeRequest", {}).get("sourceBranch"),
                "target_branch": payload.get("mergeRequest", {}).get("targetBranch"),
                "author": payload.get("mergeRequest", {}).get("author", {}).get("name"),
                "action": payload.get("action", ""),
            }

        elif event_type in ("pipeline.start", "pipeline.finish"):
            event_info["data"] = {
                "pipeline_id": payload.get("pipeline", {}).get("id"),
                "status": payload.get("pipeline", {}).get("status"),
                "branch": payload.get("pipeline", {}).get("ref"),
                "triggered_by": payload.get("pipeline", {}).get("triggeredBy"),
            }

        return event_info


# ============== 工厂函数 ==============

def create_coding_config(
    token: str,
    team: str,
    platform: str = "tencent",
    **kwargs,
) -> CodingConfig:
    """
    创建 Coding 配置的工厂函数
    
    Args:
        token: 个人访问令牌
        team: 团队名称
        platform: 平台类型 ("tencent" 或 "volcengine")
        **kwargs: 其他配置参数
    
    Returns:
        CodingConfig 实例
    
    Example:
        # 腾讯云 Coding
        config = create_coding_config(
            token="your-token",
            team="my-team",
            platform="tencent",
        )
        
        # 火山引擎 Coding
        config = create_coding_config(
            token="volc-token",
            team="my-team",
            platform="volcengine",
        )
    """
    platform_enum = (
        CodingPlatform.VOLCENGINE 
        if platform.lower() == "volcengine" 
        else CodingPlatform.TENCENT
    )
    return CodingConfig(
        token=token,
        team=team,
        platform=platform_enum,
        **kwargs,
    )


# ============== Agent 集成 ==============

@dataclass
class CodingContext:
    """Coding 操作上下文"""
    repo_name: Optional[str] = None
    project_name: Optional[str] = None
    branch: str = "master"
    default_message: str = "Agent 自动提交"


class CodingAgentMixin:
    """
    Agent 集成 Coding 的 Mixin

    使用方式:
        class MyAgent(CodingAgentMixin, BaseAgent):
            pass
    """

    def __init__(self, coding_config: CodingConfig, **kwargs):
        super().__init__(**kwargs)
        self.coding = CodingTools(coding_config)
        self.coding_context = CodingContext()

    async def coding_clone(self, repo_name: str, branch: str = "master") -> dict:
        """克隆仓库"""
        self.coding_context.repo_name = repo_name
        self.coding_context.branch = branch
        result = await self.coding.clone_repo(repo_name, branch=branch)
        return result.data if result.success else {"error": result.error}

    async def coding_read(self, file_path: str) -> dict:
        """读取文件"""
        if not self.coding_context.repo_name:
            return {"error": "请先克隆仓库"}

        result = await self.coding.get_file_content(
            self.coding_context.repo_name,
            file_path,
            ref=self.coding_context.branch,
        )
        return result.data if result.success else {"error": result.error}

    async def coding_write(
        self,
        file_path: str,
        content: str,
        message: Optional[str] = None,
    ) -> dict:
        """写入文件"""
        if not self.coding_context.repo_name:
            return {"error": "请先克隆仓库"}

        result = await self.coding.create_or_update_file(
            self.coding_context.repo_name,
            file_path,
            content,
            message or self.coding_context.default_message,
            self.coding_context.branch,
        )
        return result.data if result.success else {"error": result.error}

    async def coding_commit(
        self,
        message: str,
        actions: list,
    ) -> dict:
        """提交更改"""
        if not self.coding_context.repo_name:
            return {"error": "请先克隆仓库"}

        result = await self.coding.create_commit(
            self.coding_context.repo_name,
            message,
            actions,
            self.coding_context.branch,
        )
        return result.data if result.success else {"error": result.error}

    async def coding_create_mr(
        self,
        source_branch: str,
        target_branch: str = "master",
        title: str = "",
        description: str = "",
    ) -> dict:
        """创建合并请求"""
        if not self.coding_context.repo_name:
            return {"error": "请先克隆仓库"}

        result = await self.coding.create_mr(
            self.coding_context.repo_name,
            source_branch,
            target_branch,
            title or f"MR: {source_branch} -> {target_branch}",
            description,
        )
        return result.data if result.success else {"error": result.error}

    async def coding_trigger_pipeline(
        self,
        pipeline_id: int,
        branch: Optional[str] = None,
    ) -> dict:
        """触发流水线"""
        result = await self.coding.trigger_pipeline(
            self.coding_context.project_name or self.coding.config.team,
            pipeline_id,
            branch or self.coding_context.branch,
        )
        return result.data if result.success else {"error": result.error}

    async def close(self):
        """关闭连接"""
        await self.coding.close()


# ============== 工具注册 ==============

def register_coding_tools(registry, config: CodingConfig):
    """
    注册 Coding 工具到工具注册表

    使用方式:
        from harness import ToolRegistry
        from harness.integrations.coding import register_coding_tools, CodingConfig

        registry = ToolRegistry()
        config = CodingConfig(token="your-token", team="your-team")
        register_coding_tools(registry, config)
    """
    tools = CodingTools(config)

    @registry.register(
        name="coding_clone",
        description="克隆 Coding 仓库，获取仓库信息",
        parameters={
            "type": "object",
            "properties": {
                "repo_name": {"type": "string", "description": "仓库名称"},
                "branch": {"type": "string", "description": "分支名称，默认为 master"},
            },
            "required": ["repo_name"],
        },
    )
    async def coding_clone(repo_name: str, branch: str = "master"):
        result = await tools.clone_repo(repo_name, branch=branch)
        return result.data if result.success else {"error": result.error}

    @registry.register(
        name="coding_read_file",
        description="读取 Coding 仓库中的文件内容",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件路径"},
                "repo_name": {"type": "string", "description": "仓库名称"},
                "branch": {"type": "string", "description": "分支名称"},
            },
            "required": ["file_path"],
        },
    )
    async def coding_read_file(
        file_path: str,
        repo_name: str = "",
        branch: str = "master",
    ):
        repo = repo_name or tools.config.team
        result = await tools.get_file_content(repo, file_path, ref=branch)
        return result.data if result.success else {"error": result.error}

    @registry.register(
        name="coding_write_file",
        description="创建或更新 Coding 仓库中的文件",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "文件内容"},
                "message": {"type": "string", "description": "提交信息"},
                "repo_name": {"type": "string", "description": "仓库名称"},
                "branch": {"type": "string", "description": "分支名称"},
            },
            "required": ["file_path", "content", "message"],
        },
    )
    async def coding_write_file(
        file_path: str,
        content: str,
        message: str,
        repo_name: str = "",
        branch: str = "master",
    ):
        repo = repo_name or tools.config.team
        result = await tools.create_or_update_file(
            repo, file_path, content, message, branch
        )
        return result.data if result.success else {"error": result.error}

    @registry.register(
        name="coding_commit",
        description="提交文件更改到 Coding 仓库",
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "提交信息"},
                "actions": {
                    "type": "array",
                    "description": "操作列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "enum": ["create", "update", "delete"]},
                            "filePath": {"type": "string"},
                            "content": {"type": "string"},
                        },
                    },
                },
                "repo_name": {"type": "string", "description": "仓库名称"},
                "branch": {"type": "string", "description": "分支名称"},
            },
            "required": ["message", "actions"],
        },
    )
    async def coding_commit(
        message: str,
        actions: list,
        repo_name: str = "",
        branch: str = "master",
    ):
        repo = repo_name or tools.config.team
        result = await tools.create_commit(repo, message, actions, branch)
        return result.data if result.success else {"error": result.error}

    @registry.register(
        name="coding_list_projects",
        description="列出 Coding 项目",
        parameters={
            "type": "object",
            "properties": {
                "page": {"type": "integer", "description": "页码"},
                "page_size": {"type": "integer", "description": "每页数量"},
            },
        },
    )
    async def coding_list_projects(page: int = 1, page_size: int = 20):
        result = await tools.list_projects(page, page_size)
        return result.data if result.success else {"error": result.error}

    @registry.register(
        name="coding_create_mr",
        description="创建合并请求",
        parameters={
            "type": "object",
            "properties": {
                "source_branch": {"type": "string", "description": "源分支"},
                "target_branch": {"type": "string", "description": "目标分支"},
                "title": {"type": "string", "description": "MR 标题"},
                "description": {"type": "string", "description": "MR 描述"},
                "repo_name": {"type": "string", "description": "仓库名称"},
            },
            "required": ["source_branch"],
        },
    )
    async def coding_create_mr(
        source_branch: str,
        target_branch: str = "master",
        title: str = "",
        description: str = "",
        repo_name: str = "",
    ):
        repo = repo_name or tools.config.team
        result = await tools.create_mr(
            repo, source_branch, target_branch, title, description
        )
        return result.data if result.success else {"error": result.error}

    @registry.register(
        name="coding_trigger_pipeline",
        description="触发 Coding 流水线",
        parameters={
            "type": "object",
            "properties": {
                "pipeline_id": {"type": "integer", "description": "流水线 ID"},
                "branch": {"type": "string", "description": "分支名称"},
                "variables": {"type": "object", "description": "流水线变量"},
                "project_name": {"type": "string", "description": "项目名称"},
            },
            "required": ["pipeline_id"],
        },
    )
    async def coding_trigger_pipeline(
        pipeline_id: int,
        branch: str = "",
        variables: dict = None,
        project_name: str = "",
    ):
        proj = project_name or tools.config.team
        result = await tools.trigger_pipeline(
            proj, pipeline_id, branch or None, variables
        )
        return result.data if result.success else {"error": result.error}


__all__ = [
    # 平台
    "CodingPlatform",
    "TencentCodingEndpoints",
    "VolcEngineCodingEndpoints",
    # 配置
    "CodingConfig",
    "create_coding_config",
    # 工具
    "CodingTools",
    "CodingWebhookHandler",
    "CodingToolResult",
    # Agent 集成
    "CodingContext",
    "CodingAgentMixin",
    "register_coding_tools",
    # 枚举
    "AuthType",
]
