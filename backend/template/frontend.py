"""
Google ADK Streamlit Web Interface
"""

import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Google ADK Multi-Agent Studio",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    from agent import get_root_agent
    ORCHESTRATOR = get_root_agent()
    INITIALIZED = True
except Exception as e:
    ORCHESTRATOR = None
    INITIALIZED = False
    INIT_ERROR = str(e)

with st.sidebar:
    st.title("ADK Controls")
    api_key = st.text_input("Google API Key", value=os.environ.get("GOOGLE_API_KEY", ""), type="password")
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key

    st.divider()
    st.subheader("Registered Sub-Agents")
    if INITIALIZED and ORCHESTRATOR:
        for ag in ORCHESTRATOR.list_agents():
            with st.expander(f"🔹 {ag['name']}"):
                st.caption(f"**ID:** `{ag['id']}`")
                st.caption(f"**Role:** {ag['role']}")
                st.caption(f"**Tools:** `{', '.join(ag['tools'])}`")

st.title("Google ADK Multi-Agent Studio")

tab1, tab2, tab3 = st.tabs(["💬 Orchestrator Chat", "⚡ Multi-Agent Pipeline", "🧪 Sub-Agent Playground"])

with tab1:
    st.subheader("Chat with Root Orchestrator")
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Hello! I am the Root Orchestrator."}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Ask a question, request code, calculate data, or draft a report...")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            if INITIALIZED and ORCHESTRATOR:
                res = ORCHESTRATOR.chat(user_input, auto_route=True)
                reply = res.get("result", {}).get("response", str(res))
            else:
                reply = f"[Simulated Response] Processed '{user_input}'"
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})