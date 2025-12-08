import asyncio
import re
import json
from typing import List, Dict
from openai import AsyncOpenAI

class FocusSession:
    def __init__(self, api_key: str, base_url: str = None, model: str = "gpt-3.5-turbo", topic: str = ""):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.topic = topic
        
        if base_url:
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = AsyncOpenAI(api_key=api_key)
            
        self.insight_notes = []
        self.full_input_buffer = ""
        # 共识集数据结构
        self.confirmed_consensus = []  # 已确认共识
        self.pending_consensus = []    # 待确认共识
        self.conversation_history = [] # 对话历史记录

    def _chunk_text(self, text: str, max_length: int = 300) -> List[str]:
        """
        语义分块：根据标点符号或长度切分
        增加分块粒度，避免过细切分。只有当长度超过 max_length 且遇到结束标点时才切分。
        """
        # 简单按标点切分
        # keep delimiters
        parts = re.split(r'([。！？\n])', text)
        chunks = []
        current_chunk = ""
        
        for part in parts:
            current_chunk += part
            # 只有当当前块长度超过阈值，且遇到了句子结束符，才进行切分
            # 这样可以保证一个 chunk 包含完整的句子，且有足够的上下文
            if len(current_chunk) >= max_length and part in ['。', '！', '？', '\n']:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = ""
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
            
        return chunks

    async def _think_background(self, chunk: str, chunk_id: int):
        """
        后台思考者：针对片段进行联想发散
        """
        prompt = f"""你是一个敏锐的记录员。对方正在汇报片段：'{chunk}'。
当前讨论的主题是：【{self.topic}】。
任务：记录这段话引发的深层联想，重点关注与主题【{self.topic}】相关的细节。
要求：
1. 必须严格区分【原文内容】和【发散思考】。
2. 严禁将你的联想强加给对方。
3. 【我的思考】部分必须严格控制在 50 字以内，言简意赅。
4. 输出格式必须为：
   原文点：<简要概括原文核心点>
   我的思考：<你的联想、疑问或延伸，尽量与主题 '{self.topic}' 挂钩>"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.choices[0].message.content
            # 简单清理一下
            note = content.strip()
            self.insight_notes.append({"id": chunk_id, "chunk": chunk, "note": note})
            return note
        except Exception as e:
            return f"Thinking failed: {e}"

    async def _select_best_insight(self) -> str:
        """
        聚焦选择器：选出 1-3 个最有价值的切入点
        """
        if not self.insight_notes:
            return "无"
            
        all_notes_str = "\n".join([f"ID {n['id']}: {n['note']}" for n in self.insight_notes])
        
        prompt = f"""回顾后台记录的笔记：
{all_notes_str}

当前讨论的主题是：【{self.topic}】。
请挑选出 0-3 个最值得深入讨论的切入点。
要求：
1. 优先包含对方明确提出的问题（如果有）。
2. 挑选最犀利、最有趣或最值得深究的细节。
3. 剔除那些明显偏离主题【{self.topic}】的无关发散。
4. 返回格式：请直接返回被选中点的【ID数字列表】，例如：[1, 3, 5]，不要返回其他文字。"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            selection = response.choices[0].message.content.strip()
            
            # 提取所有数字 ID
            selected_ids = [int(i) for i in re.findall(r'\d+', selection)]
            
            selected_notes = []
            for note in self.insight_notes:
                if note['id'] in selected_ids:
                    selected_notes.append(f"【切入点 {note['id']}】: {note['note']}")
            
            if selected_notes:
                return "\n\n".join(selected_notes)
            
            # Fallback
            return self.insight_notes[-1]['note']
        except Exception as e:
            return f"Selection failed: {e}"

    async def _analyze_consensus(self, user_input: str, ai_response: str) -> Dict:
        """
        共识分析器：分析对话内容，更新共识集
        """
        # 获取最近几轮对话历史用于上下文分析
        recent_history = self.conversation_history[-3:] if len(self.conversation_history) > 3 else self.conversation_history
        history_str = ""
        for i, turn in enumerate(recent_history, 1):
            history_str += f"第{i}轮:\n用户: {turn['user'][:100]}...\nAI: {turn['ai'][:100]}...\n\n"
        
        prompt = f"""分析以下对话内容，判断共识达成情况：

当前轮对话：
用户发言：{user_input}
AI 回应：{ai_response}

最近对话历史：
{history_str}

当前已确认共识：{self.confirmed_consensus}
当前待确认共识：{self.pending_consensus}

任务：
1. 检查待确认共识中是否有可以转化为已确认共识的内容
2. 提出 0-2 个新的待确认共识点（基于当前对话内容）
3. 判断标准：
   - 双方明确表达相同观点或事实
   - 一方提出观点，另一方明确表示认同
   - 避免将假设或推测当作共识
   - 避免将单方面的陈述当作共识

输出格式为 JSON：{{"confirmed": ["新确认共识1", "新确认共识2"], "new_pending": ["新待确认共识1", "新待确认共识2"]}}

注意：共识应该是双方都明确认可的观点或事实，要有充分的证据支持。"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            result = response.choices[0].message.content
            consensus_data = json.loads(result)
            
            # 验证和清理共识数据
            validated_data = {
                "confirmed": [],
                "new_pending": []
            }
            
            # 验证确认的共识
            for consensus in consensus_data.get("confirmed", []):
                if isinstance(consensus, str) and consensus.strip() and len(consensus.strip()) > 5:
                    validated_data["confirmed"].append(consensus.strip())
            
            # 验证新的待确认共识
            for pending in consensus_data.get("new_pending", []):
                if isinstance(pending, str) and pending.strip() and len(pending.strip()) > 5:
                    validated_data["new_pending"].append(pending.strip())
            
            return validated_data
            
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return {"confirmed": [], "new_pending": []}
        except Exception as e:
            print(f"共识分析错误: {e}")
            return {"confirmed": [], "new_pending": []}

    async def _speak_response(self, selected_point: str) -> str:
        """
        表达生成器：生成简短回复
        """
        prompt = f"""对方刚称述完它的观点。你需要和他对话和探讨。
