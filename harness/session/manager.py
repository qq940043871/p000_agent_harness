# harness/session/manager.py
# Session 管理器 - 物理隔离的会话管理

import json
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, List, Iterator
from enum import Enum


class SessionStatus(Enum):
    """Session 状态"""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SessionMeta:
    """Session 元数据"""
    session_id: str
    created_at: float
    task_description: str = ""
    status: str = "active"
    turns: int = 0
    total_tokens: int = 0
    error_count: int = 0


class Session:
    """
    单个会话的完整上下文
    
    物理存储：每个 Session 对应一个目录
    """

    def __init__(self, session_dir: Path):
        self.dir = session_dir
        self.dir.mkdir(parents=True, exist_ok=True)

        self._meta_path = self.dir / "session.json"
        self._messages_path = self.dir / "messages.jsonl"
        self._meta: Optional[SessionMeta] = None

    @classmethod
    def create(cls, base_dir: Path, task_description: str = "") -> "Session":
        """创建新 Session"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        # 从任务描述生成短 ID
        task_slug = cls._make_slug(task_description)
        session_id = f"{timestamp}_{task_slug}" if task_slug else timestamp
        session_dir = base_dir / session_id

        session = cls(session_dir)
        session._meta = SessionMeta(
            session_id=session_id,
            created_at=time.time(),
            task_description=task_description,
        )
        session._save_meta()

        return session

    @classmethod
    def load(cls, session_dir: Path) -> "Session":
        """从目录加载已有 Session"""
        session = cls(session_dir)
        if session._meta_path.exists():
            data = json.loads(session._meta_path.read_text())
            session._meta = SessionMeta(**data)
        return session

    @staticmethod
    def _make_slug(text: str, max_words: int = 3) -> str:
        """从文本生成 URL 友好的 slug"""
        if not text:
            return ""
        words = text.split()[:max_words]
        slug = "-".join(words).lower()
        # 只保留字母、数字和短横线
        slug = "".join(c if c.isalnum() or c == "-" else "" for c in slug)
        return slug[:50]  # 限制长度

    # ── 消息管理 ─────────────────────────────────────────

    def append_message(self, message: dict):
        """追加消息到 Session（JSONL 格式，追加写）"""
        with open(self._messages_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(message, ensure_ascii=False) + "\n")

    def append_messages(self, messages: List[dict]):
        """批量追加消息"""
        with open(self._messages_path, "a", encoding="utf-8") as f:
            for msg in messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def get_messages(self) -> List[dict]:
        """读取全部消息历史"""
        if not self._messages_path.exists():
            return []

        messages = []
        with open(self._messages_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass  # 跳过损坏的行
        return messages

    def get_message_count(self) -> int:
        """获取消息数量（不加载全部内容）"""
        if not self._messages_path.exists():
            return 0
        with open(self._messages_path) as f:
            return sum(1 for line in f if line.strip())

    def iter_messages(self) -> Iterator[dict]:
        """迭代器方式读取消息（内存友好）"""
        if not self._messages_path.exists():
            return
        with open(self._messages_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        pass

    # ── 工件管理 ─────────────────────────────────────────

    def save_artifact(self, name: str, content: str, file_type: str = ".txt") -> Path:
        """
        保存会话产生的工件（如报告、生成的代码等）
        
        Args:
            name: 工件名称
            content: 工件内容
            file_type: 文件类型后缀
            
        Returns:
            保存的文件路径
        """
        artifact_dir = self.dir / "artifacts"
        artifact_dir.mkdir(exist_ok=True)
        
        # 确保文件名唯一
        file_path = artifact_dir / f"{name}{file_type}"
        counter = 1
        while file_path.exists():
            file_path = artifact_dir / f"{name}_{counter}{file_type}"
            counter += 1
        
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def list_artifacts(self) -> List[Path]:
        """列出所有工件"""
        artifact_dir = self.dir / "artifacts"
        if not artifact_dir.exists():
            return []
        return sorted(artifact_dir.iterdir())

    # ── 元数据管理 ───────────────────────────────────────

    def update_stats(self, turns: int = None, total_tokens: int = None, error_count: int = None):
        """更新执行统计"""
        if self._meta:
            if turns is not None:
                self._meta.turns = turns
            if total_tokens is not None:
                self._meta.total_tokens = total_tokens
            if error_count is not None:
                self._meta.error_count = error_count
            self._save_meta()

    def mark_completed(self):
        """标记为完成"""
        if self._meta:
            self._meta.status = "completed"
            self._save_meta()

    def mark_failed(self):
        """标记为失败"""
        if self._meta:
            self._meta.status = "failed"
            self._save_meta()

    def _save_meta(self):
        """保存元数据到文件"""
        if self._meta:
            self._meta_path.write_text(
                json.dumps(asdict(self._meta), indent=2, ensure_ascii=False)
            )

    @property
    def meta(self) -> Optional[SessionMeta]:
        return self._meta

    @property
    def session_id(self) -> str:
        return self._meta.session_id if self._meta else self.dir.name

    @property
    def created_time(self) -> str:
        """返回可读格式的创建时间"""
        if self._meta:
            return datetime.fromtimestamp(self._meta.created_at).strftime("%Y-%m-%d %H:%M:%S")
        return ""

    @property
    def is_active(self) -> bool:
        """是否活跃"""
        return self._meta and self._meta.status == "active"


class SessionManager:
    """
    Session 生命周期管理器
    
    负责创建、加载、列举 Session
    """

    def __init__(self, workspace: str = "."):
        self.base_dir = Path(workspace) / ".workbuddy" / "sessions"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._current_session: Optional[Session] = None

    def new_session(self, task_description: str = "") -> Session:
        """创建并激活新 Session"""
        session = Session.create(self.base_dir, task_description)
        self._current_session = session
        self._update_current_link(session)
        return session

    def get_current(self) -> Optional[Session]:
        """获取当前激活的 Session"""
        return self._current_session

    def load_session(self, session_id: str) -> Optional[Session]:
        """加载指定 Session"""
        session_dir = self.base_dir / session_id
        if session_dir.exists():
            return Session.load(session_dir)
        return None

    def load_latest(self) -> Optional[Session]:
        """加载最新的 Session"""
        sessions = self.list_sessions(limit=1)
        return sessions[0] if sessions else None

    def list_sessions(
        self,
        limit: int = 20,
        status: SessionStatus = None,
    ) -> List[Session]:
        """
        列出最近的 Sessions
        
        Args:
            limit: 最大数量
            status: 按状态过滤
        """
        sessions = []
        for d in sorted(self.base_dir.iterdir(), reverse=True):
            if d.is_dir() and not d.name.startswith("."):
                session = Session.load(d)
                if status is None or session.meta.status == status.value:
                    sessions.append(session)
                    if len(sessions) >= limit:
                        break
        return sessions

    def list_by_date(self, date: str = None) -> List[Session]:
        """
        按日期列出 Sessions
        
        Args:
            date: 日期字符串，格式 YYYY-MM-DD
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        sessions = []
        for d in self.base_dir.iterdir():
            if d.is_dir() and d.name.startswith(date):
                sessions.append(Session.load(d))
        return sorted(sessions, key=lambda s: s.session_id, reverse=True)

    def cleanup_old_sessions(self, keep_days: int = 30) -> int:
        """
        清理旧的 Session
        
        Args:
            keep_days: 保留最近多少天的 Session
            
        Returns:
            删除的 Session 数量
        """
        import shutil
        
        cutoff = time.time() - (keep_days * 86400)
        deleted = 0
        
        for d in self.base_dir.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                meta_path = d / "session.json"
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text())
                    if meta["created_at"] < cutoff:
                        shutil.rmtree(d)
                        deleted += 1
        
        return deleted

    def _update_current_link(self, session: Session):
        """更新 current 软链接（仅 Unix 系统）"""
        current_link = self.base_dir / "current"
        try:
            if current_link.exists() or current_link.is_symlink():
                current_link.unlink()
            current_link.symlink_to(session.dir.name)
        except (OSError, NotImplementedError):
            pass  # Windows 可能不支持软链接，忽略

    @property
    def session_count(self) -> int:
        """获取 Session 总数"""
        return sum(1 for d in self.base_dir.iterdir() if d.is_dir() and not d.name.startswith("."))
