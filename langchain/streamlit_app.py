"""Streamlit 채팅 UI — FastAPI(/ask)를 호출한다.

실행 전에 FastAPI 서버가 먼저 떠있어야 한다: uvicorn app:app --reload
실행: streamlit run streamlit_app.py
"""
import os

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="AWS 서비스 선택/비용 최적화 어드바이저", page_icon="💬")
st.title("AWS 서비스 선택 / 비용 최적화 어드바이저")
st.caption("7주차 · langchain (LangChain LCEL 체인)")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("sources"):
            st.caption("출처: " + ", ".join(f"{s['source']} ({s['header']})" for s in msg["sources"]))

question = st.chat_input("예: 트래픽 적은 개인 프로젝트인데 뭐 써야해?")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("생각 중..."):
            try:
                res = requests.post(f"{API_URL}/ask", json={"question": question}, timeout=60)
                res.raise_for_status()
                data = res.json()
                answer, sources = data["answer"], data.get("sources", [])
                st.write(answer)
                if sources:
                    st.caption("출처: " + ", ".join(f"{s['source']} ({s['header']})" for s in sources))
            except requests.exceptions.RequestException as e:
                answer, sources = f"오류: FastAPI 서버({API_URL})에 연결할 수 없습니다. uvicorn이 켜져 있는지 확인하세요. ({e})", []
                st.error(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer, "sources": sources})
