"""Streamlit 채팅 UI — FastAPI(/query/stream)를 호출해 토큰 단위로 스트리밍 표시한다.
로그인 기반 멀티턴: 로그인하면 세션 토큰을 브라우저 쿠키에 저장해서, 새로고침/재접속해도
로그인이 유지되고 내 대화 목록(서랍)도 계정 기준으로 그대로 이어진다.

실행 전에 FastAPI 서버가 먼저 떠있어야 한다: uvicorn app:app --reload
실행: streamlit run streamlit_app.py
"""
import base64
import json
import os
import time
from datetime import datetime, timedelta

import extra_streamlit_components as stx
import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")
_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "logo.png")
_COOKIE_NAME = "ganeum_token"

st.set_page_config(page_title="가늠 — AWS 어드바이저", page_icon="☁️")

with open(_LOGO_PATH, "rb") as f:
    _logo_b64 = base64.b64encode(f.read()).decode()

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600&family=Jua&display=swap');
    html, body, [class*="css"] { font-family: 'Poppins', sans-serif; }

    /* 배경: 하늘색 그라데이션 + 은은한 구름 모양 (banapresso 참고 - 밝고 화사한 톤) */
    .stApp {
        background: linear-gradient(180deg, #CFE9F7 0%, #EAF5FB 45%, #FBFDFE 100%);
    }
    .ganeum-cloud {
        position: fixed; pointer-events: none; z-index: 0;
        background: #ffffff; border-radius: 50%; opacity: 0.55;
        filter: blur(1px);
    }

    .ganeum-header { display: flex; justify-content: center; margin: 4px 0 -10px; position: relative; z-index: 1; }
    .ganeum-header img { width: 240px; max-width: 70%; height: auto; }

    /* 모바일(좁은 화면)에서 로고/구름/여백을 줄여서 화면을 덜 차지하게 함 */
    @media (max-width: 480px) {
        .ganeum-header img { width: 170px; }
        .ganeum-cloud { transform: scale(0.6); }
        div[data-testid="stChatMessage"] { font-size: 15px; }
    }
    </style>

    <div class="ganeum-cloud" style="width:140px; height:70px; top:60px; left:5%;"></div>
    <div class="ganeum-cloud" style="width:100px; height:50px; top:180px; right:8%;"></div>
    <div class="ganeum-cloud" style="width:80px; height:40px; top:340px; left:12%;"></div>
    """,
    unsafe_allow_html=True,
)
# 로고 PNG(투명 배경) 안에 "가늠"/"Ganeum" 워드마크가 이미 들어있어서 텍스트를 따로 안 붙인다.
st.markdown(
    f'<div class="ganeum-header"><img src="data:image/png;base64,{_logo_b64}" alt="가늠 로고"/></div>',
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align:center; color:#5B7089; font-size:15px; margin-top:4px; position:relative; z-index:1;'>"
    "AWS, 얼마나 필요한지 가늠해드립니다 · 멀티 에이전트(supervisor + retrieval + cost) + 멀티턴</p>",
    unsafe_allow_html=True,
)


# CookieManager 생성자가 내부적으로 쿠키를 읽어오는 위젯 호출을 하기 때문에, st.cache_resource로
# 감싸면 "cached function 안에서 위젯 호출" 경고와 함께 죽는다. 대신 고정된 key로 매 rerun마다
# 새로 만든다 - key가 같으면 Streamlit이 같은 컴포넌트 인스턴스로 취급해서 문제 없다.
cookie_manager = stx.CookieManager(key="ganeum_cookie_manager")


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"}


def _login_or_signup_view():
    st.markdown(
        "<p style='text-align:center; color:#5B7089; position:relative; z-index:1;'>"
        "로그인하면 어느 기기에서 접속하든 내 대화 목록이 그대로 이어져요.</p>",
        unsafe_allow_html=True,
    )
    tab_login, tab_signup = st.tabs(["로그인", "회원가입"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("아이디", key="login_username")
            password = st.text_input("비밀번호", type="password", key="login_password")
            submitted = st.form_submit_button("로그인", use_container_width=True)
        if submitted:
            try:
                res = requests.post(
                    f"{API_URL}/auth/login", json={"username": username, "password": password}, timeout=10
                )
                if res.status_code == 200:
                    _set_session(res.json())
                    st.rerun()
                else:
                    st.error(res.json().get("detail", "로그인에 실패했습니다."))
            except requests.exceptions.RequestException as e:
                st.error(f"서버에 연결할 수 없습니다: {e}")

    with tab_signup:
        with st.form("signup_form"):
            username = st.text_input("아이디", key="signup_username")
            password = st.text_input("비밀번호", type="password", key="signup_password")
            submitted = st.form_submit_button("회원가입 후 바로 시작", use_container_width=True)
        if submitted:
            try:
                res = requests.post(
                    f"{API_URL}/auth/signup", json={"username": username, "password": password}, timeout=10
                )
                if res.status_code == 200:
                    _set_session(res.json())
                    st.rerun()
                else:
                    st.error(res.json().get("detail", "회원가입에 실패했습니다."))
            except requests.exceptions.RequestException as e:
                st.error(f"서버에 연결할 수 없습니다: {e}")


def _set_session(auth_response: dict):
    st.session_state.token = auth_response["token"]
    st.session_state.username = auth_response["username"]
    cookie_manager.set(
        _COOKIE_NAME,
        auth_response["token"],
        expires_at=datetime.now() + timedelta(days=30),
        key="set_token_cookie",
    )
    # cookie_manager.set()은 브라우저 쪽 컴포넌트(iframe)가 document.cookie를 실제로
    # 써주는 왕복이 끝나야 반영되는데, 그 직후 바로 st.rerun()을 부르면 그 왕복이 끝나기 전에
    # 화면이 다시 그려져서 쿠키가 안 써진 것처럼 보인다(경쟁 조건). 아주 짧게 기다려서
    # 브라우저가 쿠키를 실제로 쓸 시간을 준다.
    time.sleep(0.5)


# 쿠키에서 토큰을 읽어와 로그인 상태를 복원한다 (새로고침/재접속해도 유지되는 부분).
# CookieManager 생성자가 만들어질 때 이미 한 번 쿠키를 읽어와 self.cookies에 들고 있어서,
# 여기서 또 get_all()로 새 컴포넌트 호출을 만들지 않고 그 결과(.get())를 그대로 재사용한다 -
# 한 번의 rerun 안에서 쿠키 컴포넌트를 여러 번 호출하면 응답이 꼬여서 화면 전환이 느려짐.
if "token" not in st.session_state:
    token_from_cookie = cookie_manager.get(_COOKIE_NAME)
    if token_from_cookie:
        try:
            res = requests.get(f"{API_URL}/auth/me", headers={"Authorization": f"Bearer {token_from_cookie}"}, timeout=10)
            if res.status_code == 200:
                st.session_state.token = token_from_cookie
                st.session_state.username = res.json()["username"]
        except requests.exceptions.RequestException:
            pass

if "token" not in st.session_state:
    _login_or_signup_view()
    st.stop()


if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None


def _fetch_my_threads() -> list[dict]:
    try:
        res = requests.get(f"{API_URL}/my-threads", headers=_auth_headers(), timeout=10)
        return res.json() if res.status_code == 200 else []
    except requests.exceptions.RequestException:
        return []


with st.sidebar:
    st.caption(f"👤 {st.session_state.username}")
    if st.button("로그아웃", use_container_width=True):
        try:
            requests.post(f"{API_URL}/auth/logout", headers=_auth_headers(), timeout=10)
        except requests.exceptions.RequestException:
            pass
        cookie_manager.delete(_COOKIE_NAME, key="delete_token_cookie")
        time.sleep(0.5)  # set()과 동일한 이유 - 브라우저가 쿠키를 지울 시간을 준다.
        for key in ("token", "username", "messages", "thread_id"):
            st.session_state.pop(key, None)
        st.rerun()

    st.divider()
    st.caption(f"대화방 번호: {st.session_state.thread_id or '(아직 없음, 첫 질문 후 생성됨)'}")
    if st.button("새 대화 시작", use_container_width=True):
        st.session_state.messages = []
        st.session_state.thread_id = None
        st.rerun()

    st.divider()
    st.caption("지난 대화")
    my_threads = _fetch_my_threads()
    if not my_threads:
        st.caption("_아직 지난 대화가 없어요._")
    for t in my_threads:
        is_current = t["thread_id"] == st.session_state.thread_id
        label = ("📍 " if is_current else "") + t["preview"]
        if st.button(label, key=f"thread-{t['thread_id']}", use_container_width=True):
            try:
                history = requests.get(
                    f"{API_URL}/threads/{t['thread_id']}", headers=_auth_headers(), timeout=10
                ).json()
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

            with requests.post(
                f"{API_URL}/query/stream", json=payload, headers=_auth_headers(), stream=True, timeout=300
            ) as res:
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
