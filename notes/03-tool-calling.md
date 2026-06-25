# Chapter 2：工具调用框架 — 从基础到生产级

> 源码目录：[src/chapter_02/](../src/chapter_02/)

---

## 学习目标

Chapter 1 中我们实现了 LLM 驱动 Agent：大脑思考 → 选择工具 → 调用工具 → 生成回复。
但该实现缺少生产环境中必备的能力——**参数校验**、**错误处理**、**重试机制**、**熔断保护**。

本章构建一个完整的工具调用框架，将这四个能力系统性地融入工具执行链路。

---

## 文件架构

```
src/chapter_02/
├── parameter_validator.py   ← 参数验证器
├── error_handler.py         ← 统一错误处理器
├── retry.py                 ← 指数退避重试
├── circuit_breaker.py       ← 熔断器
├── tool_definitions.py      ← 工具定义 + 真实 API 函数
├── tool_executor.py         ← 工具执行器主框架（串联所有模块）
└── main.py                  ← 演示入口
```

**依赖关系**：

```
main.py
  └── tool_executor.py
        ├── parameter_validator.py
        ├── error_handler.py
        ├── retry.py
        └── circuit_breaker.py
```

---

## 核心执行流程

```
用户输入: "北京今天天气怎么样？"
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  ToolExecutor.handle_user_request()                     │
│                                                         │
│  ① _ask_llm_for_tool(user_input)                       │
│     └── 调用 DeepSeek LLM，让 LLM 选择工具 + 提取参数  │
│     └── 返回: tool_name="get_weather", params={city:"北京"}│
│     ↓                                                   │
│  ② execute_tool(tool_name, params)                      │
│     ├── 2a. 参数验证 → ParameterValidator              │
│     ├── 2b. 熔断守卫 → CircuitBreaker                  │
│     ├── 2c. 重试执行 → ExponentialBackoffRetry         │
│     └── 2d. 错误处理 → ErrorHandler                    │
│     ↓                                                   │
│  ③ _generate_final_response(user_input, result)        │
│     └── 再次调用 LLM，将结构化结果转为自然语言回复     │
│     └── 返回: "北京今天晴天，32°C，体感温度30°C..."   │
└─────────────────────────────────────────────────────────┘
```

---

## 模块详解

### 1. 参数验证器 (parameter_validator.py)

**职责**：在工具执行前校验参数是否符合 JSON Schema 定义。

```python
class ParameterValidator:
    """基于 JSON Schema 风格的工具参数校验"""

    TYPE_MAP = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "object": dict,
        "array": list,
    }

    def validate(self, params):
        # ① 检查必填参数
        for field in required:
            if field not in params:
                errors.append(...)

        # ② 检查参数类型
        for key, value in params.items():
            if not isinstance(value, expected_python_type):
                errors.append(...)

        # ③ 检查枚举值
            if "enum" in prop_def and value not in prop_def["enum"]:
                errors.append(...)

        # ④ 检查字符串长度
            if "minLength" in prop_def and len(value) < min_len:
                errors.append(...)

        return len(errors) == 0, errors
```

**支持的四项校验**：

| 校验项 | JSON Schema 关键字 | 说明 |
|--------|------------------|------|
| 必填 | `required: ["city"]` | 缺少必填字段直接拒绝 |
| 类型 | `type: "string"` | JSON 类型映射到 Python 类型 |
| 枚举 | `enum: ["今天","明天"]` | 值必须在白名单内 |
| 长度 | `minLength: 1` | 字符串最小长度限制 |

---

### 2. 统一错误处理器 (error_handler.py)

**职责**：将各种 Python 异常分类为"可重试"和"不可重试"，并给出用户友好的中文提示。

