#!/usr/bin/env python3
"""
Agent Harness - 图形用户界面 (GUI)
基于 PyQt6 实现，支持深色主题

@author: OpenClaw Team
@date: 2026-04-22
"""

import asyncio
import json
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTextBrowser,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from harness import MainLoop, ToolRegistry, create_provider
from harness.cost_tracker import CostTracker
from harness.memory_manager import create_memory_manager
from harness.tracer import Tracer


# ============================================================================
# Worker Thread - 在后台线程运行 Agent
# ============================================================================


class AgentWorker(QThread):
    """后台运行 Agent 的 Worker 线程"""

    # 信号定义
    started = pyqtSignal()
    finished = pyqtSignal(str)  # 返回最终结果
    error = pyqtSignal(str)  # 错误信息
    token_update = pyqtSignal(int, int, float)  # prompt_tokens, completion_tokens, cost
    tool_called = pyqtSignal(str, str)  # tool_name, arguments
    tool_result = pyqtSignal(str, str)  # tool_name, result
    thinking = pyqtSignal(str)  # 思考过程

    def __init__(
        self,
        prompt: str,
        provider_config: dict,
        workspace: str,
        max_turns: int = 50,
        parent=None,
    ):
        super().__init__(parent)
        self.prompt = prompt
        self.provider_config = provider_config
        self.workspace = workspace
        self.max_turns = max_turns
        self._running = True

    def run(self):
        """在线程中运行 Agent"""
        loop = None
        try:
            self.started.emit()

            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._run_agent(loop))
            # LoopResult 序列化为 JSON 字符串
            import json
            self.finished.emit(json.dumps({
                "content": result.content,
                "status": str(result.status.value) if hasattr(result.status, 'value') else str(result.status),
            }, ensure_ascii=False))

        except Exception as e:
            self.error.emit(str(e))
        finally:
            if loop:
                loop.close()

    async def _run_agent(self, loop):
        """实际运行 Agent 的异步函数"""
        from harness.tools.plugins import register_all_tools

        # 参考 web.py 的逻辑：只有部分 provider 支持 base_url
        provider_type = self.provider_config.get("provider_type")
        base_url = self.provider_config.get("base_url")
        
        # 构建 create_provider 的参数
        create_kwargs = {
            "provider_type": provider_type,
            "api_key": self.provider_config["api_key"],
            "model": self.provider_config.get("model", ""),
        }
        
        # 只有 deepseek/openai/openai_compat 支持 base_url
        if provider_type in ("deepseek", "openai", "openai_compat") and base_url:
            create_kwargs["base_url"] = base_url
        
        # 只有 claude 支持 model_kwargs
        if provider_type == "claude":
            create_kwargs["model_kwargs"] = self.provider_config.get("model_kwargs", {})
        
        # 创建 Provider
        provider = create_provider(**create_kwargs)
        
        registry = ToolRegistry()
        register_all_tools(registry, self.workspace)

        # 可选组件
        cost_tracker = CostTracker()
        tracer = Tracer()
        memory = create_memory_manager(self.workspace)

        # 创建 MainLoop
        main_loop = MainLoop(
            provider=provider,
            tool_registry=registry,
            cost_tracker=cost_tracker,
            tracer=tracer,
            max_turns=self.max_turns,
        )

        # 设置回调
        def on_token_update(prompt_tokens: int, completion_tokens: int, cost: float, total_tokens: int = 0):
            self.token_update.emit(prompt_tokens, completion_tokens, cost)

        def on_tool_call(tool_name: str, arguments: str):
            self.tool_called.emit(tool_name, arguments)

        def on_tool_result(tool_name: str, result: str):
            self.tool_result.emit(tool_name, result)

        def on_thinking(content: str):
            self.thinking.emit(content)

        main_loop.on("token_update", on_token_update)
        main_loop.on("tool_call", on_tool_call)
        main_loop.on("tool_result", on_tool_result)
        main_loop.on("thinking", on_thinking)

        # 运行
        result = await main_loop.run(self.prompt)
        return result


