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
# 원본 logo.png는 아이콘+"가늠"+"Ganeum" 글자가 세로로 쌓여있는 이미지라, 헤더에 그대로 쓰면
# 세로로 길게 늘어진다. logo-icon.png는 그중 아이콘 부분만 잘라둔 것 - 이걸 텍스트 "가늠"과
# 나란히(가로) 배치해서 헤더를 컴팩트하게 만든다.
_LOGO_ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "logo-icon.png")
_COOKIE_NAME = "ganeum_token"

st.set_page_config(page_title="가늠 — AWS 어드바이저", page_icon="☁️")

with open(_LOGO_ICON_PATH, "rb") as f:
    _logo_icon_b64 = base64.b64encode(f.read()).decode()

st.markdown(
    """
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
    @import url('https://fonts.googleapis.com/css2?family=Jua&display=swap');
    /* Streamlit 내부 아이콘은 전용 아이콘 폰트(리게이처 텍스트)를 쓰는데, 이걸 무시하고 전역
       폰트를 강제하면 아이콘이 "keyboard_double_arrow_right" 같은 글자 그대로 깨져 보인다.
       그래서 span/div는 건드리지 않고, 실제 텍스트 요소만 지정한다.
       본문은 Pretendard(가독성), 로고 옆 태그라인/타이틀류는 Jua(동글동글한 느낌)로 구분. */
    html, body, .stMarkdown, p, h1, h2, h3, label, textarea, input, button {
        font-family: 'Pretendard', -apple-system, sans-serif;
    }
    .ganeum-tagline, .ganeum-round {
        font-family: 'Jua', sans-serif !important;
    }

    /* 배경: 하늘색 -> 연초록으로 은은하게 넘어가는 그라데이션 + 구름 모양 */
    .stApp {
        background: linear-gradient(160deg, #CFE9F7 0%, #DCF2E8 50%, #FBFDFE 100%);
    }

    @keyframes ganeum-float {
        0%, 100% { transform: translateY(0) scale(1); }
        50% { transform: translateY(-6px) scale(1.15); }
    }
    .ganeum-loading {
        display: inline-flex; align-items: center; gap: 8px; color: #5B7089;
    }
    .ganeum-loading .cloud { display: inline-block; font-size: 20px; animation: ganeum-float 1.1s ease-in-out infinite; }
    .ganeum-cloud {
        position: fixed; pointer-events: none; z-index: 0;
        background: #ffffff; border-radius: 50%; opacity: 0.5;
        filter: blur(2px);
    }

    .ganeum-header {
        display: flex; align-items: center; justify-content: center; gap: 14px;
        margin: 20px 0 4px; position: relative; z-index: 1;
    }
    .ganeum-header img { width: 74px; height: auto;
        filter: drop-shadow(0 4px 10px rgba(63,82,102,0.18)); }
    .ganeum-header .ganeum-name {
        font-family: 'Jua', sans-serif; font-size: 44px; color: #3F5266; line-height: 1;
    }

    .ganeum-tagline {
        text-align: center; color: #5B7089; font-size: 15px; margin: 6px 0 28px;
        position: relative; z-index: 1; line-height: 1.6; font-weight: 500;
    }

    /* 로그인 후(채팅) 화면에서 오른쪽 위에 작게 붙는 로고 - 큰 헤더/태그라인 대신 이것만 씀 */
    .ganeum-header-mini {
        display: flex; align-items: center; justify-content: flex-end; gap: 6px;
        margin: -8px 0 12px; position: relative; z-index: 1;
    }
    .ganeum-header-mini img { width: 30px; height: auto; }
    .ganeum-header-mini span {
        font-family: 'Jua', sans-serif; font-size: 17px; color: #3F5266;
    }

    /* 채팅 말풍선 - 기본 Streamlit 스타일을 카드형으로 부드럽게 */
    div[data-testid="stChatMessage"] {
        background: rgba(255, 255, 255, 0.72);
        border-radius: 18px;
        padding: 4px 6px;
        margin-bottom: 10px;
        box-shadow: 0 2px 10px rgba(63, 82, 102, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.6);
    }

    /* 버튼 - 둥글고 부드러운 톤 */
    .stButton > button {
        border-radius: 12px !important;
        border: 1px solid rgba(91, 112, 137, 0.18) !important;
        transition: all 0.15s ease;
    }
    .stButton > button:hover {
        border-color: #5B7089 !important;
        box-shadow: 0 3px 10px rgba(63, 82, 102, 0.15);
        transform: translateY(-1px);
    }

    /* 채팅 입력창 */
    div[data-testid="stChatInput"] {
        border-radius: 16px;
    }

    /* 사이드바 배경도 톤 맞추기 */
    section[data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.55);
    }

    /* 모바일(좁은 화면)에서 로고/구름/여백을 줄여서 화면을 덜 차지하게 함 */
    @media (max-width: 480px) {
        .ganeum-header img { width: 52px; }
        .ganeum-header .ganeum-name { font-size: 32px; }
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
def _render_full_header():
    """로그인 전 화면에서만 쓰는 큰 헤더(아이콘+이름+태그라인)."""
    st.markdown(
        f'<div class="ganeum-header">'
        f'<img src="data:image/png;base64,{_logo_icon_b64}" alt="가늠 로고"/>'
        f'<span class="ganeum-name">가늠</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p class='ganeum-tagline'>AWS, 얼마나 필요한지 가늠해드립니다<br>"
        "무엇을 써야 할지, 어떤 게 더 나을지 비교하고 — 예상 비용까지 함께 가늠해드려요</p>",
        unsafe_allow_html=True,
    )


def _render_mini_header():
    """로그인 후(채팅) 화면에서 쓰는, 오른쪽 위에 작게 붙는 로고."""
    st.markdown(
        f'<div class="ganeum-header-mini">'
        f'<img src="data:image/png;base64,{_logo_icon_b64}" alt="가늠 로고"/>'
        f'<span>가늠</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# CookieManager 생성자가 내부적으로 쿠키를 읽어오는 위젯 호출을 하기 때문에, st.cache_resource로
# 감싸면 "cached function 안에서 위젯 호출" 경고와 함께 죽는다. 대신 고정된 key로 매 rerun마다
# 새로 만든다 - key가 같으면 Streamlit이 같은 컴포넌트 인스턴스로 취급해서 문제 없다.
cookie_manager = stx.CookieManager(key="ganeum_cookie_manager")


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"}


def _login_or_signup_view():
    _render_full_header()
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

_render_mini_header()

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

    if st.button("＋ 새 대화 시작", use_container_width=True):
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
        col_open, col_del = st.columns([0.82, 0.18])
        with col_open:
            if st.button(label, key=f"thread-{t['thread_id']}", use_container_width=True):
                try:
                    res = requests.get(
                        f"{API_URL}/threads/{t['thread_id']}", headers=_auth_headers(), timeout=10
                    )
                    if res.status_code != 200:
                        # 응답이 200이 아니면 {"thread_id": ...} 모양이 아니라 {"detail": "..."} 형태라
                        # 아래에서 바로 history["thread_id"]를 쓰면 KeyError가 나서 화면이 죽는다.
                        # 여기서 먼저 걸러서 사용자한테 보이는 에러 메시지로만 처리한다.
                        detail = res.json().get("detail", f"HTTP {res.status_code}") if res.content else f"HTTP {res.status_code}"
                        st.error(f"대화를 불러오지 못했습니다: {detail}")
                    else:
                        history = res.json()
                        st.session_state.thread_id = history["thread_id"]
                        st.session_state.messages = [
                            {"role": m["role"], "content": m["content"]} for m in history["messages"]
                        ]
                        st.rerun()
                except requests.exceptions.RequestException as e:
                    st.error(f"대화를 불러오지 못했습니다: {e}")
        with col_del:
            if st.button("🗑️", key=f"delete-{t['thread_id']}", use_container_width=True):
                try:
                    requests.delete(f"{API_URL}/threads/{t['thread_id']}", headers=_auth_headers(), timeout=10)
                except requests.exceptions.RequestException:
                    pass
                if is_current:
                    st.session_state.thread_id = None
                    st.session_state.messages = []
                st.rerun()

_AVATARS = {"user": "🙂", "assistant": "☁️"}

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar=_AVATARS.get(msg["role"])):
        st.write(msg["content"])

question = st.chat_input("무엇이 궁금하신가요?")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user", avatar=_AVATARS["user"]):
        st.write(question)

    with st.chat_message("assistant", avatar=_AVATARS["assistant"]):
        placeholder = st.empty()
        placeholder.markdown(
            '<div class="ganeum-loading"><span class="cloud">☁️</span> 가늠하는 중...</div>',
            unsafe_allow_html=True,
        )
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
