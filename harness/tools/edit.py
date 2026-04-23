# harness/tools/edit.py
# 多级模糊匹配的文件编辑工具

import re
import difflib
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class EditResult:
    """编辑结果"""
    success: bool
    message: str
    match_level: str = ""   # 使用了哪一级匹配
    diff: str = ""          # 变更差异


class EditTool:
    """
    多级模糊匹配的文件编辑工具
    
    匹配策略（按优先级）：
    1. 精确匹配（最优先）
    2. 空白标准化后匹配
    3. 行号区间匹配
    4. 模糊相似度匹配（最后兜底）
    """

    # 模糊匹配的相似度阈值
    FUZZY_THRESHOLD = 0.85
    
    def __init__(self, auto_create_dirs: bool = True):
        """
        初始化 EditTool
        
        Args:
            auto_create_dirs: 当文件所在目录不存在时是否自动创建
        """
        self.auto_create_dirs = auto_create_dirs

    async def edit(
        self,
        path: str,
        old_str: str,
        new_str: str,
        fuzzy: bool = True,
    ) -> str:
        """
        编辑文件中的指定内容
        
        Args:
            path: 文件路径
            old_str: 要替换的原始内容
            new_str: 替换后的新内容
            fuzzy: 是否启用模糊匹配
            
        Returns:
            操作结果描述
        """
        file_path = Path(path)
        
        # 边界处理：old_str 为空 → 在文件末尾追加
        if not old_str:
            return await self._append_to_file(file_path, new_str)
        
        # 边界处理：new_str 为空 → 删除 old_str
        if not new_str:
            return await self._delete_from_file(file_path, old_str, fuzzy)
        
        # 检查文件是否存在
        if not file_path.exists():
            # 边界处理：文件不存在且有 new_str → 创建新文件
            if self.auto_create_dirs:
                return await self._create_file(file_path, new_str)
            return f"错误：文件不存在 - {path}"
        
        try:
            original_content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"错误：读取文件失败 - {e}"
        
        # 检查 old_str 是否唯一
        occurrences = original_content.count(old_str)
        if occurrences > 1:
            return (
                f"警告：目标内容在文件中出现 {occurrences} 次。"
                f"请提供更多上下文以唯一定位目标位置。"
            )
        
        result = self._try_edit(original_content, old_str, new_str, fuzzy)
        
        if result.success:
            new_content = original_content.replace(old_str, new_str, 1)
            if result.match_level != "exact":
                # 非精确匹配时，使用实际找到的片段替换
                new_content = result.new_content
            
            file_path.write_text(new_content, encoding="utf-8")
            return f"✓ 编辑成功 [{result.match_level}]\n{result.diff}"
        else:
            return result.message

    async def _append_to_file(self, file_path: Path, content: str) -> str:
        """追加内容到文件末尾"""
        try:
            existing = ""
            if file_path.exists():
                existing = file_path.read_text(encoding="utf-8")
                # 确保有换行分隔
                if existing and not existing.endswith("\n"):
                    existing += "\n"
            
            file_path.write_text(existing + content, encoding="utf-8")
            return f"✓ 已追加内容到文件末尾: {file_path}"
        except Exception as e:
            return f"错误：追加文件失败 - {e}"

    async def _delete_from_file(self, file_path: Path, old_str: str, fuzzy: bool) -> str:
        """从文件中删除指定内容"""
        try:
            original_content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"错误：读取文件失败 - {e}"
        
        if old_str not in original_content:
            if not fuzzy:
                return self._format_not_found_error(original_content, old_str)
            
            # 尝试模糊匹配
            result = self._fuzzy_line_match(original_content, old_str, "")
            if result and result.success:
                file_path.write_text(result.new_content, encoding="utf-8")
                return f"✓ 删除成功 [模糊匹配]"
            return self._format_not_found_error(original_content, old_str)
        
        new_content = original_content.replace(old_str, "", 1)
        file_path.write_text(new_content, encoding="utf-8")
        return f"✓ 已删除指定内容"

    async def _create_file(self, file_path: Path, content: str) -> str:
        """创建新文件"""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"✓ 已创建新文件: {file_path}"
        except Exception as e:
            return f"错误：创建文件失败 - {e}"

    def _try_edit(
        self,
        content: str,
        old_str: str,
        new_str: str,
        fuzzy: bool,
    ) -> EditResult:
        """尝试多级匹配"""
        
        # ── 第一级：精确匹配 ──────────────────────────────────
        if old_str in content:
            new_content = content.replace(old_str, new_str, 1)
            return EditResult(
                success=True,
                message="精确匹配成功",
                match_level="exact",
                new_content=new_content,
                diff=self._make_diff(old_str, new_str),
            )

        if not fuzzy:
            return EditResult(
                success=False,
                message=self._format_not_found_error(content, old_str),
            )

        # ── 第二级：空白标准化匹配 ────────────────────────────
        normalized_content = self._normalize_whitespace(content)
        normalized_old = self._normalize_whitespace(old_str)

        if normalized_old in normalized_content:
            # 找到原始内容中对应的位置
            actual_old = self._find_actual_span(content, old_str)
            if actual_old:
                new_content = content.replace(actual_old, new_str, 1)
                return EditResult(
                    success=True,
                    message="空白标准化匹配成功",
                    match_level="whitespace_normalized",
                    new_content=new_content,
                    diff=self._make_diff(actual_old, new_str),
                )

        # ── 第三级：行级模糊匹配 ──────────────────────────────
        fuzzy_result = self._fuzzy_line_match(content, old_str, new_str)
        if fuzzy_result:
            return fuzzy_result

        # ── 所有级别都失败 ────────────────────────────────────
        return EditResult(
            success=False,
            message=self._format_not_found_error(content, old_str),
        )

    def _normalize_whitespace(self, text: str) -> str:
        """标准化空白字符"""
        # 统一换行符
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # 去除行尾空格
        lines = [line.rstrip() for line in text.split("\n")]
        return "\n".join(lines)

    def _find_actual_span(self, content: str, target: str) -> Optional[str]:
        """
        在原始内容中找到与 target 语义相同（忽略空白差异）的实际片段
        """
        target_lines = [l.strip() for l in target.split("\n") if l.strip()]
        if not target_lines:
            return None

        content_lines = content.split("\n")
        first_line = target_lines[0]

        for i, line in enumerate(content_lines):
            if line.strip() == first_line:
                # 找到可能的起始行，尝试匹配后续行
                end_idx = i
                matched_lines = 0
                for j, tl in enumerate(target_lines):
                    if i + j < len(content_lines) and content_lines[i + j].strip() == tl:
                        matched_lines += 1
                        end_idx = i + j

                if matched_lines == len(target_lines):
                    # 完全匹配，返回原始片段
                    return "\n".join(content_lines[i:end_idx + 1])

        return None

    def _fuzzy_line_match(
        self,
        content: str,
        old_str: str,
        new_str: str,
    ) -> Optional[EditResult]:
        """
        基于相似度的模糊行匹配
        使用 difflib 计算相似度
        """
        content_lines = content.split("\n")
        old_lines = old_str.split("\n")
        n = len(old_lines)
        
        # 至少需要匹配 2 行以上才使用模糊匹配
        if n < 2:
            return None

        best_ratio = 0.0
        best_start = -1

        # 滑动窗口搜索最相似的片段
        for i in range(len(content_lines) - n + 1):
            window = content_lines[i:i + n]
            window_str = "\n".join(window)

            ratio = difflib.SequenceMatcher(
                None, old_str, window_str
            ).ratio()

            if ratio > best_ratio:
                best_ratio = ratio
                best_start = i

        if best_ratio >= self.FUZZY_THRESHOLD and best_start >= 0:
            actual_old = "\n".join(content_lines[best_start:best_start + n])
            new_content = content.replace(actual_old, new_str, 1)

            return EditResult(
                success=True,
                message=f"模糊匹配成功（相似度 {best_ratio:.1%}）",
                match_level=f"fuzzy_{best_ratio:.0%}",
                new_content=new_content,
                diff=self._make_diff(actual_old, new_str),
            )

        return None

    def _make_diff(self, old: str, new: str) -> str:
        """生成可读的差异说明"""
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile="before", tofile="after",
            n=2,
        )
        return "".join(list(diff)[:30])  # 最多显示 30 行 diff

    def _format_not_found_error(self, content: str, old_str: str) -> str:
        """生成详细的未找到错误信息，帮助 Agent 自我修正"""
        # 找最相似的片段给 Agent 参考
        old_lines = old_str.split("\n")
        content_lines = content.split("\n")

        # 取 old_str 的第一行，在文件中搜索类似内容
        first_line = old_lines[0].strip() if old_lines else ""
        similar_lines = [
            (i + 1, line)
            for i, line in enumerate(content_lines)
            if first_line and difflib.SequenceMatcher(None, first_line, line.strip()).ratio() > 0.6
        ]

        msg = f"错误：在文件中未找到目标内容。\n"
        msg += f"目标片段（前 3 行）:\n"
        for line in old_lines[:3]:
            msg += f"  | {repr(line)}\n"

        if similar_lines:
            msg += f"\n文件中最相似的行:\n"
            for lineno, line in similar_lines[:3]:
                msg += f"  行 {lineno}: {repr(line)}\n"

        return msg
