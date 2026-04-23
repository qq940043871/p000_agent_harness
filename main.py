#!/usr/bin/env python3
# main.py - OpenClaw Agent Harness CLI 入口

"""
OpenClaw Agent Harness - CLI 入口

用法:
    # 单次任务
    python main.py "帮我分析当前目录的项目结构"
    
    # 交互模式
    python main.py
    
    # 指定工作目录
    python main.py -w /path/to/project "执行的任务"
    
    # 使用特定 Provider
    python main.py --provider openai "任务描述"
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from harness import (
    MainLoop,
    ToolRegistry,
    PromptBuilder,
    SessionManager,
    create_provider,
    load_provider_from_yaml,
)
from harness.tools import EditTool
from harness.tools.plugins import register_all_tools


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def setup_parser() -> argparse.ArgumentParser:
    """设置命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="OpenClaw Agent Harness - Agent 运行时框架",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "task",
        nargs="?",
        help="要执行的任务（不提供则进入交互模式）",
    )
    
    parser.add_argument(
        "-w", "--workspace",
        default=".",
        help="工作目录（默认：当前目录）",
    )
    
    parser.add_argument(
        "--provider",
        choices=["doubao", "claude", "openai", "qwen", "deepseek"],
        help="使用的 LLM Provider（默认：从配置文件读取）",
    )
    
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="配置文件路径（默认：config.yaml）",
    )
    
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="强制进入交互模式",
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细日志",
    )
    
    return parser


def load_config(config_path: str, provider_name: str = None, workspace: str = "."):
    """加载配置并创建 Provider"""
    config_file = Path(workspace) / config_path
    
    if config_file.exists():
        return load_provider_from_yaml(str(config_file), provider_name)
    
    # 没有配置文件时的默认配置
    logger.warning(f"配置文件 {config_path} 不存在，使用默认配置")
    
    provider_type = provider_name or "claude"
    
    if provider_type == "claude":
        import os
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("请设置 ANTHROPIC_API_KEY 环境变量，或提供配置文件")
        return create_provider("claude", api_key=api_key)
    
    raise ValueError(f"不支持的 Provider: {provider_type}，请创建配置文件")


def create_agent(workspace: str = "."):
    """创建 Agent 实例"""
    # 1. 创建工具注册表
    registry = ToolRegistry()
    
    # 2. 注册内置工具
    register_all_tools(registry, workspace)
    
    # 3. 注册 Edit 工具
    edit_tool = EditTool()
    
    @registry.tool(
        description=(
            "精确编辑文件中的特定内容。将 old_str 替换为 new_str。"
            "old_str 必须在文件中唯一存在。支持模糊匹配以容忍轻微空白差异。"
        ),
        category="filesystem",
    )
    async def edit_file(path: str, old_str: str, new_str: str) -> str:
        return await edit_tool.edit(path, old_str, new_str)
    
    # 4. 加载配置
    provider = load_config("config.yaml", workspace=workspace)
    
    # 5. 构建 System Prompt
    builder = PromptBuilder(workspace)
    system_prompt = builder.build_full()
    
    # 6. 创建 Main Loop
    loop = MainLoop(
        provider=provider,
        tool_registry=registry,
        system_prompt=system_prompt,
        max_turns=50,
    )
    
    return loop


async def run_single_task(task: str, workspace: str = "."):
    """执行单个任务"""
    print(f"📋 任务: {task}")
    print(f"📁 工作目录: {workspace}")
    print("-" * 60)
    
    loop = create_agent(workspace)
    
    try:
        result = await loop.run(task)
        
        print("\n" + "=" * 60)
        print("📊 执行结果")
        print("=" * 60)
        print(f"状态: {result.status.value}")
        print(f"轮次: {result.stats.turns}")
        print(f"Token: {result.stats.total_tokens}")
        print(f"耗时: {result.stats.elapsed:.2f}s")
        
        if result.error:
            print(f"错误: {result.error}")
        
        print("\n" + "-" * 60)
        print("📝 输出")
        print("-" * 60)
        print(result.content or "(无文本输出)")
        
        return result.is_success()
    
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        return False


async def run_interactive(workspace: str = "."):
    """交互模式"""
    print("=" * 60)
    print("OpenClaw Agent Harness - 交互模式")
    print("=" * 60)
    print("输入任务描述，Agent 将为你执行。")
    print("输入 'exit' 或 'quit' 退出。")
    print("输入 'clear' 清除对话历史。")
    print("-" * 60)
    
    loop = create_agent(workspace)
    session_manager = SessionManager(workspace)
    
    messages_history = []
    
    while True:
        try:
            user_input = input("\n👤 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        
        if not user_input:
            continue
        
        if user_input.lower() in ["exit", "quit", "q"]:
            print("再见！")
            break
        
        if user_input.lower() == "clear":
            messages_history = []
            print("✅ 对话历史已清除")
            continue
        
        # 创建新 Session
        session = session_manager.new_session(user_input[:50])
        
        # 添加用户消息
        messages_history.append({"role": "user", "content": user_input})
        session.append_message({"role": "user", "content": user_input})
        
        print("\n🤖 Agent: 处理中...")
        
        try:
            # 构建上下文
            context_prompt = "\n".join([
                f"{'用户' if m['role'] == 'user' else '助手'}: {m['content']}"
                for m in messages_history[-5:]  # 只用最近 5 轮
            ])
            
            # 执行
            result = await loop.run(context_prompt)
            
            # 输出结果
            print(f"\n🤖 Agent: {result.content}")
            
            # 记录
            messages_history.append({"role": "assistant", "content": result.content})
            session.append_message({"role": "assistant", "content": result.content})
            session.mark_completed()
            
            print(f"\n📊 统计: {result.stats.turns}轮 | {result.stats.total_tokens} tokens")
            
        except Exception as e:
            print(f"\n❌ 错误: {e}")
            session.mark_failed()


async def main():
    """主函数"""
    parser = setup_parser()
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 确定运行模式
    if args.task and not args.interactive:
        # 单任务模式
        success = await run_single_task(args.task, args.workspace)
        sys.exit(0 if success else 1)
    else:
        # 交互模式
        await run_interactive(args.workspace)


if __name__ == "__main__":
    asyncio.run(main())
