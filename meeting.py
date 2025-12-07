# meeting.py
from typing import List, Optional
from openai import OpenAI
from agent import ResearchAgent

class MeetingController:
    def __init__(self, api_key: str, base_url: str = None, model: str = "gpt-4o"):
        """
        初始化会议控制器 (主持人)
        """
        self.agents: List[ResearchAgent] = [] # 参会专家列表
        self.history = []     # 完整的会议记录
        self.topic = ""       # 当前议题
        
        # 主持人自己也需要一个 LLM 大脑来做决策
        if base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=api_key)
        self.model = model

    def set_topic(self, topic: str):
        """设定会议议题"""
        self.topic = topic
        # 清空历史，开始新会话
        self.history = [
            {"role": "user", "content": f"大家好，今天的会议议题是：{topic}。请各位专家依次发表看法。"}
        ]

    def add_agent(self, agent: ResearchAgent):
        """邀请专家入会"""
        self.agents.append(agent)

    def select_next_speaker(self) -> ResearchAgent:
        """
        【核心逻辑】主持人通过分析上下文，决定下一个谁发言
        """
        # 如果只有一个人，那就只能是他了
        if len(self.agents) == 1:
            return self.agents[0]
            
        # 1. 准备给主持人的 Prompt
        agent_profiles = "\n".join([f"- {a.name}: {a.system_prompt}" for a in self.agents])
        
        # 只取最近 10 条记录作为决策依据，节省 Token
        recent_history = []
        for msg in self.history[-10:]:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:100] # 截断一下防止太长
            recent_history.append(f"{role}: {content}")
        history_text = "\n".join(recent_history)

        prompt = f"""
        你是一场科研组会的主持人。
        
        当前议题：{self.topic}
        参会专家：
        {agent_profiles}
        
        最近的对话：
        {history_text}
        
        请决策：下一位最应该发言的专家是谁？
        决策规则：
        1. 如果有人被指名提问，优先选他。
        2. 如果user提出问题没有指定对象，则是user上一轮的专家回答。
        3. 如果话题涉及某人专业领域，优先选他。
        4. 避免同一个人连续发言。
        
        请仅返回专家的【名字】，不要包含任何其他字符。
        """

        try:
            # 2. 调用 LLM 决策
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            selected_name = response.choices[0].message.content.strip()
            
            # 3. 匹配名字并返回对象
            for agent in self.agents:
                if agent.name in selected_name:
                    return agent
            
            # 如果匹配失败（LLM 偶尔会发疯），默认顺延给下一个人
            return self.agents[0]
            
        except Exception as e:
            print(f"主持人掉线了: {e}")
            return self.agents[0]

    def step(self) -> dict:
        """
        推进会议进行“一步” (Round)
        :return: 这一轮的发言记录 {"role": "专家名", "content": "发言内容"}
        """
        # 1. 主持人点名
        speaker = self.select_next_speaker()
        
        # 2. 构造上下文 (RAG 的一种变体)
        # 我们把整个会议记录拼接成字符串，喂给专家
        # 提示：实际生产中，如果记录太长，需要做 Summarization (摘要)
        context_str = "\n".join([f"[{m['role']}]: {m['content']}" for m in self.history])
        
        prompt_for_speaker = f"""
        这是目前的会议记录：
        {context_str}
        
        轮到你了。请作为【{speaker.name}】，结合你的专业背景({speaker.system_prompt})，
        对刚才的讨论发表看法。
        要求：
        1. 观点鲜明，可以反驳其他人。
        2. 可以质疑某位专家，并点名他解答你的疑问，但不要同时质疑多个人。
        3. 如果是第一轮发言，请先自我介绍并亮明观点。
        4. 如果回答超过500字，在最后给出一个100字以内的总结。
        5. 避免重复回答之前说过的内容。
        """
        
        # 3. 专家发言
        # 注意：这里我们调用 agent.chat，但不传入图片，纯文字讨论
        content = speaker.chat(prompt_for_speaker)
        
        # 4. 记录历史
        message = {"role": speaker.name, "content": content}
        self.history.append(message)
        
        return message