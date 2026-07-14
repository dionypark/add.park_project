"""Streamlit 채팅 UI — FastAPI(/query)를 호출한다. 세션 동안 대화방 번호를 유지해 대화를 이어간다.

실행 전에 FastAPI 서버가 먼저 떠있어야 한다: uvicorn app:app --reload
실행: streamlit run streamlit_app.py
"""
import os

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

USER_AVATAR = "🧑‍🔬"
BOT_AVATAR = "🦖"

st.set_page_config(page_title="AWS 쥬라기 어드바이저", page_icon="🦕")
st.title("🦕 AWS 서비스 선택 / 비용 최적화 어드바이저 🌿")
st.caption("8주차 · ranggraph (LangGraph ReAct 에이전트, 멀티턴 대화 지원)")
st.markdown("🦴 🌴 🥚 🦖 🌋 🦕 🌿 🦴 🌴 🥚 🦖 🌋 🦕 🌿")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

with st.sidebar:
    st.markdown("### 🦖 대화방 정보")
    st.caption(f"대화방 번호: {st.session_state.thread_id or '(아직 없음, 첫 질문 후 생성됨)'}")
    if st.button("🥚 새 대화 시작"):
        st.session_state.messages = []
        st.session_state.thread_id = None
        st.rerun()

for msg in st.session_state.messages:
    avatar = USER_AVATAR if msg["role"] == "user" else BOT_AVATAR
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])

question = st.chat_input("예: 트래픽 적은 개인 프로젝트인데 뭐 써야해?")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.write(question)

    with st.chat_message("assistant", avatar=BOT_AVATAR):
        with st.spinner("🦖 화석 문서를 뒤지는 중... (필요하면 검색합니다)"):
            try:
                payload = {"question": question}
                if st.session_state.thread_id:
                    payload["thread_id"] = st.session_state.thread_id
                res = requests.post(f"{API_URL}/query", json=payload, timeout=60)
                res.raise_for_status()
                data = res.json()
                answer = data["answer"]
                st.session_state.thread_id = data["thread_id"]
                st.write(answer)
            except requests.exceptions.RequestException as e:
                answer = f"오류: FastAPI 서버({API_URL})에 연결할 수 없습니다. uvicorn이 켜져 있는지 확인하세요. ({e})"
                st.error(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
