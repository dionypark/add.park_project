"""Streamlit 채팅 UI — FastAPI(/query/stream)를 호출해 토큰 단위로 스트리밍 표시한다.
세션 동안 대화방 번호를 유지해 대화를 이어간다.

실행 전에 FastAPI 서버가 먼저 떠있어야 한다: uvicorn app:app --reload
실행: streamlit run streamlit_app.py
"""
import json
import os

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "logo.svg")

st.set_page_config(page_title="가늠 — AWS 어드바이저", page_icon="☁️")

with open(_LOGO_PATH, encoding="utf-8") as f:
    _logo_svg = f.read()

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@700;800&display=swap');
    .ganeum-header { display: flex; align-items: center; gap: 12px; margin-bottom: 4px; }
    .ganeum-header svg { width: 44px; height: 44px; border-radius: 10px; }
    .ganeum-title { font-family: 'Baloo 2', sans-serif; font-weight: 800; font-size: 34px; color: #FF5FA2; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(f'<div class="ganeum-header">{_logo_svg}<span class="ganeum-title">가늠</span></div>', unsafe_allow_html=True)
st.caption("AWS, 얼마나 필요한지 가늠해드립니다 · 멀티 에이전트(supervisor + retrieval + cost) + 멀티턴")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

with st.sidebar:
    st.caption(f"대화방 번호: {st.session_state.thread_id or '(아직 없음, 첫 질문 후 생성됨)'}")
    if st.button("새 대화 시작", use_container_width=True):
        st.session_state.messages = []
        st.session_state.thread_id = None
        st.rerun()

    st.divider()
    st.caption("지난 대화")
    try:
        threads = requests.get(f"{API_URL}/threads", timeout=10).json()
    except requests.exceptions.RequestException:
        threads = []

    if not threads:
        st.caption("_아직 지난 대화가 없어요._")
    for t in threads:
        is_current = t["thread_id"] == st.session_state.thread_id
        label = ("📍 " if is_current else "") + t["preview"]
        if st.button(label, key=f"thread-{t['thread_id']}", use_container_width=True):
            try:
                history = requests.get(f"{API_URL}/threads/{t['thread_id']}", timeout=10).json()
                st.session_state.thread_id = history["thread_id"]
                st.session_state.messages = [
                    {"role": m["role"], "content": m["content"]} for m in history["messages"]
                ]
                st.rerun()
            except requests.exceptions.RequestException as e:
                st.error(f"대화를 불러오지 못했습니다: {e}")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

question = st.chat_input("예: Lambda로 월 100만 건 요청, 200ms, 512MB면 요금이 얼마나 나와?")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("_생각 중..._")
        answer = ""
        needs_search = False
        needs_calculation = False
        try:
            payload = {"question": question}
            if st.session_state.thread_id:
                payload["thread_id"] = st.session_state.thread_id

            with requests.post(f"{API_URL}/query/stream", json=payload, stream=True, timeout=120) as res:
                res.raise_for_status()
                current_event = None
                for line in res.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith("event: "):
                        current_event = line[len("event: "):]
                    elif line.startswith("data: "):
                        data = json.loads(line[len("data: "):])
                        if current_event == "phase":
                            needs_search = data.get("needs_search", False)
                            needs_calculation = data.get("needs_calculation", False)
                        elif current_event == "token":
                            answer += data.get("text", "")
                            placeholder.markdown(answer + "▌")
                        elif current_event == "done":
                            st.session_state.thread_id = data.get("thread_id", st.session_state.thread_id)
                        elif current_event == "error":
                            answer += f"\n\n**오류:** {data.get('message')}"

            placeholder.markdown(answer or "답변을 생성하지 못했습니다.")
            used = []
            if needs_search:
                used.append("검색")
            if needs_calculation:
                used.append("계산")
            if used:
                st.caption("사용된 에이전트: " + " + ".join(used))
        except requests.exceptions.RequestException as e:
            answer = f"오류: FastAPI 서버({API_URL})에 연결할 수 없습니다. uvicorn이 켜져 있는지 확인하세요. ({e})"
            placeholder.error(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