当前讨论的主题是：【{self.topic}】。

当前已确认共识：{self.confirmed_consensus}
当前待确认共识：{self.pending_consensus}

任务：基于以下选中的切入点进行回复（注意：切入点中包含了【原文点】和【我的思考】）：
{selected_point}

动作：将这几个点串联起来，进行自然的深度回应。确保你的回应紧扣主题【{self.topic}】，不要跑题。
约束：
1. 必须分清：【原文点】是对方说的，【我的思考】是你自己的想法。严禁把你的思考说成是对方的观点！
2. 如果其中包含对方明确提出的问题，必须先回答问题。
3. 像在交流讨论一样说话，不要打官腔，不要做"综上所述"类的总结。
4. 观点要鲜明，不要模棱两可。
5. 可以适当引用已有共识，避免重复讨论已达成共识的内容。
6. 可以在回复中提出 0-2 个新的待确认共识点（用【待确认】标记）。
7. 一般篇幅在50-100字左右，最长篇幅不要超过200字，可长可短。"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Speaking failed: {e}"

    async def process_full_input(self, text: str, progress_callback=None):
        """
        主流程：处理全量输入 -> 异步思考 -> 选择 -> 表达 -> 共识分析
        """
        self.full_input_buffer = text
        self.insight_notes = [] # Reset
        
        # 1. Chunking
        chunks = self._chunk_text(text)
        
        # 2. Async Listening & Expanding
        tasks = []
        for i, chunk in enumerate(chunks):
            tasks.append(self._think_background(chunk, i))
        
        # 并发执行所有思考任务
        for task in asyncio.as_completed(tasks):
            await task
            if progress_callback:
                progress_callback(self.insight_notes)
        
        # 3. Focusing & Selecting
        selected_point = await self._select_best_insight()
        
        # 4. Speaking
        final_response = await self._speak_response(selected_point)
        
        # 5. 共识分析（记录对话历史并分析）
        self.conversation_history.append({"user": text, "ai": final_response})
        consensus_result = await self._analyze_consensus(text, final_response)
        
        # 更新共识集
        for consensus in consensus_result.get("confirmed", []):
            if consensus not in self.confirmed_consensus:
                self.confirmed_consensus.append(consensus)
        
        # 移除已确认的共识（如果有的话）
        for consensus in consensus_result.get("confirmed", []):
            if consensus in self.pending_consensus:
                self.pending_consensus.remove(consensus)
        
        # 添加新的待确认共识
        for new_pending in consensus_result.get("new_pending", []):
            if new_pending not in self.pending_consensus:
                self.pending_consensus.append(new_pending)
        
        return {
            "chunks_count": len(chunks),
            "insights": self.insight_notes,
            "selected_point": selected_point,
            "response": final_response,
            "consensus_result": consensus_result,
            "confirmed_consensus": self.confirmed_consensus,
            "pending_consensus": self.pending_consensus
        }
