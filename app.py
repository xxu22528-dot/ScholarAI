import streamlit as st
import os
import json
import asyncio
from agent import ResearchAgent
from meeting import MeetingController
from focus_mode import FocusSession
from utils.file_utils import extract_text_from_pdf, encode_image_to_base64
from utils.db_utils import create_session, get_all_sessions, get_session_info, add_message, get_messages, delete_session

# --- 1. 页面配置 ---
st.set_page_config(page_title="ScholarAI - 科研智囊团", page_icon="🎓", layout="wide")

# ==========================================
# Session State 初始化
# ==========================================
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
if "agent" not in st.session_state:
    st.session_state.agent = None
if "meeting_controller" not in st.session_state:
    st.session_state.meeting_controller = None

# --- 2. 侧边栏：全局配置与会话管理 ---
with st.sidebar:
    st.header("⚙️ 配置中心")
    api_key = st.text_input("API Key", type="password", help="请输入阿里云 DashScope / OpenAI / DeepSeek Key")
    
    # 默认选中 Qwen
    model_provider = st.selectbox("选择模型服务商", ["Qwen", "OpenAI", "DeepSeek", "Kimi (Moonshot)"])
    
    if model_provider == "Qwen":
        default_model = "qwen-plus"
    elif model_provider == "OpenAI":
        default_model = "gpt-4o"
    elif model_provider == "DeepSeek":
        default_model = "deepseek-chat"
    else:
        default_model = "moonshot-v1-8k"
        
    model_name = st.text_input("模型名称", value=default_model)
    
    base_url_map = {
        "OpenAI": None, 
        "DeepSeek": "https://api.deepseek.com",
        "Kimi (Moonshot)": "https://api.moonshot.cn/v1",
        "Qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1"
    }
    base_url = base_url_map[model_provider]

    st.divider()
    
    # === 会话列表管理 ===
    st.subheader("🗂️ 会话历史")
    
    # 新建会话按钮
    if st.button("➕ 新建会话", use_container_width=True):
        st.session_state.current_session_id = None
        st.session_state.agent = None
        st.session_state.meeting_controller = None
        st.rerun()

    # 显示历史会话
    sessions = get_all_sessions()
    if sessions:
        for s in sessions:
            col1, col2 = st.columns([4, 1])
            with col1:
                # 选中会话
                if st.button(f"{'👥' if s['session_type']=='meeting' else '🤖'} {s['title']}", key=s['session_id'], use_container_width=True):
                    st.session_state.current_session_id = s['session_id']
                    st.session_state.agent = None
                    st.session_state.meeting_controller = None
                    st.rerun()
            with col2:
                # 删除会话
                if st.button("🗑️", key=f"del_{s['session_id']}"):
                    delete_session(s['session_id'])
                    if st.session_state.get('current_session_id') == s['session_id']:
                        st.session_state.current_session_id = None
                        st.session_state.agent = None
                        st.session_state.meeting_controller = None
                    st.rerun()
    else:
        st.caption("暂无历史记录")

if not api_key:
    st.warning("👈 请先在左侧输入 API Key 启动系统")
    st.stop()

