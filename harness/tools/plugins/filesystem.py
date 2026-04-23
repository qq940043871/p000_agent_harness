# harness/tools/plugins/filesystem.py
# 文件系统工具集 - 基本文件操作

import os
import subprocess
from pathlib import Path
from typing import Optional

from ..registry import ToolRegistry


def register_filesystem_tools(registry: ToolRegistry, workspace: str = "."):
    """
    注册文件系统工具集
    
    Args:
        registry: 工具注册表实例
        workspace: 工作目录
    """
    
    @registry.tool(
        description="列出目录内容。返回所有文件和文件夹的名称。",
        category="filesystem",
    )
    async def list_dir(path: str = None) -> str:
        """
        列出目录内容
        
        Args:
            path: 目录路径，默认当前目录
        """
        target = Path(workspace) / (path or ".")
        try:
            entries = []
            for entry in sorted(target.iterdir()):
                icon = "📁" if entry.is_dir() else "📄"
                entries.append(f"{icon} {entry.name}")
            return "\n".join(entries) if entries else "(空目录)"
        except FileNotFoundError:
            return f"错误：目录不存在 - {target}"
        except PermissionError:
            return f"错误：没有权限访问 - {target}"
        except Exception as e:
            return f"错误：{e}"
    
    @registry.tool(
        description="读取文件内容。返回文件的完整文本内容。",
        category="filesystem",
    )
    async def read_file(path: str, start_line: int = 1, max_lines: int = None) -> str:
        """
        读取文件内容
        
        Args:
            path: 文件路径
            start_line: 起始行号（从1开始）
            max_lines: 最大读取行数
        """
        file_path = Path(workspace) / path
        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            
            # 处理行号
            start_idx = max(0, start_line - 1)
            end_idx = len(lines) if max_lines is None else start_idx + max_lines
            
            result_lines = lines[start_idx:end_idx]
            result = "\n".join(result_lines)
            
            # 添加上下文信息
            info = f"--- {file_path} (行 {start_line}-{end_idx}) ---\n"
            if len(lines) > end_idx:
                info += f"[... 共 {len(lines)} 行，只显示前 {end_idx} 行 ...]\n"
            
            return info + result
        except FileNotFoundError:
            return f"错误：文件不存在 - {file_path}"
        except PermissionError:
            return f"错误：没有权限读取 - {file_path}"
        except Exception as e:
            return f"错误：读取失败 - {e}"
    
    @registry.tool(
        description="写入或创建文件。如果文件已存在会被覆盖。",
        category="filesystem",
    )
    async def write_file(path: str, content: str) -> str:
        """
        写入文件
        
        Args:
            path: 文件路径
            content: 文件内容
        """
        file_path = Path(workspace) / path
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"✓ 已写入 {len(content)} 字符到 {file_path}"
        except PermissionError:
            return f"错误：没有写入权限 - {file_path}"
        except Exception as e:
            return f"错误：写入失败 - {e}"
    
    @registry.tool(
        description="搜索文件。按名称模式查找文件。",
        category="filesystem",
    )
    async def find_files(pattern: str, path: str = None) -> str:
        """
        搜索文件
        
        Args:
            pattern: 文件名模式（支持 *  wildcard）
            path: 搜索目录，默认当前目录
        """
        import fnmatch
        
        target = Path(workspace) / (path or ".")
        matches = []
        try:
            for root, dirs, files in os.walk(target):
                for name in files:
                    if fnmatch.fnmatch(name.lower(), pattern.lower()):
                        rel_path = Path(root) / name
                        matches.append(str(rel_path.relative_to(target)))
            if matches:
                return "\n".join(sorted(matches))
            return f"未找到匹配 '{pattern}' 的文件"
        except Exception as e:
            return f"错误：搜索失败 - {e}"
    
    @registry.tool(
        description="搜索文件内容。在文件中搜索包含关键词的行。",
        category="filesystem",
    )
    async def grep_files(pattern: str, path: str = None, file_pattern: str = "*.py") -> str:
        """
        搜索文件内容
        
        Args:
            pattern: 要搜索的文本
            path: 搜索目录，默认当前目录
            file_pattern: 文件类型过滤（如 *.py, *.md）
        """
        import fnmatch
        
        target = Path(workspace) / (path or ".")
        matches = []
        try:
            for root, dirs, files in os.walk(target):
                for name in files:
                    if fnmatch.fnmatch(name, file_pattern):
                        file_path = Path(root) / name
                        try:
                            for i, line in enumerate(file_path.read_text(encoding="utf-8").split("\n"), 1):
                                if pattern.lower() in line.lower():
                                    matches.append(f"{file_path}:{i}: {line.strip()}")
                        except:
                            pass  # 跳过无法读取的文件
            if matches:
                return "\n".join(matches[:100])  # 限制结果数量
            return f"未找到包含 '{pattern}' 的内容"
        except Exception as e:
            return f"错误：搜索失败 - {e}"
    
    @registry.tool(
        description="获取文件或目录的详细信息",
        category="filesystem",
    )
    async def stat(path: str) -> str:
        """
        获取文件信息
        
        Args:
            path: 文件或目录路径
        """
        file_path = Path(workspace) / path
        try:
            stat = file_path.stat()
            info = [
                f"路径: {file_path.absolute()}",
                f"类型: {'目录' if file_path.is_dir() else '文件'}",
                f"大小: {stat.st_size} 字节",
                f"创建时间: {stat.st_ctime}",
                f"修改时间: {stat.st_mtime}",
            ]
            return "\n".join(info)
        except FileNotFoundError:
            return f"错误：不存在 - {file_path}"
        except Exception as e:
            return f"错误：{e}"


def register_system_tools(registry: ToolRegistry):
    """
    注册系统工具集
    """
    
    @registry.tool(
        description="执行 shell 命令并返回输出。用于运行程序、安装包等。",
        category="system",
    )
    async def bash(command: str, cwd: str = None, timeout: int = 30) -> str:
        """
        执行 shell 命令
        
        Args:
            command: 要执行的命令
            cwd: 工作目录
            timeout: 超时时间（秒）
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout,
            )
            output = []
            if result.stdout:
                output.append(f"[stdout]\n{result.stdout}")
            if result.stderr:
                output.append(f"[stderr]\n{result.stderr}")
            if result.returncode != 0:
                output.append(f"[exit code: {result.returncode}]")
            return "\n".join(output) if output else "(无输出)"
        except subprocess.TimeoutExpired:
            return f"错误：命令执行超时（{timeout}秒）"
        except Exception as e:
            return f"错误：{e}"
    
    @registry.tool(
        description="获取当前工作目录和基本系统信息",
        category="system",
    )
    async def get_working_directory() -> str:
        """获取当前工作目录"""
        import platform
        import os
        return (
            f"工作目录: {os.getcwd()}\n"
            f"平台: {platform.system()} {platform.release()}\n"
            f"Python: {platform.python_version()}"
        )


def register_all_tools(registry: ToolRegistry, workspace: str = "."):
    """
    注册所有内置工具
    
    Usage:
        registry = ToolRegistry()
        register_all_tools(registry, "/path/to/project")
    """
    register_filesystem_tools(registry, workspace)
    register_system_tools(registry)
