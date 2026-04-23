# 《从 0 开始构建 Agent Harness》

> 像写操作系统一样，实现 OpenClaw 的底层 Harness

---

## 📚 课程目录

### 开篇词
- [开篇词 | 框架正在坍塌：像写操作系统一样，实现 OpenClaw 的底层 Harness](./00_开篇词.md)

---

### 第一章：认知与核心引擎

| 序号 | 标题 | 核心内容 |
|---|---|---|
| 01 | [架构演进：从 Framework 到 Harness](./chapter01/01_架构演进.md) | Framework 的困境，Harness 设计哲学，OpenClaw 架构总览 |
| 02 | [核心心脏：手写 Agent 的 Main Loop](./chapter01/02_核心心脏.md) | ReAct 循环实现，终止条件设计，状态机模型 |
| 03 | [慢思考与自省：剥离独立 Thinking 阶段](./chapter01/03_慢思考与自省.md) | 两阶段调用，Claude Extended Thinking，自适应慢思考 |
| 04 | [大脑接入：抽象 Provider 接口](./chapter01/04_大脑接入.md) | Provider 抽象层，Claude/OpenAI 适配，Provider 工厂模式 |

---

### 第二章：极简工具与物理交互

| 序号 | 标题 | 核心内容 |
|---|---|---|
| 05 | [动作延伸：构建 Tool Registry 与分发机制](./chapter02/05_动作延伸.md) | 装饰器注册，Schema 自动推断，工具分组与插件化 |
| 06 | [大道至简：最简工具集法则与 YOLO 哲学](./chapter02/06_大道至简.md) | 5 个核心工具，YOLO 执行哲学，工具设计七原则 |
| 07 | [容错艺术：支持多级模糊匹配的 Edit 工具](./chapter02/07_容错艺术.md) | 精确/空白标准化/模糊匹配，边界案例处理 |
| 08 | [并发提效：并行调用多个独立工具](./chapter02/08_并发提效.md) | asyncio.gather 并发，Semaphore 限流，超时控制 |
| 09 | [飞书集成：接入飞书机器人的事件流](./chapter02/09_飞书集成.md) | Webhook 接收，消息回复，卡片消息，异步处理 |

---

### 第三章：上下文工程体系

| 序号 | 标题 | 核心内容 |
|---|---|---|
| 10 | [提示词组装：动态加载 AGENTS.md 与外挂 Skills](./chapter03/10_提示词组装.md) | PromptBuilder，AGENTS.md，Skills 插件化 |
| 11 | [会话管理：Session 物理隔离与 Working Memory](./chapter03/11_会话管理.md) | Session 目录结构，JSONL 持久化，SessionManager |
| 12 | [突破内存：基于阶梯降级的 Context Compaction](./chapter03/12_突破内存.md) | 轻/中/重三级压缩，LLM 摘要压缩，Token 估算 |
| 13 | [记忆沉淀：持久化记忆与待办管理](./chapter03/13_记忆沉淀.md) | MEMORY.md 结构，MemoryManager，TodoManager |
| 14 | [错误自愈：上下文感知的 Error Recovery](./chapter03/14_错误自愈.md) | 错误分类，恢复提示模板，ErrorRecoverySystem |

---

### 第四章：稳定性控制与多智能体

| 序号 | 标题 | 核心内容 |
|---|---|---|
| 15 | [行为干预：防止 Agent 陷入"死循环"的 System Reminders](./chapter04/15_行为干预.md) | 里程碑提醒，连续错误检测，重复调用预警 |
| 16 | [防御纵深：Middleware 拦截与飞书人工审批](./chapter04/16_防御纵深.md) | 危险命令检测，MiddlewareChain，飞书审批卡片 |
| 17 | [任务委派：Subagent 隔离复杂探索任务](./chapter04/17_任务委派.md) | Subagent 模式，上下文隔离，并发 Subagent |

---

### 第五章：可观测性与科学度量