# ==========================================
# 视图 A: 创建新会话
# ==========================================
def render_create_view():
    st.title("✨ 创建新研讨")
    
    mode = st.radio("选择模式", ["🤖 单模型精读", "👥 组会研讨模式", "🎯 聚焦式对话模式"], horizontal=True)
    
    if mode == "🤖 单模型精读":
        title_placeholder = "输入论文标题或研究方向..."
    elif mode == "👥 组会研讨模式":
        title_placeholder = "输入会议议题..."
    else:
        title_placeholder = "输入长篇汇报主题..."

    title = st.text_input("会话标题", placeholder=title_placeholder)
    
    # --- 组会模式下的专家配置 ---
    agents_config = []
    if mode == "👥 组会研讨模式":
        st.divider()
        st.subheader("配置参会专家")
        st.caption("请定义 2-4 位不同观点的专家")
        
        c1, c2 = st.columns(2)
        with c1:
            name1 = st.text_input("专家1 名字", value="AI信仰者")
            desc1 = st.text_area("专家1 人设", value="激进的AI信仰者，认为AGI即将到来", height=70)
        with c2:
            name2 = st.text_input("专家2 名字", value="认知科学家")
            desc2 = st.text_area("专家2 人设", value="保守的实证主义者，注重实验数据", height=70)
            
        c3, c4 = st.columns(2)
        with c3:
            name3 = st.text_input("专家3 名字 (选填)", value="伦理学家")
            desc3 = st.text_area("专家3 人设 (选填)", value="关注AI对社会就业和伦理的影响", height=70)
        with c4:
            name4 = st.text_input("专家4 名字 (选填)")
            desc4 = st.text_area("专家4 人设 (选填)", height=70)

        if name1 and desc1: agents_config.append({"name": name1, "prompt": desc1})
        if name2 and desc2: agents_config.append({"name": name2, "prompt": desc2})
        if name3 and desc3: agents_config.append({"name": name3, "prompt": desc3})
        if name4 and desc4: agents_config.append({"name": name4, "prompt": desc4})

    # --- 开始按钮 ---
    if st.button("立即开始", type="primary"):
        if not title:
            st.error("请输入标题")
            return
        
        if mode == "👥 组会研讨模式" and len(agents_config) < 2:
            st.error("组会模式至少需要 2 位专家")
            return
            
        if mode == "🤖 单模型精读":
            session_type = "chat"
        elif mode == "👥 组会研讨模式":
            session_type = "meeting"
        else:
            session_type = "focus"

        new_id = create_session(title, session_type)
        
        if mode == "👥 组会研讨模式":
            config_json = json.dumps(agents_config, ensure_ascii=False)
            add_message(new_id, "system_agents_config", config_json)
        
        st.session_state.current_session_id = new_id
        st.rerun()

# ==========================================
# 视图 B: 单模型精读界面
# ==========================================
def render_chat_view(session_id, title):
    st.title(f"🤖 {title}")
    
    with st.sidebar:
        st.divider()
        st.markdown("### 📎 文件上传")
        uploaded_file = st.file_uploader("上传", type=["pdf", "png", "jpg"], label_visibility="collapsed")
        
        pdf_content = None
        image_base64 = None
        if uploaded_file:
            if "pdf" in uploaded_file.type:
                with st.spinner("提取文本..."):
                    pdf_content = extract_text_from_pdf(uploaded_file)
                    st.success("PDF 已就绪")
            elif "image" in uploaded_file.type:
                st.image(uploaded_file, caption="预览")
                image_base64 = encode_image_to_base64(uploaded_file)

    if st.session_state.agent is None:
        agent = ResearchAgent(
            name="科研助理",
            system_prompt="你是一个专业的科研助手。",
            model=model_name,
            api_key=api_key,
            base_url=base_url
        )
        db_history = get_messages(session_id)
        if db_history:
            for msg in db_history:
                agent.history.append({"role": msg["role"], "content": msg["content"]})
        
        st.session_state.agent = agent

    agent = st.session_state.agent

    for msg in agent.history[1:]:
        with st.chat_message(msg["role"]):
            if isinstance(msg["content"], list):
                for item in msg["content"]:
                    if item["type"] == "text":
                        st.write(item["text"])
            else:
                st.write(msg["content"])

    if user_input := st.chat_input("输入你的问题..."):
        with st.chat_message("user"):
            st.write(user_input)
        add_message(session_id, "user", user_input)
        
        final_prompt = user_input
        if pdf_content:
            final_prompt = f"【背景资料】\n{pdf_content}\n\n【问题】{user_input}"
        
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                response = agent.chat(final_prompt, image_base64)
                st.write(response)
        add_message(session_id, "assistant", response)

    st.divider()
    
    with st.expander("📝 导出对话纪要", expanded=False):
        if st.button("生成总结报告"):
            if len(agent.history) <= 1:
                st.warning("暂无讨论记录")
            else:
                with st.spinner("✍️ 正在整理对话记录，生成纪要..."):
                    history_lines = []
                    for m in agent.history:
                        role = m["role"]
                        content = m["content"]
                        text_content = ""
                        if isinstance(content, list):
                            for item in content:
                                if item["type"] == "text":
                                    text_content += item["text"]
                                elif item["type"] == "image_url":
                                    text_content += "[图片]"
                        else:
                            text_content = str(content)
                        history_lines.append(f"{role}: {text_content}")
                    
                    full_context = "\n".join(history_lines)
                    report = agent.summarize(full_context)
                    
                    st.markdown("### 📝 对话纪要")
                    st.markdown(report)
                    
                    st.download_button(
                        label="📥 下载 Markdown 文件",
                        data=report,
                        file_name=f"{title}_report.md",
                        mime="text/markdown"
                    )

