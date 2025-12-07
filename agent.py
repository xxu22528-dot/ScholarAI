# agent.py
from typing import List, Dict, Optional
from openai import OpenAI

class ResearchAgent:
    def __init__(self, name: str, system_prompt: str, model: str, api_key: str, base_url: str = None):
        """
        初始化科研代理人
        :param name: 名字 (e.g. "论文精读助手")
        :param system_prompt: 人设 (e.g. "你是一个严谨的科研专家...")
        :param model: 模型名称 (e.g. "gpt-4o", "deepseek-chat")
        :param api_key: API 密钥
        :param base_url: 模型服务商地址
        """
        self.name = name
        self.model = model
        self.system_prompt = system_prompt
        
        # 1. 初始化客户端 (支持多模型的核心)
        if base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=api_key) # 默认连 OpenAI
            
        # 2. 初始化记忆
        self.history: List[Dict] = [
            {"role": "system", "content": system_prompt}
        ]

    def chat(self, user_input: str, image_base64: Optional[str] = None) -> str:
        """
        核心对话函数
        :param user_input: 用户的文字输入
        :param image_base64: 图片的 Base64 编码字符串 (可选)
        """
        # A. 构建消息内容
        if image_base64:
            # --- 视觉模式 ---
            # 大多数兼容 OpenAI 视觉接口的模型都接受这种格式
            content = [
                {"type": "text", "text": user_input},
                {
                    "type": "image_url", 
                    "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                }
            ]
        else:
            # --- 纯文本模式 ---
            content = user_input

        # B. 用户消息入栈
        self.history.append({"role": "user", "content": content})

        try:
            # C. 调用 API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                stream=False, # 暂时不使用流式输出，保持逻辑简单
            )
            
            reply = response.choices[0].message.content
            
            # D. AI 回复入栈
            # 注意：即使输入是复杂的图文结构，AI 的回复通常只是纯文本
            self.history.append({"role": "assistant", "content": reply})
            
            return reply

        except Exception as e:
            error_msg = f"❌ 接口调用失败: {str(e)}"
            # 出错时不记录进历史，防止污染记忆
            self.history.pop() 
            return error_msg

    def clear_memory(self):
        """清空对话历史，重置为初始状态"""
        self.history = [
            {"role": "system", "content": self.system_prompt}
        ]
    def summarize(self, context: str, output_format: str = "markdown") -> str:
        """
        专门用于生成总结或报告
        """
        prompt = f"""
        请根据以下对话记录，整理一份结构化的科研纪要。
        
        【对话记录】
        {context}
        
        【要求】
        1. 使用 {output_format} 格式。
        2. 包含以下部分：
           - 💡 核心观点摘要 (Abstract)
           - ⚔️ 主要争议/讨论过程,重点记录user的问题以及讨论出的结论 (Discussion)
           - 📌 下一步建议或结论 (Conclusion)
        3. 记录全面细致。
        """
        
        # 临时构建一条消息，不影响长期记忆
        messages = [
            {"role": "system", "content": "你是一名专业的学术编辑，擅长整理会议纪要。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"生成报告失败: {str(e)}"

def main():
    """测试代码"""
    agent = ResearchAgent(
        name="论文精读助手",
        system_prompt="你是一个严谨的科研专家，能从论文中提取有效的信息，并给出相应的建议。",
        model="qwen3-vl-flash",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="sk-xxx"
    )
    print(agent.chat("请给我一个关于机器学习的论文"))


    # client = OpenAI(
    #     # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx"
    #     api_key="sk-xxx",
    #     base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    # )
    # completion = client.chat.completions.create(
    #     # 模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
    #     model="qwen-plus",
    #     messages=[
    #         {"role": "system", "content": "You are a helpful assistant."},
    #         {"role": "user", "content": "你是谁？"},
    #     ]
    # )
    # completion = client.chat.completions.create(
    #     model="qwen-vl-plus",  # 此处以qwen-vl-plus为例，可按需更换模型名称。模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
    #     messages=[{"role": "user","content": [
    #             {"type": "image_url",
    #             "image_url": {"url": "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg"}},
    #             {"type": "text", "text": "这是什么"},
    #             ]}]
    #     )
    #print(completion.model_dump_json().message.content)

if __name__ == "__main__":
    main()