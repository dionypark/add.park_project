"""Streamlit 채팅 UI — FastAPI(/query)를 호출한다. 세션 동안 대화방 번호를 유지해 대화를 이어간다.

실행 전에 FastAPI 서버가 먼저 떠있어야 한다: uvicorn app:app --reload
실행: streamlit run streamlit_app.py
"""
import os

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Multi-Agent RAG", page_icon="🧭")
st.title("Multi-Agent RAG — AWS 어드바이저")
st.caption("최종 포폴 · 멀티 에이전트(supervisor + retrieval + cost) + 멀티턴")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

with st.sidebar:
    st.caption(f"대화방 번호: {st.session_state.thread_id or '(아직 없음, 첫 질문 후 생성됨)'}")
    if st.button("새 대화 시작"):
        st.session_state.messages = []
        st.session_state.thread_id = None
        st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

question = st.chat_input("예: Lambda로 월 100만 건 요청, 200ms, 512MB면 요금이 얼마나 나와?")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("에이전트들이 판단 중..."):
            try:
                payload = {"question": question}
                if st.session_state.thread_id:
                    payload["thread_id"] = st.session_state.thread_id
                res = requests.post(f"{API_URL}/query", json=payload, timeout=90)
                res.raise_for_status()
                data = res.json()
                answer = data["answer"]
                st.session_state.thread_id = data["thread_id"]
                st.write(answer)
                used = []
                if data.get("needs_search"):
                    used.append("검색")
                if data.get("needs_calculation"):
                    used.append("계산")
                if used:
                    st.caption("사용된 에이전트: " + " + ".join(used))
            except requests.exceptions.RequestException as e:
                answer = f"오류: FastAPI 서버({API_URL})에 연결할 수 없습니다. uvicorn이 켜져 있는지 확인하세요. ({e})"
                st.error(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