# ==========================================
# 视图 C: 聚焦式对话模式 (Focus Mode)
# ==========================================
def render_focus_view(session_id, title):
    st.title(f"🎯 {title}")
    
    # 初始化 Session State
    if "focus_session" not in st.session_state:
        st.session_state.focus_session = FocusSession(api_key=api_key, base_url=base_url, model=model_name)
    
    focus_agent = st.session_state.focus_session
    
    # 显示历史记录
    history = get_messages(session_id)
    for msg in history:
        with st.chat_message(msg["role"]):
            # 如果是 insights 类型的特殊消息，我们渲染成 expander
            if msg["role"] == "system_insights":
                try:
                    insights = json.loads(msg["content"])
                    with st.expander("🧠 后台思维发散记录", expanded=False):
                        for note in insights:
                            st.markdown(f"**片段 {note.get('id', '?')}**: {note.get('chunk', '')[:50]}...")
                            st.caption(f"💡 {note.get('note', '')}")
                except:
                    pass
            else:
                st.write(msg["content"])

    # 输入区域
    # 为了支持长文本，我们使用 chat_input，但提示用户可以粘贴长文
    if user_input := st.chat_input("在此粘贴长篇汇报内容..."):
        # 1. 用户消息上屏
        with st.chat_message("user"):
            st.write(user_input)
        add_message(session_id, "user", user_input)
        
        # 2. 处理流程
        with st.chat_message("assistant"):
            status_placeholder = st.empty()
            
            # 定义回调函数来更新 UI
            def update_progress(insights):
                with status_placeholder.container():
                    with st.expander("🧠 正在进行后台全量思维发散...", expanded=True):
                        for note in insights:
                            st.markdown(f"**Thinking on Chunk {note['id']}**: {note['note']}")
            
            with st.spinner("👂 正在监听并拆解语义块..."):
                # 运行异步任务
                # 注意：Streamlit 中运行 asyncio.run 可能有 event loop 问题
                # 简单的处理方式是创建一个新的 loop 或者使用 asyncio.run (如果当前不在 loop 中)
                try:
                    result = asyncio.run(focus_agent.process_full_input(user_input, progress_callback=update_progress))
                except RuntimeError:
                    # 如果已经在 loop 中 (比如某些 streamlit 部署环境)，则使用 create_task 或 await
                    # 但在这里 standard streamlit run 是同步的，可以直接 run
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(focus_agent.process_full_input(user_input, progress_callback=update_progress))
                    loop.close()

            # 3. 结果展示
            # A. 展示 Insights
            insights = result["insights"]
            with st.expander("🧠 思维发散完成 (点击查看所有后台笔记)", expanded=False):
                for note in insights:
                    st.markdown(f"**片段 {note['id']}**: {note['chunk'][:50]}...")
                    st.info(f"💡 {note['note']}")
            
            # 保存 insights 到历史 (作为特殊系统消息，方便回看)
            add_message(session_id, "system_insights", json.dumps(insights, ensure_ascii=False))

            # B. 展示 Selected Point
            st.markdown(f"### 🎯 聚焦切入点")
            st.markdown(f"> {result['selected_point']}")
            
            # C. 展示最终回复
            st.markdown("### 💬 回应")
            st.write(result["response"])
            
            # 保存回复
            add_message(session_id, "assistant", result["response"])

