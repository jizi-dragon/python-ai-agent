# agent.py
from brain import AgentBrain
from tools import AgentTools

class SimpleAgent:
    """一个简单的任务规划 AI Agent"""
    
    def __init__(self):
        self.brain = AgentBrain()
        # 静态工具类无需实例化
        self.tools = AgentTools
        # 定义 Agent 知道的工具列表及其描述，用于提示大脑
        self.tool_descriptions = """
        你可以使用以下工具：
        1. 搜索工具：当你需要获取最新、未知的信息时使用，例如'搜索 北京天气'。
        2. 计划工具：当你需要将多个步骤整理成计划时使用，例如'制定计划 [步骤1，步骤2]'。
        3. 时间工具：当你需要知道当前时间时使用，指令就是'获取时间'。
        4. 计算工具：当你需要进行数学计算时使用，例如'计算 3+5*2'。
        """
    
    def run(self, user_task):
        """运行 Agent 的主循环"""
        print(f"&#x1f3af; 用户任务: {user_task}")
        print("=" * 40)
        
        # 第一步：感知与初步思考
        initial_prompt = f"""
        你的角色是一个任务规划助手。
        {self.tool_descriptions}
        
        用户的任务是：{user_task}
        
        请严格按照以下固定格式回答，不要添加额外内容：
        思考：[简要分析任务需要什么]
        工具：[选择要使用的工具名称，如果没有合适的就写'无']
        指令：[发送给该工具的具体指令内容]
        """
        
        initial_response = self.brain.think(initial_prompt)
        print("&#x1f9e0; 初始思考结果：")
        print(initial_response)
        print("-" * 20)
        
        # 第二步：解析思考结果，提取工具和指令（鲁棒性优化）
        lines = [line.strip() for line in initial_response.split('\n') if line.strip()]
        tool_to_use = "无"
        tool_instruction = ""
        
        for line in lines:
            if line.startswith("思考："):
                continue  # 跳过思考行
            elif line.startswith("工具："):
                tool_to_use = line.replace("工具：", "").strip()
            elif line.startswith("指令："):
                tool_instruction = line.replace("指令：", "").strip()
        
        # 第三步：执行行动
        result = self._use_tool(tool_to_use, tool_instruction)
        print("&#x1f6e0;&#xfe0f;  执行结果：")
        print(result)
        print("=" * 40)
        
        # 第四步：整合结果并反馈给用户
        final_prompt = f"""
        用户原始任务：{user_task}
        你已经进行了思考并使用了工具。
        思考过程：{initial_response}
        工具执行结果：{result}
        
        现在，请生成一段完整的、对用户的最终回复，直接给出有帮助的答案或计划，语言要自然友好。
        """
        
        final_response = self.brain.think(final_prompt)
        print("&#x1f4a1; 最终回复给用户：")
        print(final_response)
        
        return final_response
    
    def _use_tool(self, tool_name, instruction):
        """根据工具名称调用具体的工具函数"""
        # 统一工具名称匹配（兼容大小写/多余空格）
        tool_name = tool_name.strip()
        
        if tool_name == "搜索工具":
            return self.tools.search_web(instruction)
        elif tool_name == "计划工具":
            # 兼容中英文逗号、括号，处理空指令
            if not instruction:
                return "[计划工具] 未提供计划步骤，无法生成日程。"
            # 移除括号并拆分步骤（兼容 []/()/{} 括号）
            clean_instr = instruction.strip('[](){}').strip()
            # 同时支持中英文逗号拆分
            steps = [s.strip() for s in clean_instr.replace('，', ',').split(',') if s.strip()]
            return self.tools.make_schedule(steps)
        elif tool_name == "时间工具":
            return self.tools.get_current_time()
        elif tool_name == "计算工具":
            return self.tools.calculate(instruction)
        elif tool_name == "无":
            return "[系统] 无需使用工具，直接回答用户即可。"
        else:
            return f"[系统] 未知工具：{tool_name}，无法执行。"

# 运行我们的 Agent！
if __name__ == "__main__":
    print("&#x1f916; 启动 SimpleAgent...")
    my_agent = SimpleAgent()
    
    # 测试几个不同的任务
    test_tasks = [
        "我想去旅行，帮我规划一下需要准备什么",
        "现在几点了？",
        "计算一下 15 的平方加上 20 的三分之一是多少",
    ]
    
    for task in test_tasks:
        my_agent.run(task)
        print("\n" + "#" * 50 + "\n")