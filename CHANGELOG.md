# Agent Harness 项目总结

> 本文档记录 2026-04-22 至 2026-04-23 期间对 Agent Harness 项目的迭代优化记录

---

## 📋 项目概述

**Agent Harness** 是一个支持多种 LLM Provider 的 Agent 调度框架，包含以下核心组件：

| 组件 | 技术栈 | 说明 |
|------|--------|------|
| **核心引擎** | Python | `harness/` 目录，包含 MainLoop、Provider、Tools 等 |
| **Web UI** | FastAPI + Vue3 | `web.py` + `web/index.html` |
| **GUI** | PyQt6 | `gui.py` |
| **CLI** | Python | `main.py` |

---

## 🛠️ 本次迭代完成的功能

### 1. Provider 参数兼容性修复

**问题**：`VolcenginePlanProvider.__init__()` 收到意外参数导致报错

**修复内容**：

| 文件 | 修复 |
|------|------|
| `factory.py` | 在传递给具体 Provider 前移除 `provider_type` 参数 |
| `gui.py` | 仅对 `deepseek/openai/openai_compat` 类型传递 `base_url` |
| `gui.py` | 添加 `model` 字段到 `provider_config` |

**关键代码**：
```python
# factory.py - 移除 provider_type
kwargs.pop("provider_type", None)

# gui.py - 条件传递 base_url
if provider_type in ("deepseek", "openai", "openai_compat") and base_url:
    create_kwargs["base_url"] = base_url
```

---

### 2. LoopResult 序列化修复

**问题**：`AgentWorker.finished.emit()` 传递了 `LoopResult` 对象而非字符串

**修复**：
```python
# 序列化后再 emit
self.finished.emit(json.dumps({
    "content": result.content,
    "status": str(result.status.value),
}, ensure_ascii=False))
```

---

### 3. Token 统计与费用计算

**问题**：`Usage` 对象属性名错误导致统计失败

**修复**：
- `response.usage.prompt_tokens` → `response.usage.input_tokens`
- `response.usage.completion_tokens` → `response.usage.output_tokens`
- 添加 `cost_tracker.record_usage()` 计算费用

---

### 4. Web UI 美化

**技术特性**：
- 全屏布局（100vw × 100vh）
- 紫蓝渐变背景 `#0f0c29 → #302b63 → #24243e`
- 玻璃态卡片效果 `backdrop-filter: blur(20px)`
- 发光渐变按钮
- 空状态浮动动画
- 实时统计栏（Tokens、Cost、Turns）

---

### 5. GUI 美化

**改进内容**：
| 方面 | 效果 |
|------|------|
| 背景 | 紫蓝渐变 |
| 按钮 | 圆角渐变色 |
| 卡片 | 玻璃态边框 |
| 错误提示 | 红色边框卡片 |
| 成功结果 | 绿色边框卡片 |
| 思考过程 | 紫色左侧边框 |

---

### 6. 工作空间管理功能

**后端 API**：
```
GET    /api/workspaces           # 列出所有工作空间
POST   /api/workspaces           # 创建新工作空间
PUT    /api/workspaces/{id}      # 更新工作空间
DELETE /api/workspaces/{id}      # 删除工作空间
```

**前端功能**：
- Header 右侧下拉选择器
- 创建/删除工作空间弹窗
- 会话绑定工作空间
- 持久化到 `workspaces.json`

---

### 7. 专家系统功能

**配置文件**：`experts.yaml`

| 专家 ID | 名称 | 图标 | 专长 |
|---------|------|------|------|
| `frontend` | 前端开发专家 | 🎨 | React/Vue、TypeScript、响应式设计 |
| `java` | Java全栈专家 | ☕ | Spring Boot/Cloud、微服务、大数据 |
| `qa` | 测试专家 | 🔍 | 自动化测试、性能测试、测试策略 |
| `devops` | DevOps专家 | 🚀 | CI/CD、K8s、IaC、云原生 |
| `architect` | 架构师 | 🏗️ | 架构设计、技术选型、技术债务治理 |

**后端 API**：
```
GET  /api/experts                      # 获取专家列表
GET  /api/experts/{id}/system-prompt   # 获取专家系统提示词
```

**前端 UI**：
- 输入框上方专家选择区
- 点击选择/取消专家
- 选中状态高亮显示
- 发送消息时自动注入专家提示词

---

## 🐛 修复的问题列表

| 问题 | 根因 | 解决方案 |
|------|------|----------|
| `VolcenginePlanProvider.__init__()` 不接受 `provider_type` | factory 传递了额外参数 | `kwargs.pop("provider_type")` |
| `VolcenginePlanProvider.__init__()` 不接受 `base_url` | 不是所有 Provider 都支持 | 按类型条件传递 |
| `provider_config` 缺少 `model` 字段 | 代码遗漏 | 添加 `model` 字段 |
| `LoopResult` 类型不可 emit | PyQt 信号类型限制 | 序列化为 JSON |
| `LoopStatus` 枚举不可 JSON 序列化 | 枚举类型问题 | 使用 `.value` 转字符串 |
| `Usage.prompt_tokens` 不存在 | 属性名错误 | 改为 `input_tokens` |
| 刷新后重复创建会话 | 逻辑错误 | 有会话则加载最新，无则创建 |
| 工作空间下拉被遮挡 | z-index 问题 | 调整层级和定位 |
| 专家列表不可见 | 位置在滚动区内 | 移到 chat-messages 外部 |

---

## 📁 修改的文件

```
10_agent_harness/
├── harness/
│   ├── main_loop.py          # Token 统计修复
│   └── provider/
│       └── factory.py         # provider_type 参数移除
├── web.py                     # 专家系统 API、Token 回调修复
├── web/
│   └── index.html             # 美化、工作空间、专家列表
├── gui.py                     # 美化、参数修复
├── experts.yaml               # 专家配置（新增）
└── workspaces.json           # 工作空间持久化（运行时生成）
```

---

## 🚀 快速开始

```bash
# 1. 进入项目目录
cd 10_agent_harness

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key（编辑 config.yaml）
provider_type: volcengine_plan
api_key: your-api-key-here
model: your-model-here

# 4. 启动 Web UI
python web.py
# 访问 http://localhost:8000

# 5. 或启动 GUI
python gui.py
```

---

## 📝 待优化项

1. **专家系统**：前端仍需测试验证显示效果
2. **多会话管理**：支持会话切换、分页、搜索
3. **工具可视化**：实时展示工具调用关系图
4. **历史记录导出**：支持导出为 Markdown/JSON

---

## 📅 更新记录

| 日期 | 版本 | 主要内容 |
|------|------|----------|
| 2026-04-22 | v1.0 | 初始框架完成 |
| 2026-04-22 | v1.1 | Provider 兼容性修复 |
| 2026-04-22 | v1.2 | Web/GUI 美化 |
| 2026-04-22 | v1.3 | 工作空间管理 |
| 2026-04-23 | v1.4 | 专家系统基础功能 |

---

*本文档由 Agent Harness 自动生成*
*最后更新：2026-04-23*