# ==========================================
# 视图 D: 组会模式界面 (支持用户插嘴)
# ==========================================
def render_meeting_view(session_id, title):
    st.title(f"👥 {title}")
    
    if st.session_state.meeting_controller is None:
        mc = MeetingController(api_key=api_key, base_url=base_url, model=model_name)
        mc.topic = title
        
        db_messages = get_messages(session_id)
        agents_loaded = False
        
        for msg in db_messages:
            if msg["role"] == "system_agents_config":
                try:
                    config = json.loads(msg["content"])
                    for agent_conf in config:
                        mc.add_agent(ResearchAgent(
                            name=agent_conf["name"], 
                            system_prompt=agent_conf["prompt"], 
                            model=model_name, 
                            api_key=api_key, 
                            base_url=base_url
                        ))
                    agents_loaded = True
                    break
                except:
                    pass
        
        if not agents_loaded:
            mc.add_agent(ResearchAgent(name="AI信仰者", system_prompt="激进的AI信仰者", model=model_name, api_key=api_key, base_url=base_url))
            mc.add_agent(ResearchAgent(name="认知科学家", system_prompt="保守的实证主义者", model=model_name, api_key=api_key, base_url=base_url))
            mc.add_agent(ResearchAgent(name="伦理学家", system_prompt="关注社会影响", model=model_name, api_key=api_key, base_url=base_url))

        for msg in db_messages:
            if msg["role"] != "system_agents_config":
                mc.history.append(msg)
                
        if not mc.history:
            welcome = f"大家好，今天的议题是：{title}。"
            mc.history.append({"role": "user", "content": welcome})

        st.session_state.meeting_controller = mc

    mc = st.session_state.meeting_controller

    # 1. 显示历史记录
    for msg in mc.history:
        if msg["role"] != "system": 
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

    # 2. 控制区：按钮与导出
    # 我们把“下一位发言”和“导出”放在输入框上方，避免布局冲突
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🗣️ 让下一位专家发言", type="primary", use_container_width=True):
            with st.spinner("主持人正在点名..."):
                msg = mc.step()
                add_message(session_id, msg["role"], msg["content"])
                st.rerun()
    
    with col2:
        # 简化版导出：直接生成，不再折叠，方便随时看
        if st.button("📝 生成/更新 会议纪要", use_container_width=True):
            if not mc.history:
                st.warning("暂无记录")
            else:
                with st.spinner("正在生成报告..."):
                    full_context = "\n".join([f"{m['role']}: {m['content']}" for m in mc.history])
                    editor = ResearchAgent("编辑", "编辑", model_name, api_key, base_url)
                    report = editor.summarize(full_context)
                    # 存入 Session State 防止刷新消失
                    st.session_state.last_report = report
                    st.rerun()

    # 显示生成的报告（如果有）
    if "last_report" in st.session_state and st.session_state.last_report:
        with st.expander("📄 当前会议纪要 (点击展开)", expanded=True):
            st.markdown(st.session_state.last_report)
            st.download_button("📥 下载报告", st.session_state.last_report, f"{title}_report.md")

    # 3. 用户插嘴区 (这是关键改动！)
    # st.chat_input 始终固定在页面最底部
    if user_input := st.chat_input("在此输入你的观点，或向专家提问..."):
        # 用户发言直接上屏
        add_message(session_id, "user", user_input)
        mc.history.append({"role": "user", "content": user_input})
        st.rerun()

# --- 4. 主路由逻辑 ---
if st.session_state.current_session_id is None:
    render_create_view()
else:
    session_info = get_session_info(st.session_state.current_session_id)
    if session_info:
        if session_info["session_type"] == "chat":
            render_chat_view(session_info["session_id"], session_info["title"])
        elif session_info["session_type"] == "focus":
            render_focus_view(session_info["session_id"], session_info["title"])
        else:
            render_meeting_view(session_info["session_id"], session_info["title"])
    else:
        st.error("会话不存在，请刷新页面")
        st.session_state.current_session_id = None