# harness/prompt/builder.py
# 模块化 Prompt 构建器 - 动态组装 System Prompt

import os
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class PromptSection:
    """Prompt 的一个独立片段"""
    name: str
    content: str
    priority: int = 0       # 优先级（数字越小越靠前）
    enabled: bool = True


class PromptBuilder:
    """
    模块化 Prompt 构建器
    
    动态组装 System Prompt，支持：
    - 文件加载（AGENTS.md、IDENTITY.md 等）
    - Skills 外挂
    - 运行时上下文注入
    - 条件启用/禁用片段
    """

    def __init__(self, workspace: str = "."):
        self.workspace = Path(workspace)
        self._sections: List[PromptSection] = []

    # ── 加载来源 ─────────────────────────────────────────

    def load_agents_md(self) -> "PromptBuilder":
        """加载 AGENTS.md（项目级规范）"""
        path = self.workspace / "AGENTS.md"
        if path.exists():
            content = path.read_text(encoding="utf-8")
            self._sections.append(PromptSection(
                name="agents_md",
                content=content,
                priority=10,
            ))
        return self

    def load_identity(self) -> "PromptBuilder":
        """加载 .workbuddy/IDENTITY.md（Agent 身份）"""
        path = self.workspace / ".workbuddy" / "IDENTITY.md"
        if path.exists():
            content = path.read_text(encoding="utf-8")
            self._sections.append(PromptSection(
                name="identity",
                content=content,
                priority=5,  # 最高优先级
            ))
        return self

    def load_skills(self, skill_names: List[str] = None) -> "PromptBuilder":
        """
        加载 Skills（可插拔的专业能力模块）
        
        Args:
            skill_names: 指定要加载的 Skill 名称。None 表示加载所有已安装的 Skills
        """
        skills_dir = self.workspace / ".workbuddy" / "skills"
        if not skills_dir.exists():
            return self

        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            
            if skill_names and skill_dir.name not in skill_names:
                continue

            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                content = skill_md.read_text(encoding="utf-8")
                self._sections.append(PromptSection(
                    name=f"skill_{skill_dir.name}",
                    content=f"## Skill: {skill_dir.name}\n\n{content}",
                    priority=30,
                ))

        return self

    def load_memory(self) -> "PromptBuilder":
        """加载 Working Memory（长期记忆）"""
        memory_path = self.workspace / ".workbuddy" / "memory" / "MEMORY.md"
        if memory_path.exists():
            content = memory_path.read_text(encoding="utf-8")
            if content.strip():
                self._sections.append(PromptSection(
                    name="memory",
                    content=f"## 持久记忆\n\n{content}",
                    priority=20,
                ))
        return self

    def load_today_log(self) -> "PromptBuilder":
        """加载今日工作日志"""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        log_path = self.workspace / ".workbuddy" / "memory" / f"{today}.md"
        if log_path.exists():
            content = log_path.read_text(encoding="utf-8")
            if content.strip():
                self._sections.append(PromptSection(
                    name="today_log",
                    content=f"## 今日工作\n\n{content}",
                    priority=15,
                ))
        return self

    # ── 动态注入 ─────────────────────────────────────────

    def inject(
        self,
        name: str,
        content: str,
        priority: int = 50,
    ) -> "PromptBuilder":
        """动态注入 Prompt 片段（运行时上下文）"""
        self._sections.append(PromptSection(
            name=name,
            content=content,
            priority=priority,
        ))
        return self

    def inject_working_directory(self) -> "PromptBuilder":
        """注入当前工作目录信息"""
        return self.inject(
            name="working_directory",
            content=f"当前工作目录: `{self.workspace.absolute()}`",
            priority=25,
        )

    def inject_datetime(self) -> "PromptBuilder":
        """注入当前时间"""
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self.inject(
            name="datetime",
            content=f"当前时间: {now}",
            priority=25,
        )

    def inject_user_info(self, name: str, context: str = "") -> "PromptBuilder":
        """注入用户信息"""
        content = f"用户名称: {name}"
        if context:
            content += f"\n用户背景: {context}"
        return self.inject(
            name="user_info",
            content=content,
            priority=25,
        )

    def inject_tool_guide(self, tools: List[dict]) -> "PromptBuilder":
        """注入工具使用指南"""
        content = "## 可用工具\n\n"
        for tool in tools:
            content += f"- `{tool['name']}`: {tool.get('description', '')}\n"
        return self.inject(
            name="tool_guide",
            content=content,
            priority=40,
        )

    # ── 管理 ─────────────────────────────────────────────

    def disable(self, name: str) -> "PromptBuilder":
        """禁用指定 Prompt 片段"""
        for section in self._sections:
            if section.name == name:
                section.enabled = False
        return self

    def enable(self, name: str) -> "PromptBuilder":
        """启用指定 Prompt 片段"""
        for section in self._sections:
            if section.name == name:
                section.enabled = True
        return self

    def remove(self, name: str) -> "PromptBuilder":
        """移除指定 Prompt 片段"""
        self._sections = [s for s in self._sections if s.name != name]
        return self

    def get_section(self, name: str) -> Optional[PromptSection]:
        """获取指定片段"""
        for section in self._sections:
            if section.name == name:
                return section
        return None

    # ── 构建 ─────────────────────────────────────────────

    def build(self) -> str:
        """
        按优先级排序并拼接所有 Prompt 片段
        
        Returns:
            完整的 System Prompt 字符串
        """
        active_sections = [s for s in self._sections if s.enabled]
        sorted_sections = sorted(active_sections, key=lambda s: s.priority)

        parts = []
        for section in sorted_sections:
            content = section.content.strip()
            if content:
                parts.append(content)

        return "\n\n---\n\n".join(parts)

    def build_with_sections(self) -> tuple[str, List[PromptSection]]:
        """
        构建并返回详细片段信息（用于调试）
        
        Returns:
            (完整 prompt, 使用的片段列表)
        """
        active_sections = [s for s in self._sections if s.enabled]
        sorted_sections = sorted(active_sections, key=lambda s: s.priority)
        return self.build(), sorted_sections

    # ── 预置构建流程 ────────────────────────────────────

    def build_full(self) -> str:
        """
        构建完整的 System Prompt
        包含身份、规范、记忆、Skills、上下文
        """
        return (
            self
            .load_identity()
            .load_agents_md()
            .load_memory()
            .load_today_log()
            .load_skills()
            .inject_working_directory()
            .inject_datetime()
            .build()
        )


# ── 快捷函数 ────────────────────────────────────────────

def build_system_prompt(
    workspace: str = ".",
    include_identity: bool = True,
    include_agents_md: bool = True,
    include_memory: bool = True,
    include_skills: bool = True,
    skill_names: List[str] = None,
    extra_context: dict = None,
) -> str:
    """
    快速构建 System Prompt 的便捷函数
    
    Args:
        workspace: 工作目录
        include_identity: 是否加载身份
        include_agents_md: 是否加载 AGENTS.md
        include_memory: 是否加载记忆
        include_skills: 是否加载 Skills
        skill_names: 指定加载的 Skills
        extra_context: 额外的上下文信息
    """
    builder = PromptBuilder(workspace)
    
    if include_identity:
        builder.load_identity()
    if include_agents_md:
        builder.load_agents_md()
    if include_memory:
        builder.load_memory()
    if include_skills:
        builder.load_skills(skill_names)
    
    builder.inject_working_directory()
    builder.inject_datetime()
    
    if extra_context:
        for key, value in extra_context.items():
            builder.inject(key, str(value))
    
    return builder.build()
