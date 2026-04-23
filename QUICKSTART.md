# 🚀 快速开始

## 环境要求

| 项目 | 要求 |
|------|------|
| **Python** | 3.10, 3.11, 3.12, 3.13 |
| **Conda** | Anaconda / Miniconda (可选，推荐使用) |
| **操作系统** | Windows / macOS / Linux |

---

## 一键创建环境 (推荐)

### Windows
```bash
# 双击运行或命令行执行
setup_env.bat
```

### Linux / macOS
```bash
# 添加执行权限后运行
chmod +x setup_env.sh
./setup_env.sh
```

### 手动创建 (不使用脚本)
```bash
# 创建 conda 环境
conda create -n agent-harness python=3.11 -y

# 激活环境
conda activate agent-harness

# 安装依赖
pip install -r requirements.txt
```

---

## 配置 API Key

### 方式 A: 环境变量

**Linux/macOS:**
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
export OPENAI_API_KEY="sk-your-key-here"
```

**Windows (PowerShell):**
```powershell
$env:ANTHROPIC_API_KEY="sk-ant-your-key-here"
$env:OPENAI_API_KEY="sk-your-key-here"
```

**Windows (CMD):**
```cmd
set ANTHROPIC_API_KEY=sk-ant-your-key-here
set OPENAI_API_KEY=sk-your-key-here
```

### 方式 B: 配置文件
```bash
cp config.yaml.example config.yaml
# 编辑 config.yaml，填入你的 API Key
```

---

## 启动应用

### CLI 模式 (命令行)
```bash
python main.py
```

### Web UI 模式 (浏览器访问)
```bash
python web.py
# 访问 http://localhost:8000
```

### GUI 模式 (桌面应用)
```bash
python gui.py
```

---

## 依赖说明

| 依赖包 | 说明 | 必选 |
|--------|------|------|
| `anthropic` | Claude API 客户端 | ⭐ 核心 |
| `openai` | OpenAI API 客户端 | ⭐ 核心 |
| `httpx` | HTTP 请求库 | ⭐ 核心 |
| `pyyaml` | 配置文件解析 | ⭐ 核心 |
| `fastapi` | Web 服务框架 | 🌐 Web UI |
| `uvicorn` | ASGI 服务器 | 🌐 Web UI |
| `PyQt6` | 图形界面库 | 🖥️ GUI |
| `tiktoken` | Token 计数器 | 📊 可选 |
| `pydantic` | 数据验证 | 📊 可选 |

---

## 常见问题

### Q: conda 命令找不到？
**A:** 确保正确安装了 Anaconda 或 Miniconda，并重启终端使其生效。

### Q: pip 安装失败？
**A:** 尝试更新 pip: `python -m pip install --upgrade pip`

### Q: PyQt6 安装失败？
**A:** PyQt6 在某些系统可能需要额外依赖。Linux 可尝试: `sudo apt-get install python3-pyqt6`

### Q: Web UI 无法访问？
**A:** 检查防火墙设置，确保 8000 端口未被占用。

---

## 验证安装

```bash
# 检查 Python 版本
python --version

# 检查依赖
python -c "import anthropic, openai, yaml; print('依赖检查通过')"

# 验证 CLI 可用
python main.py --help
```
