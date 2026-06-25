# Chapter 1：从规则原型到 LLM 驱动 Agent

> 源码目录：[src/chapter_01/](../src/chapter_01/)

---

## 整体演进路线

```
阶段一                           阶段二
agent_demo1.py                  agent.py
┌─────────────────┐            ┌─────────────────────────┐
│  LLMInterface    │ ──替换──→  │  AgentBrain (DeepSeek)  │
│  (硬编码规则)     │            │  (真实 LLM 调用)        │
├─────────────────┤            ├─────────────────────────┤
│  ToolRegistry    │ ──重构──→  │  AgentTools             │
│  (注册中心模式)   │            │  (静态工具类)            │
├─────────────────┤            ├─────────────────────────┤
│  SimplePlanner   │ ──融合──→  │  Prompt Engineering     │
│  (硬编码 if-else) │            │  (LLM 动态规划)         │
├─────────────────┤            ├─────────────────────────┤
│  Memory (双层)   │            │  (待后续章节加入)        │
└─────────────────┘            └─────────────────────────┘
```

---

## 阶段一：手写规则原型 (agent_demo1.py)

### 设计目标

在接入真实 LLM 之前，先用纯 Python 搭一个能跑的 Agent 骨架，理解五个核心组件是如何协作的。

### 架构图

```
用户输入
    │
    ▼
┌──────────┐    ┌──────────┐    ┌──────────┐
│ LLM 解析  │ → │ Planner  │ → │ Executor │
│  (意图)   │    │ (拆步骤)  │    │ (逐步执行) │
└──────────┘    └──────────┘    └─────┬────┘
                                       │
                         ┌─────────────┼──────┐
                         ▼             ▼      ▼
                     Memory      ToolRegistry  LLM
```

### 五个组件

| 组件 | 类 | 职责 |
|------|-----|------|
| **Memory** | `Memory` | `short` 存会话上下文，`long` 存持久化偏好 |
| **大脑** | `LLMInterface` | `generate(prompt)` → 规则匹配返回结果（替换点） |
| **工具** | `ToolRegistry` | 注册中心：`register(name, fn)` / `call(name, *args)` |
| **规划** | `SimplePlanner` | `plan(goal)` → 硬编码的步骤列表 |
| **执行** | `Executor` | `run_step(step)` → handler 字典分发 |

### 关键发现

```python
# 运行结果暴露的问题：
# 动态 prompt "基于天气信息：{...}，生成一条发给小王的提醒。"
# → 无法命中 LLMInterface 的任何 if 分支
# → 返回默认值 "我理解了。"  ← 规则系统的天花板
```

> 这个"失败"恰好证明了为什么必须接入真正的 LLM。

---

## 阶段二：接入 DeepSeek LLM (agent.py)

### 设计目标

将阶段一的每个硬编码部分，逐步替换为 LLM 驱动：

- `LLMInterface.generate()` → 真正调用 DeepSeek API
- `SimplePlanner.plan()` → 通过 Prompt Engineering 让 LLM 自行决定用什么工具
- `ToolRegistry` → 重构为静态方法类 `AgentTools`

### 文件拆解

#### 1. 连通性测试 (agent_demo.py)

```python
# 最小可行验证：用 OpenAI SDK 连 DeepSeek
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)
response = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[{"role": "user", "content": "你好"}],
)
```

**关键点**：DeepSeek 兼容 OpenAI SDK，只需改 `base_url` 和 `model` 即可切换，无需引入额外 SDK。

#### 2. 大脑封装 (brain.py)

```python
class AgentBrain:
    def __init__(self, model="deepseek-v4-flash"):
        self.model = model

    def think(self, prompt: str) -> str:
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,   # 低温度 = 更专注、更可预测
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
```

**设计要点**：
- `temperature=0.5`：工具调用场景需要确定性，不宜过高
- 异常兜底：`try/except` 返回错误信息而非崩溃
- 单一职责：只负责"思考"，不关心工具调用、不关心规划

#### 3. 工具箱 (tools.py)

```python
class AgentTools:
    @staticmethod
    def search_web(query):      # 模拟搜索（字典匹配）
    @staticmethod
    def make_schedule(steps):   # 排版日程
    @staticmethod
    def get_current_time():     # 系统时间
    @staticmethod
    def calculate(expression):  # 安全计算器
```

