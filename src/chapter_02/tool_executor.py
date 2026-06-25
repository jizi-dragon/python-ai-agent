import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from parameter_validator import ParameterValidator
from error_handler import ErrorHandler
from retry import ExponentialBackoffRetry
from circuit_breaker import CircuitBreaker


load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1"

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_API_URL)


class ToolExecutor:
    """工具执行器 —— 具备参数验证、重试、熔断、错误处理的完整工具调用框架"""

    def __init__(self):
        self.tools = {}
        self.validator = ParameterValidator
        self.error_handler = ErrorHandler()
        self.retry = ExponentialBackoffRetry()
        self.breaker = CircuitBreaker()

    def register_tool(self, name, tool_def, func):
        self.tools[name] = {
            "definition": tool_def,
            "function": func,
        }

    def execute_tool(self, tool_name, params):
        if tool_name not in self.tools:
            return {
                "success": False,
                "error": f"工具 '{tool_name}' 未注册",
            }

        tool_info = self.tools[tool_name]
        tool_def = tool_info["definition"]
        tool_func = tool_info["function"]

        validator = self.validator(tool_def)
        is_valid, errors = validator.validate(params)

        if not is_valid:
            return {
                "success": False,
                "error": "参数验证失败",
                "details": errors,
            }

        try:
            def execute_with_retry():
                return self.breaker.execute(
                    lambda: self.retry.retry(tool_func, **params)
                )

            result = execute_with_retry()

            return {
                "success": True,
                "result": result,
                "tool": tool_name,
            }

        except Exception as e:
            error_response = self.error_handler.handle(e, {
                "tool": tool_name,
                "params": params,
            })

            return {
                "success": False,
                "error": error_response["error"],
                "retryable": error_response.get("retryable", False),
                "suggestion": error_response.get("suggestion", ""),
            }

    def _build_tool_selection_prompt(self, user_input):
        tools_desc = []
        for name, info in self.tools.items():
            tool_def = info["definition"]
            params_desc = json.dumps(tool_def["parameters"], ensure_ascii=False)
            tools_desc.append(
                f"- {name}: {tool_def['description']}\n  参数定义: {params_desc}"
            )

        prompt = f"""你是一个工具选择助手。根据用户输入，选择最合适的工具并提取参数。

可用工具:
{chr(10).join(tools_desc)}

用户输入: {user_input}

请严格按以下 JSON 格式回答，不要添加任何其他内容:
{{"tool": "工具名称", "params": {{"参数名": "参数值"}}}} 

如果无法匹配任何工具，请返回:
{{"tool": null, "params": {{}}}}"""

        return prompt

    def _ask_llm_for_tool(self, user_input):
        prompt = self._build_tool_selection_prompt(user_input)

        try:
            response = client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=300,
            )

            content = response.choices[0].message.content.strip()

            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            result = json.loads(content)
            return result.get("tool"), result.get("params", {})

        except json.JSONDecodeError:
            print(f"  LLM 返回非 JSON 格式: {content[:200]}")
            return None, {}
        except Exception as e:
            print(f"  LLM 调用失败: {e}")
            return None, {}

    def _generate_final_response(self, user_input, tool_name, params, tool_result):
        prompt = f"""你是一个友好的 AI 助手。请根据工具执行结果，用自然语言回答用户。

用户原始问题: {user_input}
使用的工具: {tool_name}
工具参数: {json.dumps(params, ensure_ascii=False)}
工具返回结果: {json.dumps(tool_result, ensure_ascii=False)}

请用中文简洁友好地回答用户，直接给出有用信息。"""

        try:
            response = client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if tool_result.get("success"):
                return f"查询结果: {json.dumps(tool_result['result'], ensure_ascii=False)}"
            return f"抱歉，工具执行失败: {tool_result.get('error', '未知错误')}"

    def handle_user_request(self, user_input):
        print(f"\n{'='*50}")
        print(f"👤 用户输入: {user_input}")
        print(f"{'='*50}")

        print(f"\n🧠 [步骤1] LLM 分析用户意图，选择工具并提取参数...")
        tool_name, params = self._ask_llm_for_tool(user_input)

        if tool_name is None:
            no_tool_response = "抱歉，我暂时无法理解您的请求。请尝试询问天气、时间或搜索相关信息。"
            print(f"  → 未匹配到合适的工具")
            print(f"🤖 最终回复: {no_tool_response}")
            return no_tool_response

        print(f"  → 选择工具: {tool_name}")
        print(f"  → 提取参数: {json.dumps(params, ensure_ascii=False)}")

        print(f"\n⚙ [步骤2] 执行工具 '{tool_name}'...")
        tool_result = self.execute_tool(tool_name, params)

        if tool_result["success"]:
            print(f"  ✅ 工具执行成功")
            print(f"  → 原始结果: {json.dumps(tool_result['result'], ensure_ascii=False)}")
        else:
            print(f"  ❌ 工具执行失败")
            print(f"  → 错误: {tool_result.get('error')}")
            if tool_result.get("suggestion"):
                print(f"  💡 建议: {tool_result['suggestion']}")

        print(f"\n🤖 [步骤3] LLM 根据执行结果生成自然语言回复...")
        final_response = self._generate_final_response(
            user_input, tool_name, params, tool_result
        )

        print(f"  → {final_response}")
        print(f"{'='*50}\n")

        return final_response
