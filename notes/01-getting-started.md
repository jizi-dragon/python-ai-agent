# AI Agent 入门

## 什么是 AI Agent？

AI Agent（智能体）是一个能够感知环境、做出决策并执行行动的自主系统。
基于大语言模型（LLM）的 Agent 通常具备以下能力：

- **感知**：理解用户输入和上下文
- **推理**：分析问题并制定计划
- **行动**：调用工具、执行代码、查询数据
- **记忆**：维护对话历史和状态

## 核心组件

| 组件 | 说明 |
|------|------|
| LLM | 大语言模型，Agent 的"大脑" |
| Tools | 工具集，扩展 Agent 的能力边界 |
| Memory | 记忆系统，存储上下文和历史 |
| Planner | 规划器，分解任务并制定执行计划 |

## 学习进度

| 章节 | 内容 | 状态 |
|------|------|------|
| Chapter 1 | 极简 Agent 原型 → LLM 驱动 Agent | ✅ 完成 |
| Chapter 2 | 工具调用框架（参数验证/重试/熔断/错误处理） | ✅ 完成 |

### Chapter 1 学习路线

```
阶段一：手写规则原型 (agent_demo1.py)
  ├── 用纯 Python 搭建 Agent 骨架
  ├── 理解 Memory / LLM / Planner / Executor / Tools 五组件协作
  └── 发现规则系统的天花板

阶段二：接入真实 LLM (agent.py)
  ├── 连通 DeepSeek API (agent_demo.py)
  ├── 封装 AgentBrain：标准 OpenAI SDK 调用 (brain.py)
  ├── 构建 AgentTools：搜索/计划/时间/计算 (tools.py)
  └── 完整 Agent：LLM 思考 → 选择工具 → 调用工具 → 整合回复
```

### Chapter 2 学习路线

```
工具调用框架 (src/chapter_02/)
  ├── parameter_validator.py  → JSON Schema 风格参数校验
  ├── error_handler.py        → 统一异常分类与中文友好提示
  ├── retry.py                → 指数退避 + 随机抖动重试
  ├── circuit_breaker.py      → 三态熔断器（闭→开→半开）
  ├── tool_definitions.py     → 工具 Schema 定义 + 真实 API 实现
  ├── tool_executor.py        → 核心执行器：验证→熔断→重试→错误处理
  └── main.py                 → 完整演示入口
```

## 后续学习路线

1. ~~LLM 基础调用（API、本地模型）~~ ✅
2. ~~Function Calling / Tool Use~~ ✅
3. ReAct 模式（Reasoning + Acting）
4. Multi-Agent 协作
5. RAG（检索增强生成）