**安全设计（calculate）**：
- 字符白名单过滤：只允许 `0-9 + - * / ( ) .`
- 限制内置函数：`__builtins__` 设为空
- 显式错误处理：除零 / 语法错误 / 非法输入分别提示

#### 4. Agent 主控 (agent.py)

```python
class SimpleAgent:
    def __init__(self):
        self.brain = AgentBrain()
        self.tools = AgentTools
        self.tool_descriptions = """你可以使用以下工具：
            1. 搜索工具：...
            2. 计划工具：...
            3. 时间工具：...
            4. 计算工具：...
        """

    def run(self, user_task):
        # 第一步：Prompt Engineering — 让 LLM 输出结构化格式
        prompt = f"""
        用户的任务是：{user_task}
        {self.tool_descriptions}
        请严格按以下格式回答：
        思考：[分析任务需要什么]
        工具：[选择工具名称，无则写'无']
        指令：[发送给工具的指令]
        """

        response = self.brain.think(prompt)
        # 第二步：解析 LLM 的结构化输出
        tool_name, instruction = self._parse(response)
        # 第三步：调用工具
        result = self._use_tool(tool_name, instruction)
        # 第四步：让 LLM 整合结果，生成最终回复
        final = self.brain.think(f"工具结果：{result}，请生成自然回复")
        return final
```

### 完整流程图

```
┌──────────────────────────────────────────────────────────┐
│                      SimpleAgent.run()                    │
│                                                           │
│  ① Prompt Engineering                                     │
│     tool_descriptions + user_task                         │
│     ↓                                                     │
│  ② AgentBrain.think(prompt)  ──── DeepSeek API ────┐     │
│     ↓                                               │     │
│  ③ 解析结构化输出                                     │     │
│     "思考：需要查天气"                                │     │
│     "工具：搜索工具"   ──→  _parse() ──→ (name, cmd) │     │
│     "指令：北京明天天气"                              │     │
│     ↓                                               │     │
│  ④ _use_tool(name, cmd)                             │     │
│     ├── "搜索工具" → AgentTools.search_web(cmd)      │     │
│     ├── "时间工具" → AgentTools.get_current_time()   │     │
│     ├── "计算工具" → AgentTools.calculate(cmd)       │     │
│     └── "计划工具" → AgentTools.make_schedule(cmd)   │     │
│     ↓                                               │     │
│  ⑤ AgentBrain.think(整合 prompt + 结果) ── DeepSeek ┘     │
│     ↓                                                     │
│  ⑥ 最终自然语言回复                                        │
└──────────────────────────────────────────────────────────┘
```

---

## 两阶段对比

| 维度 | 阶段一（规则） | 阶段二（LLM 驱动） |
|------|--------------|-------------------|
| 大脑 | `LLMInterface` 硬编码 if-else | `AgentBrain` 调用 DeepSeek API |
| 规划 | `SimplePlanner` 硬编码步骤列表 | Prompt Engineering 让 LLM 自己决定 |
| 工具 | `ToolRegistry` 注册中心 | `AgentTools` 静态方法类 |
| 灵活性 | 只能处理预设关键词 | 可处理任意自然语言任务 |
| 可靠性 | 100% 确定，但天花板极低 | 依赖 LLM 输出格式，需做鲁棒解析 |
| 适用场景 | 教学理解架构 | 实际可用 |

---

## Prompt Engineering 要点

阶段二最关键的技巧是如何让 LLM 稳定输出结构化内容：

```python
# ✅ 好：明确指定格式，限制输出结构
"""
请严格按照以下固定格式回答，不要添加额外内容：
思考：[简要分析任务需要什么]
工具：[选择要使用的工具名称，如果没有合适的就写'无']
指令：[发送给该工具的具体指令内容]
"""

# 解析时需要做鲁棒处理：
# 1. 去除空行
# 2. 兼容中英文冒号
# 3. 工具名匹配时 strip 空格、兼容大小写
```

---

## 核心 Takeaways

1. **先搭骨架再换大脑**：用硬编码验证架构可行性，再接入 LLM 赋予灵性
2. **DeepSeek 兼容 OpenAI SDK**：只需改 `base_url`，零成本迁移
3. **Prompt Engineering 是核心技能**：结构化的输出格式 = Agent 能稳定解析的"协议"
4. **工具安全不容忽视**：`eval` 必须配合白名单和限制环境
5. **temperature=0.5**：工具调用场景需要确定性，不宜过高