```python
class ErrorHandler:
    RETRYABLE_ERRORS = (
        TimeoutError,           # 超时 → 可重试
        ConnectionError,        # 连接失败 → 可重试
        ConnectionRefusedError, # 拒绝连接 → 可重试
        ConnectionResetError,   # 连接重置 → 可重试
        OSError,                # IO 错误 → 可重试
    )

    ERROR_CATEGORIES = {
        TimeoutError:         {"message": "请求超时",    "suggestion": "请稍后重试"},
        ConnectionError:      {"message": "网络连接失败","suggestion": "请检查网络"},
        PermissionError:      {"message": "权限不足",    "suggestion": "请检查API密钥"},
        ValueError:           {"message": "参数值不合法","suggestion": "请检查输入"},
        # ...
    }

    def handle(self, exception, context=None):
        retryable = issubclass(type(exception), self.RETRYABLE_ERRORS)
        # 匹配错误类型，返回统一响应格式
        return {
            "error":      f"{分类.message}: {str(exception)}",
            "retryable":  retryable,
            "suggestion": 分类.suggestion,
        }
```

**设计要点**：
- `issubclass()` 检查异常继承链，一次匹配覆盖所有子类异常
- `context` 参数预留扩展空间，可记录出错的工具名和参数

**运行实例**（来自实际测试输出）：

```
⚠ 第 1 次重试失败，1.4s 后重试... (原因: timed out)
❌ 工具执行失败
错误: 请求超时: timed out
💡 建议: 请稍后重试，或检查网络连接
```

---

### 3. 指数退避重试 (retry.py)

**职责**：遇到可重试错误时，按指数增长的时间间隔自动重试，防止对下游服务造成拥塞。

```python
class ExponentialBackoffRetry:
    """
    重试延迟公式: min(base_delay × 2^attempt + random_jitter, max_delay)

    attempt=0 → 延迟 ≈ 1.0~1.5s
    attempt=1 → 延迟 ≈ 2.0~2.5s
    attempt=2 → 延迟 ≈ 4.0~4.5s
    """

    def __init__(self, max_retries=3, base_delay=1.0, max_delay=30.0):
        ...

    def retry(self, func, *args, **kwargs):
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries:
                    raise                        # 最后一次仍失败，向上抛
                delay = self.base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(delay)
```

**三个关键参数**：

| 参数 | 默认值 | 含义 |
|------|--------|------|
| `max_retries` | 3 | 最多重试 3 次（共执行 4 次） |
| `base_delay` | 1.0s | 基础延迟，每次翻倍 |
| `max_delay` | 30.0s | 延迟上限，防止无限增长 |

> 添加 `random.uniform(0, 0.5)` 的随机抖动是为了避免"惊群效应"——多个客户端同时重试导致请求尖峰。

---

### 4. 熔断器 (circuit_breaker.py)

**职责**：当连续失败达到阈值时，临时"熔断"——快速失败而不是继续尝试，防止级联故障。

**三态模型**：

```
       连续失败 ≥ threshold
  CLOSED ────────────────────→ OPEN
    ↑                            │
    │              recovery_timeout 到期
    │                            ↓
    └───────────────── HALF_OPEN ←
         调用成功              调用失败 → 回到 OPEN
```

```python
class CircuitBreaker:
    STATE_CLOSED     = "closed"      # 正常通行
    STATE_OPEN       = "open"        # 拒绝执行，快速失败
    STATE_HALF_OPEN  = "half_open"   # 探测期，允许一次尝试

    def execute(self, func, *args, **kwargs):
        # OPEN 状态：检查是否到了恢复时间
        if self.state == STATE_OPEN:
            if time.time() - self.last_failure_time >= recovery_timeout:
                self.state = STATE_HALF_OPEN    # 进入探测
            else:
                raise CircuitBreakerOpenError() # 快速失败

        try:
            result = func(*args, **kwargs)
            self._on_success()   # 成功 → 恢复 CLOSED
            return result
        except Exception:
            self._on_failure()   # 失败 → 计数+1，可能触发 OPEN
            raise
```

> 熔断器使用 `threading.Lock()` 保证状态切换的线程安全，为将来并发场景做准备。

---

### 5. 工具定义与真实 API (tool_definitions.py)

**职责**：定义工具的 JSON Schema 和对应的真实 API 调用函数。

#### 工具定义示例

```python
weather_tool = {
    "name": "get_weather",
    "description": "获取指定城市的实时天气信息，包括温度、天气状况、湿度等",
    "parameters": {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "城市名称，如'北京'、'shanghai'",
                "minLength": 1,
            },
        },
        "required": ["city"],
    },
}
```