| 序号 | 标题 | 核心内容 |
|---|---|---|
| 18 | [成本与状态追踪：Token 消耗与执行耗时](./chapter05/18_成本追踪.md) | 模型价格表，CostTracker，Provider 装饰器拦截 |
| 19 | [洞察黑盒：Tracing 机制复盘失败决策路径](./chapter05/19_洞察黑盒.md) | TurnTrace，AgentTrace，Tracer，失败点定位 |
| 20 | [科学度量：Benchmark 自动化评估脚本](./chapter05/20_科学度量.md) | BenchmarkTask，BenchmarkRunner，CI 集成 |

---

### 第六章：端到端实战串讲

| 序号 | 标题 | 核心内容 |
|---|---|---|
| 21 | [实战（一）：完整 CLI 引擎与文件探索 Bug 修复](./chapter06/21_实战一.md) | 完整工程结构，模块拼装，实战演示 |
| 22 | [实战（二）：飞书 AgentOps 小助手](./chapter06/22_实战二.md) | 日志分析工具，运维操作，飞书审批全流程 |

---

### 结束语
- [结束语 | Agent 的尽头是 OS，大模型时代开发者的驾驭新征程](./99_结束语.md)

---

## 🗂️ 工程目录结构

```
openclaw/                        # 参考实现根目录
├── harness/
│   ├── main_loop.py             # 第 02 节：Main Loop
│   ├── provider/                # 第 04 节：Provider 抽象
│   │   ├── base.py
│   │   ├── claude.py
│   │   └── openai_compat.py
│   ├── tools/                   # 第 05-08 节：工具系统
│   │   ├── registry.py
│   │   ├── executor.py
│   │   ├── edit.py
│   │   └── plugins/
│   ├── prompt/                  # 第 10 节：Prompt 构建
│   ├── session/                 # 第 11 节：Session 管理
│   ├── context/                 # 第 12 节：Context 压缩
│   ├── memory/                  # 第 13 节：记忆管理
│   ├── stability/               # 第 15 节：System Reminders
│   ├── middleware/              # 第 16 节：中间件
│   └── observability/           # 第 18-19 节：可观测性
├── integrations/
│   └── feishu/                  # 第 09/16 节：飞书集成
├── benchmark/                   # 第 20 节：Benchmark
├── main.py                      # 第 21 节：CLI 入口
├── AGENTS.md                    # Agent 行为规范
└── config.yaml                  # 配置文件
```

---

## ⚙️ 快速开始

### 环境准备

```bash
# 安装依赖
pip install anthropic openai httpx fastapi uvicorn pyyaml

# 配置 API Key
export ANTHROPIC_API_KEY=sk-ant-...
# 或者
export OPENAI_API_KEY=sk-...
```

### 配置文件

```yaml
# config.yaml
default_provider: claude

providers:
  claude:
    type: claude
    api_key: "${ANTHROPIC_API_KEY}"
    model: claude-opus-4-5
```

### 运行 CLI 模式

```bash
# 单次任务
python main.py "帮我分析当前目录的项目结构"

# 交互模式
python main.py

# 指定工作目录
python main.py -w /path/to/project "找出所有 TODO 注释"
```

### 运行飞书 Bot

```bash
export FEISHU_APP_ID=cli_xxx
export FEISHU_APP_SECRET=xxx
uvicorn integrations.feishu.webhook:app --port 8080
```

---

## 📖 核心概念速查

| 概念 | 定义 | 对应章节 |
|---|---|---|
| **Harness** | 最小化、可观测、可组合的 Agent 运行时 | 第一章 |
| **Main Loop** | 驱动 Think → Act → Observe 循环的引擎 | 02 |
| **Provider** | 抽象 LLM 接口的适配层 | 04 |
| **Tool Registry** | 工具的注册、查询、分发系统 | 05 |
| **YOLO 哲学** | 信任 LLM，减少不必要保护层 | 06 |
| **Context Compaction** | 上下文窗口压缩策略 | 12 |
| **System Reminders** | 关键时刻自动注入的行为干预提示 | 15 |
| **Middleware** | 工具调用前的拦截与处理层 | 16 |
| **Subagent** | 具有独立上下文的子 Agent 实例 | 17 |
| **Tracer** | 记录完整决策路径的可观测工具 | 19 |

---

## 📄 许可证

MIT License - 欢迎 Fork、修改、用于商业项目。

---

*课程作者：OpenClaw Team*  
*最后更新：2026-04-22*
