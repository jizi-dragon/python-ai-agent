# Agent 解剖：从一个极简原型理解 AI Agent 架构

> 源码：[src/chapter_01/agent.py](../src/chapter_01/agent.py)

---

## 一、架构全景

```
┌─────────────────────────────────────────────────────┐
│                    SimpleAgent                       │
│                                                      │
│  handle(user_prompt)                                  │
│       │                                               │
│       ▼                                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐       │
│  │ LLM 解析  │ → │ Planner  │ → │ Executor │       │
│  │  (意图)   │    │ (拆步骤)  │    │ (逐步执行) │       │
│  └──────────┘    └──────────┘    └─────┬────┘       │
│                                        │             │
│                          ┌─────────────┼──────┐      │
│                          ▼             ▼      ▼      │
│                      Memory      ToolRegistry  LLM   │
│                      (记忆)       (工具集)   (大脑)   │
└─────────────────────────────────────────────────────┘
```

**核心流程**：用户输入 → LLM 解析意图 → Planner 拆解为步骤列表 → Executor 逐步执行（过程中读写 Memory、调用 Tool、必要时再问 LLM）→ 汇总返回。

---

## 二、组件逐个分析

### 2.1 Memory — 双层记忆

```python
class Memory:
    short: Dict  # 会话上下文（一次对话内传递）
    long:  Dict  # 持久化偏好（跨对话保留）
```

| 层级 | 用途 | 示例 |
|------|------|------|
| `short` | 步骤间传递中间结果 | 查到的天气数据 → 下一步判断用 |
| `long` | 用户偏好、联系人等静态数据 | "小王" → "13911112222" |

**设计要点**：步骤之间通过 `memory.short` 解耦 —— `query_weather` 写入结果，`decide_and_notify` 读取结果，两者无需直接传参。

### 2.2 LLMInterface — 可替换的大脑

```python
class LLMInterface:
    def generate(self, prompt: str) -> str:
        # 当前：硬编码规则匹配
        # 未来：替换为 openai.ChatCompletion.create(...)
```

这是一个 **策略模式** 的应用。整个 Agent 不依赖具体 LLM 实现，只需替换 `generate()` 方法即可切换模型。

> ⚠️ **当前缺陷**：规则匹配能力极弱。实际运行中，动态生成的 prompt `"基于天气信息：...，生成一条发给小王的提醒"` 无法命中任何关键词，返回了默认的 `"我理解了。"`——这正是规则系统的天花板，也是我们必须接入真正 LLM 的原因。

### 2.3 ToolRegistry — 工具注册中心

```python
registry = ToolRegistry()
registry.register("weather", mock_weather_api)     # 注册
registry.call("weather", "北京", "明天")            # 调用
```

**模式**：服务定位器（Service Locator）。通过字符串名查找工具函数，实现了：
- 工具的热插拔（随时 register/unregister）
- 统一的调用接口
- Agent 不感知工具的具体实现

### 2.4 SimplePlanner — 任务规划器

```python
def plan(self, goal: str) -> List[Dict]:
    if "天气" in goal:
        return [
            {"action": "query_weather", ...},
            {"action": "decide_and_notify", ...},
        ]
```

当前是硬编码的 if-else，实际 Agent（如 ReAct、Plan-and-Execute）中，这部分应由 LLM 动态生成。但即便硬编码，它清晰地展示了规划的**输出格式**：一个步骤列表，每步包含 `action` 和 `params`。

### 2.5 Executor — 步骤执行器

这是本次优化的重点。原版用 if-elif 链分发：

```python
# ❌ 原版：线性 if-elif，每加一个 action 都要改 run_step
if action == "query_weather": ...
elif action == "decide_and_notify": ...
elif action == "search": ...
```

优化后改为**字典分发**：

```python
# ✅ 优化版：handler 字典，新增 action 只需加一个 key
self._handlers = {
    "query_weather": self._handle_query_weather,
    "decide_and_notify": self._handle_decide_and_notify,
    "search": self._handle_search,
}

def run_step(self, step):
    handler = self._handlers.get(step["action"])
    if handler is None:
        raise ValueError(f"未知动作: {step['action']}")
    return handler(step.get("params", {}))
```

优势：扩展性好、可读性强、新增 action 不影响已有逻辑。

---

## 三、实际运行结果分析

```
输入: "查一下明天北京的天气，如果下雨，帮我写个提醒并发给小王。"

输出:
{
  "intent": "请先查询天气；如果有雨，请生成提醒并发送给目标联系人。",
  "steps": [
    {
      "step": {"action": "query_weather", "params": {"city": "北京", "date": "明天"}},
      "result": {"city": "北京", "date": "明天", "cond": "雨", "precip_mm": 5}
    },
    {
      "step": {"action": "decide_and_notify", ...},
      "result": {"notified": true, "message": "我理解了。"}  ← 这里暴露了问题
    }
  ]
}
```

**关键发现**：

1. ✅ 步骤 1（查天气）正常工作，`short memory` 正确传递了数据
2. ❌ 步骤 2 的消息内容为 `"我理解了。"` 而非预期提醒——因为 `LLMInterface` 的规则匹配未能覆盖动态 prompt
3. ✅ 通知确实发送了（`notified: true`），说明执行流程完整

---

## 四、优化点总结

| 位置 | 原版 | 优化版 | 原因 |
|------|------|--------|------|
| Executor 分发 | if-elif 链 | handler 字典 | 可扩展性、可读性 |
| 属性可见性 | `self.tools` 公开 | `self._tools` 私有 | 封装原则 |
| 类型标注 | 缺失 | 完整标注 | IDE 支持、代码即文档 |
| 模块文档 | 无 | 架构图 + 流程说明 | 可维护性 |

---

## 五、下一步可以做的

1. **接入真实 LLM**：用 OpenAI API 替换 `LLMInterface.generate()`
2. **LLM 驱动的 Planner**：让 LLM 根据工具描述动态生成步骤，而非硬编码 if-else
3. **ReAct 循环**：让 Agent 在「思考→行动→观察」循环中自主决策
4. **工具描述协议**：为每个工具提供 JSON Schema 描述，供 LLM 理解何时调用
5. **错误恢复**：步骤失败时的重试/降级策略

---

## 六、核心 Takeaways

- **Agent = LLM + Planner + Executor + Memory + Tools**，五个组件各司其职
- **Memory 是步骤间的粘合剂**，让前后步骤在不直接传参的情况下共享数据
- **ToolRegistry 实现了工具的热插拔**，Agent 不关心工具怎么实现，只关心工具叫什么名字
- **Executor 用字典分发替代 if-elif**，是简单但有效的工程优化
- **规则系统的天花板很低**——这正是为什么我们需要真正的 LLM