> 这种结构与 OpenAI Function Calling 的 tools 定义兼容，未来可无缝迁移。

#### 真实 API 实现

| 工具 | 函数 | 数据源 | 说明 |
|------|------|--------|------|
| 天气查询 | `fetch_weather(city)` | [wttr.in](https://wttr.in) | 免费实时天气 API，全球城市可用 |
| 时间查询 | `get_current_time()` | 本地 `datetime` | 无外部依赖 |

**天气 API 调用**：

```python
def fetch_weather(city):
    url = f"https://wttr.in/{city}?format=j1"
    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()
    data = response.json()

    current = data["current_condition"][0]
    return {
        "city": city,
        "temperature": f"{current['temp_C']}°C",
        "humidity":    f"{current['humidity']}%",
        "condition":   current["weatherDesc"][0]["value"],
        "wind":        f"{current['windspeedKmph']} km/h",
        "feels_like":  f"{current['FeelsLikeC']}°C",
        "visibility":  f"{current['visibility']} km",
    }
```

> ⚠️ 搜索工具因国内网络限制已被移除。可选的替代方案包括 [SerpAPI](https://serpapi.com/)（需注册免费额度）或 [Bing Web Search API](https://www.microsoft.com/en-us/bing/apis/bing-web-search-api)。

> 踩坑记录：`datetime.tzname(None)` 会报 `TypeError: tzname() takes no arguments`，因为 `tzname()` 不接受参数，已修复为直接调用 `.tzname()`。

---

### 6. 工具执行器 (tool_executor.py)

**职责**：将五个模块串联成完整的执行链路，并集成 LLM 进行意图识别和回复生成。

```python
class ToolExecutor:
    def __init__(self):
        self.tools = {}                          # 工具注册表
        self.validator = ParameterValidator      # 参数验证器（类引用）
        self.error_handler = ErrorHandler()      # 错误处理器
        self.retry = ExponentialBackoffRetry()   # 重试器
        self.breaker = CircuitBreaker()          # 熔断器

    def register_tool(self, name, tool_def, func):
        """注册工具：名称 → {定义, 函数} 映射"""
        self.tools[name] = {"definition": tool_def, "function": func}

    def execute_tool(self, tool_name, params):
        """执行工具：验证 → 熔断 → 重试 ─→ 错误处理"""
        # ① 检查工具是否已注册
        # ② 参数验证 (ParameterValidator)
        # ③ 熔断器包裹重试器包裹实际函数
        #      breaker.execute( lambda: retry.retry(tool_func, **params) )
        # ④ 异常 → ErrorHandler 生成统一错误响应

    def handle_user_request(self, user_input):
        """三步处理链路"""
        # 步骤1: LLM 选工具 + 提取参数 → JSON 输出
        tool_name, params = self._ask_llm_for_tool(user_input)

        # 步骤2: 执行工具（验证→熔断→重试→错误处理）
        tool_result = self.execute_tool(tool_name, params)

        # 步骤3: LLM 将结果转为自然语言回复
        final = self._generate_final_response(user_input, tool_result)
        return final
```

#### LLM 工具选择 Prompt

让 LLM 稳定输出 JSON 的关键技巧：

```python
def _build_tool_selection_prompt(self, user_input):
    prompt = f"""你是一个工具选择助手。根据用户输入，选择最合适的工具并提取参数。

可用工具:
- get_weather: 获取指定城市的实时天气信息
  参数定义: {{"type": "object", "properties": {{"city": {{"type": "string"}}}}}}
- get_current_time: 获取当前的日期和时间
  参数定义: {{"type": "object", "properties": {{}}, "required": []}}

用户输入: {user_input}

请严格按以下 JSON 格式回答，不要添加任何其他内容:
{{"tool": "工具名称", "params": {{"参数名": "参数值"}}}}

如果无法匹配任何工具，请返回:
{{"tool": null, "params": {{}}}}"""
```

**设计要点**：
- `temperature=0.1`：极低温度确保工具选择和参数提取的稳定性
- JSON 输出做了容错解析：自动去除 ` ```json ` 包裹标记
- `json.JSONDecodeError` 捕获后降级返回 `(None, {})`

#### 完整的防御链路

```
execute_tool("get_weather", {"city": "北京"})
    │
    ├── ① 工具名校验     → 未注册？返回 {"success": False, "error": "工具未注册"}
    │
    ├── ② 参数验证       → 缺少必填？返回 {"success": False, "details": ["缺少必填参数: 'city'"]}
    │
    ├── ③ CircuitBreaker.execute()
    │   ├── OPEN 状态     → 快速失败 CircuitBreakerOpenError
    │   └── CLOSED/半开   → 继续 ↓
    │
    ├── ④ ExponentialBackoffRetry.retry()
    │   ├── 第 1 次成功   → 返回结果
    │   ├── 失败          → 延迟 1~1.5s 重试
    │   ├── 第 2 次失败   → 延迟 2~2.5s 重试
    │   ├── 第 3 次失败   → 延迟 4~4.5s 重试
    │   └── 第 4 次失败   → 向上抛异常
    │
    └── ⑤ ErrorHandler.handle()
        └── 异常分类 → {"success": False, "error": "...", "retryable": ..., "suggestion": "..."}
```

---

## 与 Chapter 1 的对比

| 维度 | Chapter 1 (SimpleAgent) | Chapter 2 (ToolExecutor) |
|------|------------------------|--------------------------|
| 参数验证 | 无（LLM 输出什么就用什么） | JSON Schema 风格校验：必填/类型/枚举/长度 |
| 错误处理 | `try/except` 打印 `思考过程出错` | 统一分类、中文提示、可重试标记 |
| 重试机制 | 无（一次失败即返回错误） | 指数退避 + 随机抖动，最多 4 次尝试 |
| 熔断保护 | 无 | 三态熔断器（闭→开→半开），防雪崩 |
| 工具注册 | 硬编码 if-elif 分支 (`tools.py`) | 注册中心模式 (`register_tool`) |
| LLM 选择工具 | Prompt Engineering 文本解析 | Prompt → JSON 格式，结构化稳定 |
| 真实 API | 模拟数据（字典匹配） | wttr.in 实时天气 API |
| 可扩展性 | 添加工具需改 `_use_tool` 方法 | 只需 `register_tool` + 实现函数 |

---

## 实际运行效果

```
🚀 启动工具调用框架演示
==================================================
📋 已注册的工具:
  🔧 get_weather: 获取指定城市的实时天气信息
  🔧 get_current_time: 获取当前的日期和时间
==================================================

🔍 验证参数验证器...
  → 传入空参数给 get_weather（缺少必填 city）:
     success=False, error=参数验证失败
     details=["缺少必填参数: 'city'"]
  ✅ 参数验证器工作正常

==================================================
👤 用户输入: 北京今天天气怎么样？
==================================================

🧠 [步骤1] LLM 分析用户意图，选择工具并提取参数...
  → 选择工具: get_weather
  → 提取参数: {"city": "北京"}

⚙ [步骤2] 执行工具 'get_weather'...
  ✅ 工具执行成功
  → 原始结果: {"city": "北京", "temperature": "32°C", "humidity": "30%",
               "condition": "Sunny", "wind": "10 km/h"}

🤖 [步骤3] LLM 根据执行结果生成自然语言回复...
  → 北京今天天气晴朗，气温32°C，体感温度30°C，湿度30%，
     风力不大（10 km/h），出门注意防晒！
==================================================
```

---

## 核心 Takeaways

1. **工具调用的完整防御链路**：验证 → 熔断 → 重试 → 错误处理 形成一个闭环
2. **JSON Schema 是工具定义的通用语言**：与 OpenAI Function Calling 兼容，方便未来迁移
3. **指数退避 + 随机抖动**：标准的生产级重试策略，避免下游拥塞
4. **熔断器三态模型**：CLOSED → OPEN → HALF_OPEN，是微服务架构的标准模式
5. **让 LLM 输出 JSON 而非文本**：相比第一版的"思考：/工具：/指令："文本解析，JSON 更稳定可靠
6. **免费 API 也能玩得转**：wttr.in 无需 API Key，全球城市可用，适合学习阶段