# ============================================================================
# 设置对话框
# ============================================================================


class SettingsDialog(QDialog):
    """设置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Provider 设置
        provider_group = QWidget()
        provider_layout = QVBoxLayout()

        # Provider 类型
        provider_options = [
            "volcengine_plan: 火山引擎 Coding Plan ⭐",
            "claude: Claude",
            "openai: OpenAI",
            "doubao: 豆包",
            "qwen: 通义千问",
            "deepseek: DeepSeek",
        ]
        self.provider_combo = self._create_combo(provider_options, "LLM Provider")
        provider_layout.addWidget(self.provider_combo)

        # API Key
        self.api_key_input = self._create_input("API Key", placeholder="从 config.yaml 读取或手动输入")
        provider_layout.addWidget(self.api_key_input)

        # Model
        self.model_input = self._create_input("Model", placeholder="ark-code-latest")
        provider_layout.addWidget(self.model_input)

        # Base URL (可选)
        self.base_url_input = self._create_input("Base URL (可选)", placeholder="留空使用默认")
        provider_layout.addWidget(self.base_url_input)

        provider_group.setLayout(provider_layout)
        layout.addWidget(QLabel("<b>LLM Provider</b>"))
        layout.addWidget(provider_group)

        # Agent 设置
        agent_group = QWidget()
        agent_layout = QVBoxLayout()

        self.max_turns_input = self._create_input("Max Turns", placeholder="50")
        agent_layout.addWidget(self.max_turns_input)

        self.temperature_input = self._create_input("Temperature", placeholder="0.7")
        agent_layout.addWidget(self.temperature_input)

        agent_group.setLayout(agent_layout)
        layout.addWidget(QLabel("<b>Agent Settings</b>"))
        layout.addWidget(agent_group)

        # 按钮
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # 从 config.yaml 加载默认配置
        self._load_from_yaml()

    def _load_from_yaml(self):
        """从 config.yaml 加载默认配置"""
        import yaml
        config_file = Path(__file__).parent / "config.yaml"
        
        if not config_file.exists():
            return
        
        try:
            with open(config_file, encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f)
            
            # 获取默认 provider
            default_provider = yaml_config.get("default_provider", "volcengine_plan")
            provider_config = yaml_config.get("providers", {}).get(default_provider, {})
            
            # 设置 API Key
            api_key = provider_config.get("api_key", "")
            if api_key and not api_key.startswith("YOUR-"):
                self.api_key_input.findChild(QLineEdit).setText(api_key)
            
            # 设置 Model
            model = provider_config.get("model", "")
            if model:
                self.model_input.findChild(QLineEdit).setText(model)
            
            # 设置 Provider 类型
            provider_map = {
                "volcengine_plan": 0,
                "claude": 1,
                "openai": 2,
                "doubao": 3,
                "qwen": 4,
                "deepseek": 5,
            }
            combo = self.provider_combo.findChild(QComboBox)
            if default_provider in provider_map:
                combo.setCurrentIndex(provider_map[default_provider])
            
            # 设置 Agent 配置
            agent_config = yaml_config.get("agent", {})
            max_turns = agent_config.get("max_turns", 50)
            temperature = agent_config.get("temperature", 0.7)
            self.max_turns_input.findChild(QLineEdit).setText(str(max_turns))
            self.temperature_input.findChild(QLineEdit).setText(str(temperature))
        except Exception as e:
            print(f"[GUI] 加载配置文件失败: {e}")

    def _create_combo(self, options, label):
        layout = QHBoxLayout()
        layout.addWidget(QLabel(label))
        combo = QComboBox()
        combo.addItems(options)
        layout.addWidget(combo)
        container = QWidget()
        container.setLayout(layout)
        return container

    def _create_input(self, label, placeholder=""):
        layout = QHBoxLayout()
        layout.addWidget(QLabel(label))
        line_edit = QLineEdit()
        line_edit.setPlaceholderText(placeholder)
        layout.addWidget(line_edit)
        container = QWidget()
        container.setLayout(layout)
        return container

    def get_config(self):
        """获取配置"""
        provider_text = self.provider_combo.findChild(QComboBox).currentText()
        # 提取 provider 类型（如 "volcengine_plan"）
        provider_type = provider_text.split(":")[0].strip()
        
        return {
            "provider_type": provider_type,
            "api_key": self.api_key_input.findChild(QLineEdit).text(),
            "model": self.model_input.findChild(QLineEdit).text(),
            "base_url": self.base_url_input.findChild(QLineEdit).text() or None,
            "max_turns": int(self.max_turns_input.findChild(QLineEdit).text() or "50"),
            "temperature": float(self.temperature_input.findChild(QLineEdit).text() or "0.7"),
        }


# ============================================================================
# 主窗口
# ============================================================================


class AgentHarnessGUI(QMainWindow):
    """Agent Harness 主窗口"""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.conversation_history = []
        self.config = self._load_default_config()
        self.init_ui()

    def _load_default_config(self):
        """加载默认配置，优先从 config.yaml 读取"""
        import yaml
        config_file = Path(__file__).parent / "config.yaml"
        
        if not config_file.exists():
            return {
                "provider_type": "volcengine_plan",
                "api_key": "",
                "model": "ark-code-latest",
                "base_url": None,
                "max_turns": 50,
                "temperature": 0.7,
            }
        
        try:
            with open(config_file, encoding="utf-8") as f:
                yaml_config = yaml.safe_load(f)
            
            default_provider = yaml_config.get("default_provider", "volcengine_plan")
            provider_config = yaml_config.get("providers", {}).get(default_provider, {})
            agent_config = yaml_config.get("agent", {})
            
            return {
                "provider_type": default_provider,
                "api_key": provider_config.get("api_key", ""),
                "model": provider_config.get("model", ""),
                "base_url": provider_config.get("base_url"),
                "max_turns": agent_config.get("max_turns", 50),
                "temperature": agent_config.get("temperature", 0.7),
            }
        except Exception as e:
            print(f"[GUI] 加载配置文件失败: {e}")
            return {
                "provider_type": "volcengine_plan",
                "api_key": "",
                "model": "ark-code-latest",
                "base_url": None,
                "max_turns": 50,
                "temperature": 0.7,
            }

    def init_ui(self):
        """初始化 UI"""
        self.setWindowTitle("Agent Harness - OpenClaw GUI")
        self.setMinimumSize(1200, 800)

        # 深色主题样式
        self.setStyleSheet(self._get_dark_theme())

        # 创建菜单栏
        self._create_menu_bar()

        # 创建工具栏
        self._create_tool_bar()

        # 创建主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # 左侧：会话历史
        left_panel = self._create_left_panel()
        main_layout.addWidget(left_panel, 1)

        # 右侧：主工作区
        right_panel = self._create_right_panel()
        main_layout.addWidget(right_panel, 3)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def _get_dark_theme(self):
        """现代化深色主题样式"""
        return """
        /* ========== 全局样式 ========== */
        QMainWindow {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                stop:0 #0f0c29, stop:0.5 #302b63, stop:1 #24243e);
            color: #e0e0e0;
        }
        QWidget {
            background: transparent;
            color: #e0e0e0;
            font-family: 'Segoe UI', 'Microsoft YaHei', -apple-system, sans-serif;
            font-size: 13px;
        }
        
        /* ========== 卡片式容器 ========== */
        .card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 16px;
        }
        
        /* ========== 按钮样式 ========== */
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #667eea, stop:1 #764ba2);
            color: white;
            border: none;
            padding: 10px 24px;
            border-radius: 25px;
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        QPushButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #7c8ffa, stop:1 #8d5bb5);
            padding: 11px 25px;
        }
        QPushButton:pressed {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #5568d4, stop:1 #6b4190);
        }
        QPushButton:disabled {
            background: rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.3);
        }
        
        /* 运行按钮特殊样式 */
        QPushButton#runBtn {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #11998e, stop:1 #38ef7d);
            min-width: 140px;
        }
        QPushButton#runBtn:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #12b19e, stop:1 #45f58a);
        }
        
        /* 停止按钮特殊样式 */
        QPushButton#stopBtn {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #eb3349, stop:1 #f45c43);
        }
        QPushButton#stopBtn:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #f04459, stop:1 #f67063);
        }
        
        /* 工具栏按钮 */
        QToolBar QPushButton {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 6px 12px;
        }
        QToolBar QPushButton:hover {
            background: rgba(255, 255, 255, 0.2);
        }
        
        /* ========== 文本编辑框 ========== */
        QTextEdit, QPlainTextEdit, QTextBrowser {
            background: rgba(15, 15, 25, 0.8);
            color: #e0e0e0;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 12px;
            selection-background-color: rgba(102, 126, 234, 0.4);
        }
        QTextEdit:focus, QPlainTextEdit:focus {
            border: 1px solid rgba(102, 126, 234, 0.6);
        }
        
        /* ========== 输入框 ========== */
        QLineEdit {
            background: rgba(255, 255, 255, 0.05);
            color: #e0e0e0;
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 10px;
            padding: 10px 14px;
        }
        QLineEdit:focus {
            border: 2px solid rgba(102, 126, 234, 0.8);
            background: rgba(255, 255, 255, 0.08);
        }
        QLineEdit::placeholder {
            color: rgba(255, 255, 255, 0.3);
        }
        
        /* ========== 下拉框 ========== */
        QComboBox {
            background: rgba(255, 255, 255, 0.05);
            color: #e0e0e0;
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 10px;
            padding: 10px 14px;
            selection-background-color: rgba(102, 126, 234, 0.4);
        }
        QComboBox:hover {
            border: 1px solid rgba(102, 126, 234, 0.6);
        }
        QComboBox::drop-down {
            border: none;
            padding-right: 10px;
        }
        QComboBox::down-arrow {
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid rgba(255, 255, 255, 0.5);
        }
        QComboBox QAbstractItemView {
            background: rgba(30, 30, 50, 0.95);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            selection-background-color: rgba(102, 126, 234, 0.4);
        }
        
        /* ========== 菜单栏 ========== */
        QMenuBar {
            background: rgba(15, 15, 25, 0.8);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding: 4px;
        }
        QMenuBar::item {
            background: transparent;
            color: #e0e0e0;
            padding: 8px 16px;
            border-radius: 6px;
        }
        QMenuBar::item:selected {
            background: rgba(102, 126, 234, 0.3);
        }
        QMenuBar::item:pressed {
            background: rgba(102, 126, 234, 0.5);
        }
        QMenu {
            background: rgba(30, 30, 50, 0.95);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 8px;
        }
        QMenu::item {
            background: transparent;
            color: #e0e0e0;
            padding: 10px 24px;
            border-radius: 8px;
        }
        QMenu::item:selected {
            background: rgba(102, 126, 234, 0.4);
        }
        
        /* ========== 工具栏 ========== */
        QToolBar {
            background: rgba(20, 20, 35, 0.9);
            border: none;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding: 8px 16px;
            spacing: 12px;
        }
        QToolBar::separator {
            background: rgba(255, 255, 255, 0.1);
            width: 1px;
            margin: 4px 8px;
        }
        
        /* ========== 状态栏 ========== */
        QStatusBar {
            background: rgba(15, 15, 25, 0.9);
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            padding: 8px 16px;
            color: rgba(255, 255, 255, 0.6);
        }
        
        /* ========== 分割线 ========== */
        QSplitter::handle {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 2px;
        }
        QSplitter::handle:hover {
            background: rgba(102, 126, 234, 0.5);
        }
        
        /* ========== 标签样式 ========== */
        QLabel {
            color: #e0e0e0;
        }
        .label-title {
            font-size: 16px;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: 0.5px;
        }
        .label-info {
            background: rgba(102, 126, 234, 0.2);
            border: 1px solid rgba(102, 126, 234, 0.3);
            border-radius: 20px;
            padding: 6px 14px;
            color: #a8b4fc;
        }
        .label-success {
            background: rgba(56, 239, 125, 0.2);
            border: 1px solid rgba(56, 239, 125, 0.3);
            border-radius: 20px;
            padding: 6px 14px;
            color: #38ef7d;
        }
        .label-warning {
            background: rgba(255, 193, 7, 0.2);
            border: 1px solid rgba(255, 193, 7, 0.3);
            border-radius: 20px;
            padding: 6px 14px;
            color: #ffc107;
        }
        
        /* ========== 滚动条 ========== */
        QScrollBar:vertical {
            background: transparent;
            width: 8px;
            margin: 4px 0;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 4px;
            min-height: 30px;
        }
        QScrollBar::handle:vertical:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0;
        }
        QScrollBar:horizontal {
            background: transparent;
            height: 8px;
            margin: 0 4px;
            border-radius: 4px;
        }
        QScrollBar::handle:horizontal {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 4px;
            min-width: 30px;
        }
        """

    def _create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")
        new_action = QAction("新建会话", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_conversation)
        file_menu.addAction(new_action)

        open_workspace = QAction("打开工作目录...", self)
        open_workspace.setShortcut("Ctrl+O")
        open_workspace.triggered.connect(self.open_workspace)
        file_menu.addAction(open_workspace)

        save_chat = QAction("保存会话", self)
        save_chat.setShortcut("Ctrl+S")
        save_chat.triggered.connect(self.save_conversation)
        file_menu.addAction(save_chat)

        file_menu.addSeparator()
        settings_action = QAction("设置...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.show_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑")
        clear_action = QAction("清空输出", self)
        clear_action.triggered.connect(self.clear_output)
        edit_menu.addAction(clear_action)

        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _create_tool_bar(self):
        """创建工具栏"""
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Logo/标题
        logo_label = QLabel("🤖 Agent Harness")
        logo_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff; padding: 0 16px;")
        toolbar.addWidget(logo_label)
        
        toolbar.addSeparator()

        # 新建会话
        new_btn = QPushButton("✨ 新建会话")
        new_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.15);
                padding: 8px 16px;
                border-radius: 20px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.15);
            }
        """)
        new_btn.clicked.connect(self.new_conversation)
        toolbar.addWidget(new_btn)

        # 运行
        self.run_btn = QPushButton("▶️ 运行")
        self.run_btn.setObjectName("runBtn")
        self.run_btn.clicked.connect(self.run_agent)
        toolbar.addWidget(self.run_btn)

        # 停止
        self.stop_btn = QPushButton("⏹️ 停止")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.clicked.connect(self.stop_agent)
        self.stop_btn.setEnabled(False)
        toolbar.addWidget(self.stop_btn)

        toolbar.addSeparator()

        # 设置按钮
        settings_btn = QPushButton("⚙️ 设置")
        settings_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.1);
                padding: 8px 16px;
                border-radius: 20px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.12);
            }
        """)
        settings_btn.clicked.connect(self.show_settings)
        toolbar.addWidget(settings_btn)

    def _create_left_panel(self):
        """创建左侧面板 - 会话历史"""
        panel = QWidget()
        panel.setStyleSheet("""
            background: rgba(20, 20, 35, 0.7);
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)

        # 标题
        title = QLabel("📋 会话历史")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff; padding-bottom: 8px;")
        layout.addWidget(title)

        # 会话列表
        self.history_list = QTextBrowser()
        self.history_list.setStyleSheet("""
            QTextBrowser {
                background: rgba(10, 10, 20, 0.6);
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
        """)
        self.history_list.setOpenExternalLinks(True)
        layout.addWidget(self.history_list)

        return panel

    def _create_right_panel(self):
        """创建右侧面板 - 主工作区"""
        panel = QWidget()
        panel.setStyleSheet("""
            background: rgba(20, 20, 35, 0.5);
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # 顶部信息栏 - 使用渐变背景卡片
        info_bar = QWidget()
        info_bar.setStyleSheet("""
            background: rgba(102, 126, 234, 0.1);
            border: 1px solid rgba(102, 126, 234, 0.2);
            border-radius: 12px;
            padding: 12px;
        """)
        info_layout = QHBoxLayout(info_bar)
        info_layout.setSpacing(16)

        self.provider_label = QLabel(f"🤖 {self.config['provider_type']}")
        self.tokens_label = QLabel("📊 Tokens: 0 / 0")
        self.cost_label = QLabel("💰 Cost: $0.00")
        self.turns_label = QLabel("🔄 Turn: 0 / 0")

        for label in [self.provider_label, self.tokens_label, self.cost_label, self.turns_label]:
            label.setStyleSheet("padding: 6px 12px; background: rgba(0,0,0,0.2); border-radius: 8px; font-size: 12px;")
            info_layout.addWidget(label)

        info_layout.addStretch()
        layout.addWidget(info_bar)

        # 思考过程
        thinking_group = self._create_card_group("💭 思考过程", "thinking_output")
        self.thinking_output.setMaximumHeight(120)
        layout.addWidget(thinking_group)

        # 工具调用
        tools_group = self._create_card_group("🔧 工具调用", "tools_output")
        self.tools_output.setMaximumHeight(120)
        layout.addWidget(tools_group)

        # 主输出
        output_group = self._create_card_group("✨ 执行结果", "output_text")
        self.output_text.setPlaceholderText("<span style='color: #888;'>Agent 输出将显示在这里...</span>")
        layout.addWidget(output_group)

        # 输入框
        input_group = QWidget()
        input_group.setStyleSheet("""
            background: rgba(102, 126, 234, 0.08);
            border: 1px solid rgba(102, 126, 234, 0.15);
            border-radius: 16px;
            padding: 16px;
        """)
        input_layout = QVBoxLayout(input_group)
        input_layout.setSpacing(12)

        self.prompt_input = QPlainTextEdit()
        self.prompt_input.setPlaceholderText("💬 输入你的问题或指令...\n\n按 Ctrl+Enter 或点击「运行 Agent」执行")
        self.prompt_input.setMaximumHeight(100)
        self.prompt_input.setStyleSheet("""
            QPlainTextEdit {
                background: rgba(10, 10, 20, 0.8);
                border: 1px solid rgba(102, 126, 234, 0.3);
                border-radius: 12px;
                padding: 14px;
                color: #ffffff;
                font-size: 14px;
            }
            QPlainTextEdit:focus {
                border: 2px solid rgba(102, 126, 234, 0.6);
            }
        """)
        input_layout.addWidget(self.prompt_input)

        # 按钮行
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        # 清空按钮
        clear_btn = QPushButton("🗑️ 清空")
        clear_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.15);
                padding: 10px 20px;
                border-radius: 25px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 0.15);
            }
        """)
        clear_btn.clicked.connect(self.clear_output)
        btn_layout.addWidget(clear_btn)
        
        # 运行按钮
        run_btn = QPushButton("🚀 运行 Agent")
        run_btn.setObjectName("runBtn")
        run_btn.setMinimumWidth(160)
        run_btn.clicked.connect(self.run_agent)
        btn_layout.addWidget(run_btn)
        
        input_layout.addLayout(btn_layout)
        layout.addWidget(input_group)

        return panel
    
    def _create_card_group(self, title, attr_name):
        """创建卡片式分组"""
        group = QWidget()
        group.setStyleSheet("""
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 14px;
            padding: 12px;
        """)
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #ffffff; margin-bottom: 4px;")
        layout.addWidget(title_label)
        
        output = QTextBrowser()
        output.setStyleSheet("""
            QTextBrowser {
                background: rgba(10, 10, 20, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        setattr(self, attr_name, output)
        layout.addWidget(output)
        
        return group

    # =========================================================================
    # 事件处理
    # =========================================================================

    def new_conversation(self):
        """新建会话"""
        self.conversation_history.clear()
        self.output_text.clear()
        self.thinking_output.clear()
        self.tools_output.clear()
        self.prompt_input.clear()
        self.tokens_label.setText("Tokens: 0 / 0")
        self.cost_label.setText("Cost: $0.00")
        self.turns_label.setText("Turn: 0 / 0")
        self.status_bar.showMessage("新建会话")

    def open_workspace(self):
        """打开工作目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择工作目录", str(Path.home())
        )
        if dir_path:
            self.workspace = dir_path
            self.status_bar.showMessage(f"工作目录: {dir_path}")

    def save_conversation(self):
        """保存会话"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存会话", f"conversation_{datetime.now():%Y%m%d_%H%M%S}.json",
            "JSON Files (*.json)"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({
                    "config": self.config,
                    "history": self.conversation_history,
                    "timestamp": datetime.now().isoformat(),
                }, f, ensure_ascii=False, indent=2)
            self.status_bar.showMessage(f"会话已保存: {file_path}")

    def show_settings(self):
        """显示设置对话框"""
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.config = dialog.get_config()
            self.provider_label.setText(f"Provider: {self.config['provider_type']}")
            self.status_bar.showMessage("设置已更新")

    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self,
            "关于 Agent Harness",
            "<h3>Agent Harness GUI</h3>"
            "<p>基于 OpenClaw 的 Agent 运行界面</p>"
            "<p>版本: 1.0.0</p>"
            "<p>© 2026 OpenClaw Team</p>",
        )

    def clear_output(self):
        """清空输出"""
        self.output_text.clear()
        self.thinking_output.clear()
        self.tools_output.clear()

    def run_agent(self):
        """运行 Agent"""
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            self.status_bar.showMessage("请输入问题或指令")
            return

        if not self.config.get("api_key"):
            QMessageBox.warning(self, "警告", "请先在设置中配置 API Key")
            return

        # 更新 UI
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_bar.showMessage("Agent 运行中...")

        # 清空之前的结果
        self.thinking_output.clear()
        self.tools_output.clear()
        self.output_text.setHtml("<i>正在思考...</i>")

        # 添加到历史
        self.conversation_history.append({
            "role": "user",
            "content": prompt,
            "timestamp": datetime.now().isoformat(),
        })

        # 创建 Worker
        self.worker = AgentWorker(
            prompt=prompt,
            provider_config={
                "provider_type": self.config["provider_type"],
                "api_key": self.config["api_key"],
                "model": self.config.get("model", ""),
                "base_url": self.config.get("base_url"),
                "model_kwargs": {
                    "temperature": self.config["temperature"],
                },
            },
            workspace=getattr(self, "workspace", str(Path.cwd())),
            max_turns=self.config["max_turns"],
        )

        # 连接信号
        self.worker.started.connect(self._on_started)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.token_update.connect(self._on_token_update)
        self.worker.tool_called.connect(self._on_tool_call)
        self.worker.tool_result.connect(self._on_tool_result)
        self.worker.thinking.connect(self._on_thinking)

        # 启动
        self.worker.start()

    def stop_agent(self):
        """停止 Agent"""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
            self.status_bar.showMessage("Agent 已停止")
            self.run_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    @pyqtSlot()
    def _on_started(self):
        """Agent 开始运行"""
        self.status_bar.showMessage("Agent 运行中...")

    @pyqtSlot(str)
    def _on_finished(self, result_json):
        """Agent 完成"""
        import json
        try:
            result_obj = json.loads(result_json)
            content = result_obj.get("content", "")
            status = result_obj.get("status", "")
        except (json.JSONDecodeError, TypeError):
            content = result_json
            status = ""
        
        self.output_text.setHtml(f"""
            <div style='background: rgba(56, 239, 125, 0.1); border: 1px solid rgba(56, 239, 125, 0.2); 
                        border-radius: 12px; padding: 16px; margin: 8px 0;'>
                <span style='color: #38ef7d; font-weight: 600; font-size: 14px;'>✅ 完成</span>
                <span style='color: #888; font-size: 12px; margin-left: 12px;'>{status}</span>
                <hr style='border-color: rgba(56, 239, 125, 0.2); margin: 12px 0;'>
                <pre style='color: #e0e0e0; font-size: 13px; line-height: 1.6;'>{content}</pre>
            </div>
        """)
        self.conversation_history.append({
            "role": "assistant",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        self.status_bar.showMessage(f"✅ Agent 完成: {status}")
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    @pyqtSlot(str)
    def _on_error(self, error):
        """Agent 错误"""
        self.output_text.setHtml(f"""
            <div style='background: rgba(245, 58, 67, 0.15); border: 1px solid rgba(245, 58, 67, 0.3); 
                        border-radius: 12px; padding: 16px; margin: 8px 0;'>
                <span style='color: #ff6b6b; font-weight: 600; font-size: 16px;'>❌ 错误</span>
                <hr style='border-color: rgba(245, 58, 67, 0.3); margin: 12px 0;'>
                <pre style='color: #f5a5a5; font-size: 13px;'>{error}</pre>
            </div>
        """)
        self.status_bar.showMessage(f"❌ 错误: {error[:50]}...")
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    @pyqtSlot(int, int, float)
    def _on_token_update(self, prompt_tokens, completion_tokens, cost):
        """Token 更新"""
        self.tokens_label.setText(f"Tokens: {prompt_tokens} / {completion_tokens}")
        self.cost_label.setText(f"Cost: ${cost:.4f}")

    @pyqtSlot(str, str)
    def _on_tool_call(self, tool_name, arguments):
        """工具调用"""
        self.tools_output.append(f"""
            <div style='background: rgba(102, 126, 234, 0.15); padding: 8px 12px; border-radius: 8px; margin: 4px 0;'>
                <span style='color: #a8b4fc; font-weight: 600;'>🔧 {tool_name}</span>
            </div>
            <pre style='margin: 8px 0 0 16px; color: #9cdcfe; font-size: 12px;'>{arguments}</pre>
        """)

    @pyqtSlot(str, str)
    def _on_tool_result(self, tool_name, result):
        """工具结果"""
        result_preview = result[:300] + "..." if len(result) > 300 else result
        self.tools_output.append(f"""
            <div style='background: rgba(56, 239, 125, 0.1); padding: 6px 12px; border-radius: 8px; margin: 4px 0 8px 16px;'>
                <span style='color: #38ef7d;'>✓ {result_preview}</span>
            </div>
        """)

    @pyqtSlot(str)
    def _on_thinking(self, content):
        """思考过程"""
        self.thinking_output.append(f"""
            <div style='color: #c792ea; padding: 4px 0; border-left: 2px solid #9c6ef3; padding-left: 10px; margin: 4px 0;'>
                <span style='font-size: 12px;'>💭</span> {content}
            </div>
        """)
        # 滚动到底部
        cursor = self.thinking_output.textCursor()
        cursor.movePosition(cursor.End)
        self.thinking_output.setTextCursor(cursor)


# ============================================================================
# 入口
# ============================================================================


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Agent Harness")
    app.setOrganizationName("OpenClaw")

    window = AgentHarnessGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
