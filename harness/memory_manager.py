"""
Memory Manager - 持久化记忆管理系统

支持：
- 状态外部化存储
- 基于文件的持久化
- 待办事项管理
- 跨会话记忆恢复
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any


class MemoryType(Enum):
    """记忆类型"""
    WORKING = auto()      # 工作记忆（短期）
    EPISODIC = auto()     # 情景记忆（事件）
    SEMANTIC = auto()     # 语义记忆（知识）
    PROCEDURAL = auto()   # 程序记忆（技能）
    TODO = auto()         # 待办事项


@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    content: str
    memory_type: MemoryType
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    importance: int = 5          # 重要性 1-10
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    parent_id: str | None = None  # 用于记忆关联

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "importance": self.importance,
            "tags": self.tags,
            "metadata": self.metadata,
            "session_id": self.session_id,
            "parent_id": self.parent_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MemoryEntry:
        return cls(
            id=data["id"],
            content=data["content"],
            memory_type=MemoryType[data["memory_type"]],
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            importance=data.get("importance", 5),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            session_id=data.get("session_id"),
            parent_id=data.get("parent_id"),
        )


@dataclass
class TodoItem:
    """待办事项"""
    id: str
    content: str
    status: str = "pending"      # pending, in_progress, completed, cancelled
    priority: int = 5             # 优先级 1-10
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    due_date: str | None = None
    completed_at: str | None = None
    parent_id: str | None = None  # 用于子任务
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at,
            "due_date": self.due_date,
            "completed_at": self.completed_at,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TodoItem:
        return cls(
            id=data["id"],
            content=data["content"],
            status=data.get("status", "pending"),
            priority=data.get("priority", 5),
            created_at=data.get("created_at", datetime.now().isoformat()),
            due_date=data.get("due_date"),
            completed_at=data.get("completed_at"),
            parent_id=data.get("parent_id"),
            metadata=data.get("metadata", {}),
        )


class FileStorage:
    """基于文件系统的存储"""

    def __init__(self, base_path: str | Path):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        for mem_type in MemoryType:
            (self.base_path / mem_type.name.lower()).mkdir(exist_ok=True)

    def _get_file_path(self, memory_type: MemoryType, memory_id: str) -> Path:
        """获取记忆文件路径"""
        return self.base_path / memory_type.name.lower() / f"{memory_id}.json"

    def save(self, entry: MemoryEntry) -> None:
        """保存记忆"""
        path = self._get_file_path(entry.memory_type, entry.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry.to_dict(), f, ensure_ascii=False, indent=2)

    def load(self, memory_type: MemoryType, memory_id: str) -> MemoryEntry | None:
        """加载记忆"""
        path = self._get_file_path(memory_type, memory_id)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return MemoryEntry.from_dict(json.load(f))

    def delete(self, memory_type: MemoryType, memory_id: str) -> bool:
        """删除记忆"""
        path = self._get_file_path(memory_type, memory_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_by_type(self, memory_type: MemoryType) -> list[MemoryEntry]:
        """列出指定类型的所有记忆"""
        dir_path = self.base_path / memory_type.name.lower()
        entries = []

        for file_path in dir_path.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    entries.append(MemoryEntry.from_dict(json.load(f)))
            except (json.JSONDecodeError, KeyError):
                continue

        return sorted(entries, key=lambda e: e.updated_at, reverse=True)

    def search(self, query: str, memory_types: list[MemoryType] | None = None) -> list[MemoryEntry]:
        """搜索记忆"""
        if memory_types is None:
            memory_types = list(MemoryType)

        results = []
        query_lower = query.lower()

        for mem_type in memory_types:
            for entry in self.list_by_type(mem_type):
                if query_lower in entry.content.lower():
                    results.append(entry)

        return sorted(results, key=lambda e: e.importance, reverse=True)


class MemoryManager:
    """
    记忆管理器

    功能：
    - 状态外部化存储
    - 跨会话持久化
    - 记忆检索和关联
    - 待办事项管理
    """

    def __init__(
        self,
        storage_path: str | Path,
        max_working_memory: int = 100,
        auto_save: bool = True,
    ):
        self.storage = FileStorage(storage_path)
        self.max_working_memory = max_working_memory
        self.auto_save = auto_save

        # 内存缓存
        self._cache: dict[str, MemoryEntry] = {}
        self._todo_cache: dict[str, TodoItem] = {}

        # 当前会话 ID
        self._current_session_id: str | None = None

    def set_session(self, session_id: str) -> None:
        """设置当前会话 ID"""
        self._current_session_id = session_id

    def _generate_id(self, prefix: str = "mem") -> str:
        """生成唯一 ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        import uuid
        short_uuid = uuid.uuid4().hex[:8]
        return f"{prefix}_{timestamp}_{short_uuid}"

    # ==================== 记忆操作 ====================

    def store(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.WORKING,
        importance: int = 5,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """
        存储记忆

        Args:
            content: 记忆内容
            memory_type: 记忆类型
            importance: 重要性 1-10
            tags: 标签
            metadata: 元数据

        Returns:
            创建的记忆条目
        """
        entry = MemoryEntry(
            id=self._generate_id(),
            content=content,
            memory_type=memory_type,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {},
            session_id=self._current_session_id,
        )

        # 保存到缓存
        self._cache[entry.id] = entry

        # 自动保存到磁盘
        if self.auto_save:
            self.storage.save(entry)

        # 触发工作记忆清理
        if memory_type == MemoryType.WORKING:
            self._cleanup_working_memory()

        return entry

    def recall(self, memory_id: str) -> MemoryEntry | None:
        """回忆指定记忆"""
        # 先从缓存查找
        if memory_id in self._cache:
            return self._cache[memory_id]

        # 从存储加载
        for mem_type in MemoryType:
            entry = self.storage.load(mem_type, memory_id)
            if entry:
                self._cache[memory_id] = entry
                return entry

        return None

    def update(self, memory_id: str, content: str | None = None, **kwargs) -> MemoryEntry | None:
        """更新记忆"""
        entry = self.recall(memory_id)
        if not entry:
            return None

        if content is not None:
            entry.content = content

        for key, value in kwargs.items():
            if hasattr(entry, key):
                setattr(entry, key, value)

        entry.updated_at = datetime.now().isoformat()

        # 保存
        self._cache[memory_id] = entry
        if self.auto_save:
            self.storage.save(entry)

        return entry

    def forget(self, memory_id: str) -> bool:
        """遗忘（删除）记忆"""
        entry = self.recall(memory_id)
        if not entry:
            return False

        # 从缓存删除
        self._cache.pop(memory_id, None)

        # 从存储删除
        return self.storage.delete(entry.memory_type, memory_id)

    def retrieve(
        self,
        query: str | None = None,
        memory_types: list[MemoryType] | None = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        """
        检索记忆

        Args:
            query: 搜索关键词
            memory_types: 记忆类型过滤
            limit: 返回数量限制

        Returns:
            匹配的记忆列表
        """
        if query:
            results = self.storage.search(query, memory_types)
        else:
            # 返回最近记忆
            results = []
            types_to_search = memory_types or list(MemoryType)
            for mem_type in types_to_search:
                results.extend(self.storage.list_by_type(mem_type))

        # 排序：重要性 > 更新时间
        results.sort(key=lambda e: (e.importance, e.updated_at), reverse=True)

        return results[:limit]

    def get_working_memory(self) -> list[MemoryEntry]:
        """获取工作记忆"""
        return self.storage.list_by_type(MemoryType.WORKING)

    def get_recent_memories(self, hours: int = 24, limit: int = 50) -> list[MemoryEntry]:
        """获取最近 N 小时内的记忆"""
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()

        all_memories = []
        for mem_type in MemoryType:
            all_memories.extend(self.storage.list_by_type(mem_type))

        recent = [
            m for m in all_memories
            if m.updated_at > cutoff_str
        ]

        return sorted(recent, key=lambda m: m.updated_at, reverse=True)[:limit]

    def _cleanup_working_memory(self) -> None:
        """清理工作记忆，保留重要的"""
        working = self.storage.list_by_type(MemoryType.WORKING)

        if len(working) <= self.max_working_memory:
            return

        # 分离重要和非重要记忆
        important = [m for m in working if m.importance >= 7]
        normal = [m for m in working if m.importance < 7]

        # 保留重要的 + 部分最近的
        keep = important + sorted(normal, key=lambda m: m.updated_at, reverse=True)[:self.max_working_memory - len(important)]

        # 删除多余的
        keep_ids = {m.id for m in keep}
        for entry in working:
            if entry.id not in keep_ids:
                self.forget(entry.id)

    # ==================== 待办事项 ====================

    def add_todo(
        self,
        content: str,
        priority: int = 5,
        due_date: str | None = None,
        parent_id: str | None = None,
    ) -> TodoItem:
        """添加待办事项"""
        todo = TodoItem(
            id=self._generate_id("todo"),
            content=content,
            priority=priority,
            due_date=due_date,
            parent_id=parent_id,
        )

        self._todo_cache[todo.id] = todo

        # 保存到文件
        todo_path = self.storage.base_path / "todo" / f"{todo.id}.json"
        todo_path.parent.mkdir(exist_ok=True)
        with open(todo_path, "w", encoding="utf-8") as f:
            json.dump(todo.to_dict(), f, ensure_ascii=False, indent=2)

        return todo

    def get_todos(
        self,
        status: str | None = None,
        include_children: bool = True,
    ) -> list[TodoItem]:
        """获取待办事项列表"""
        todo_dir = self.storage.base_path / "todo"
        if not todo_dir.exists():
            return []

        todos = []
        for file_path in todo_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    todo = TodoItem.from_dict(json.load(f))
                    if status is None or todo.status == status:
                        todos.append(todo)
            except (json.JSONDecodeError, KeyError):
                continue

        # 按优先级和创建时间排序
        todos.sort(key=lambda t: (-t.priority, t.created_at))

        # 过滤子任务
        if not include_children:
            todos = [t for t in todos if t.parent_id is None]

        return todos

    def complete_todo(self, todo_id: str) -> TodoItem | None:
        """标记待办为完成"""
        todo_path = self.storage.base_path / "todo" / f"{todo_id}.json"
        if not todo_path.exists():
            return None

        with open(todo_path, "r", encoding="utf-8") as f:
            todo = TodoItem.from_dict(json.load(f))

        todo.status = "completed"
        todo.completed_at = datetime.now().isoformat()

        with open(todo_path, "w", encoding="utf-8") as f:
            json.dump(todo.to_dict(), f, ensure_ascii=False, indent=2)

        return todo

    def delete_todo(self, todo_id: str) -> bool:
        """删除待办事项"""
        todo_path = self.storage.base_path / "todo" / f"{todo_id}.json"
        if todo_path.exists():
            todo_path.unlink()
            return True
        return False

    # ==================== 上下文组装 ====================

    def build_context_prompt(
        self,
        current_task: str | None = None,
        include_types: list[MemoryType] | None = None,
    ) -> str:
        """
        构建上下文提示

        将相关记忆组装成提示文本，用于注入到 System Prompt。
        """
        context_parts = []

        # 最近的记忆
        recent = self.get_recent_memories(hours=24, limit=10)
        if recent:
            context_parts.append("【近期活动】")
            for m in recent[:5]:
                context_parts.append(f"- {m.content}")
            context_parts.append("")

        # 活跃的待办
        todos = self.get_todos(status="in_progress")
        if todos:
            context_parts.append("【进行中的任务】")
            for t in todos:
                context_parts.append(f"- [{t.id}] {t.content}")
            context_parts.append("")

        # 重要记忆
        important = self.retrieve(memory_types=[MemoryType.SEMANTIC, MemoryType.PROCEDURAL], limit=5)
        if important:
            context_parts.append("【重要信息】")
            for m in important[:3]:
                context_parts.append(f"- {m.content}")
            context_parts.append("")

        if context_parts:
            return "\n".join(context_parts)
        return ""


# ==================== 便捷函数 ====================

def create_memory_manager(
    workspace_path: str | Path,
    session_id: str | None = None,
) -> MemoryManager:
    """创建记忆管理器（便捷函数）"""
    storage_path = Path(workspace_path) / ".workbuddy" / "memory"
    manager = MemoryManager(storage_path)

    if session_id:
        manager.set_session(session_id)

    return manager
