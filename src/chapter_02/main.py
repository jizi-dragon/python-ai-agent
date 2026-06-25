from tool_executor import ToolExecutor
from tool_definitions import (
    weather_tool, time_tool,
    fetch_weather, get_current_time,
)


def main():
    print("🚀 启动工具调用框架演示")
    print("=" * 50)
    print("📋 已注册的工具:")
    for tool_def in [weather_tool, time_tool]:
        print(f"  🔧 {tool_def['name']}: {tool_def['description']}")
    print("=" * 50)

    executor = ToolExecutor()
    executor.register_tool("get_weather", weather_tool, fetch_weather)
    executor.register_tool("get_current_time", time_tool, get_current_time)

    print("\n🔍 验证参数验证器...")
    print("  → 传入空参数给 get_weather（缺少必填 city）:")
    result = executor.execute_tool("get_weather", {})
    print(f"     success={result['success']}, error={result.get('error')}")
    print(f"     details={result.get('details')}")
    print("  ✅ 参数验证器工作正常\n")

    test_cases = [
        "北京今天天气怎么样？",
        "现在几点了？",
        "上海天气如何",
    ]

    for user_input in test_cases:
        executor.handle_user_request(user_input)


if __name__ == "__main__":
    main()
