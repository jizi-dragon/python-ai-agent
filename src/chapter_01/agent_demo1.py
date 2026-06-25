"""
agent.py — 极简 AI Agent 原型（可直接运行）

核心流程：
  用户输入 → LLM 解析意图 → Planner 拆解步骤 → Executor 逐步执行 → 汇总返回

包含组件：
  Memory        — 短期/长期记忆
  LLMInterface  — LLM 抽象层（替换点）
  ToolRegistry  — 工具注册与调用
  SimplePlanner — 任务规划器
  Executor      — 步骤执行器
  SimpleAgent   — Agent 本体，组装所有组件
"""

from typing import Any, Dict, List, Callable
import json


# ============================================================
# Memory
# ============================================================
class Memory:
    """极简双层记忆：short 存会话上下文，long 存持久化偏好"""

    def __init__(self):
        self.short: Dict[str, Any] = {}
        self.long: Dict[str, Any] = {}

    def get_short(self, k: str, default: Any = None) -> Any:
        return self.short.get(k, default)

    def set_short(self, k: str, v: Any) -> None:
        self.short[k] = v

    def get_long(self, k: str, default: Any = None) -> Any:
        return self.long.get(k, default)

    def set_long(self, k: str, v: Any) -> None:
        self.long[k] = v


# ============================================================
# LLM 抽象层（替换点）
# ============================================================
class LLMInterface:
    """
    规则式模拟回答器。
    真实使用时替换 generate() 为 OpenAI / 本地模型调用。
    """

    def generate(self, prompt: str) -> str:
        if "是否下雨" in prompt or "下雨" in prompt:
            return "请先查询天气；如果有雨，请生成提醒并发送给目标联系人。"
        if "生成提醒" in prompt:
            return "请提醒小王：明天北京有雨，请带伞。"
        return "我理解了。"


# ============================================================
# 工具注册 & 模拟工具
# ============================================================
class ToolRegistry:
    """工具注册中心：注册 → 查找 → 调用"""

    def __init__(self):
        self._tools: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        self._tools[name] = fn

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        if name not in self._tools:
            raise ValueError(f"工具未注册: {name}")
        return self._tools[name](*args, **kwargs)


def mock_weather_api(city: str, date: str) -> Dict[str, Any]:
    if "北京" in city and "明天" in date:
        return {"city": city, "date": date, "cond": "雨", "precip_mm": 5}
    return {"city": city, "date": date, "cond": "晴", "precip_mm": 0}


def mock_send_message(contact: str, message: str) -> bool:
    print(f"[发送消息] to={contact} message={message}")
    return True


def mock_search(query: str) -> str:
    return f"模拟搜索结果：关于 `{query}` 的信息摘要。"


# ============================================================
# Planner
# ============================================================
class SimplePlanner:
    """将用户目标拆解为步骤列表。当前为硬编码演示，真实场景应由 LLM 动态生成。"""

    def plan(self, goal: str) -> List[Dict[str, Any]]:
        if "天气" in goal or "下雨" in goal:
            return [
                {"action": "query_weather", "params": {"city": "北京", "date": "明天"}},
                {"action": "decide_and_notify", "params": {"contact_name": "小王"}},
            ]
        return [{"action": "search", "params": {"query": goal}}]


# ============================================================
# Executor
# ============================================================
class Executor:
    """步骤执行器：根据 action 名字分发到对应处理逻辑"""

    def __init__(self, tools: ToolRegistry, memory: Memory, llm: LLMInterface):
        self.tools = tools
        self.memory = memory
        self.llm = llm
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {
            "query_weather": self._handle_query_weather,
            "decide_and_notify": self._handle_decide_and_notify,
            "search": self._handle_search,
        }

    def run_step(self, step: Dict[str, Any]) -> Any:
        action = step["action"]
        handler = self._handlers.get(action)
        if handler is None:
            raise ValueError(f"未知动作: {action}")
        return handler(step.get("params", {}))

    def _handle_query_weather(self, params: Dict[str, Any]) -> Dict[str, Any]:
        result = self.tools.call("weather", params["city"], params["date"])
        self.memory.set_short("last_weather", result)
        return result

    def _handle_decide_and_notify(self, params: Dict[str, Any]) -> Dict[str, Any]:
        weather = self.memory.get_short("last_weather", {})
        if weather.get("cond") != "雨":
            return {"notified": False, "reason": "天气晴朗"}
        prompt = (
            f"基于天气信息：{weather}，生成一条发给{params['contact_name']}的提醒。"
        )
        reminder = self.llm.generate(prompt)
        contact = self.memory.get_long(params["contact_name"], "13800000000")
        ok = self.tools.call("send_message", contact, reminder)
        return {"notified": ok, "message": reminder}

    def _handle_search(self, params: Dict[str, Any]) -> str:
        return self.tools.call("search", params["query"])


# ============================================================
# Agent 本体
# ============================================================
class SimpleAgent:
    """组装所有组件，对外暴露 handle()"""

    def __init__(self):
        self.memory = Memory()
        self.tools = ToolRegistry()
        self.llm = LLMInterface()
        self.planner = SimplePlanner()
        self.executor = Executor(self.tools, self.memory, self.llm)

        self.tools.register("weather", mock_weather_api)
        self.tools.register("send_message", mock_send_message)
        self.tools.register("search", mock_search)

        self.memory.set_long("小王", "13911112222")

    def handle(self, user_prompt: str) -> Dict[str, Any]:
        intent = self.llm.generate(user_prompt)
        steps = self.planner.plan(user_prompt)
        results = [
            {"step": step, "result": self.executor.run_step(step)}
            for step in steps
        ]
        return {"intent": intent, "steps": results}


# ============================================================
# 运行示例
# ============================================================
if __name__ == "__main__":
    agent = SimpleAgent()
    task = "查一下明天北京的天气，如果下雨，帮我写个提醒并发给小王。"
    out = agent.handle(task)
    print(json.dumps(out, ensure_ascii=False, indent=2))
