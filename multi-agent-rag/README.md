# 최종 포트폴리오 — Multi-Agent RAG

`vanilla-rag` → `langchain` → `langgraph`를 거쳐 완성되는 최종 통합본. **계층형(Hierarchical) 멀티 에이전트** 구조로, `langgraph`(싱글 에이전트)의 다음 단계.
> 실제 구조는 supervisor가 한 번 판단해서 필요한 에이전트로 병렬 분기(fan-out)하고 결과를 합류(fan-in)하는 **계층형 supervisor-worker 패턴**.`multi-agent-rag`.


## 구조

```
State = {messages, needs_search, needs_calculation, search_result, cost_result}

START → supervisor(판단만, LLM) → (조건부 분기, 필요한 쪽만/둘다 병렬)
              ├─ retrieval_agent(서브그래프, search_aws_docs) ──┐
              └─ cost_agent(서브그래프, search_aws_docs+calculate_cost) ──┤
                                                                  ↓
                                                          synthesizer
                                                  (둘 다 실행됐을 때만 LLM으로 합침,
                                                   하나만 실행됐으면 그 결과를 그대로 통과)
                                                          ↓
                                                         END
```

| 구성요소 | 역할 | 도구 |
|---|---|---|
| `supervisor` | 검색/계산 필요 여부만 판단 (일은 안 함) | 없음 |
| `retrieval_agent` | AWS 문서 검색, 자기 안에서 반복 검색 가능 (ReAct) | `search_aws_docs` |
| `cost_agent` | 요금 계산, 필요하면 최신 단가도 검색 (ReAct) | `search_aws_docs`, `calculate_cost` |
| `synthesizer` | 검색+계산 결과를 하나로 합침 (조건부) | 없음 |

## 프로젝트 요구사항

| 요구사항 | 상태 |
|---|---|
| 멀티 에이전트 구조 | ✅ supervisor + retrieval_agent + cost_agent(둘 다 진짜 ReAct 루프를 가진 독립 에이전트) |
| 서브그래프 활용 | ✅ retrieval_agent, cost_agent를 별도 컴파일된 그래프로 만들어 노드 함수 안에서 호출 |
| 병렬 실행 | ✅ 검색+계산 둘 다 필요하면 `add_conditional_edges`가 리스트를 반환해 동시 실행(fan-out), `synthesizer`에서 fan-in |
| FastAPI 배포 | ✅ `app.py` (`/query`, `thread_id`로 멀티턴) |
| 멀티턴 | ✅ `SqliteSaver`/`AsyncSqliteSaver`(영속 저장, 서랍 UI) |
| 스트리밍 | ✅ `/query/stream` (SSE, 최종 답변만 토큰 단위로 흘려보냄) |


## 실행 방법

```bash
cd multi-agent-rag
source .venv/bin/activate
pip install -r requirements.txt    # ijson 추가됨 (EC2 요금표 스트리밍 파싱용)
cp .env.example .env    # ANTHROPIC_API_KEY, LANGSMITH_API_KEY 입력 필요
python build_vectordb.py
python refresh_ec2_prices.py       # EC2 요금 캐시 최초 생성 (선택, 없으면 첫 EC2 계산 때 자동 생성)
uvicorn app:app --reload           # REST API 서버 (터미널 1)
streamlit run streamlit_app.py     # 채팅 UI (터미널 2)
```

## RAG 문서 구성 — 숫자는 API, "언제/왜"는 문서

실시간 요금 API를 붙였다고 RAG(문서 검색)가 필요 없어지는 게 아니라 역할이 다르다: **API는 "얼마"(정량), 문서는
"언제/왜 이걸 골라야 하는지 + 할인 옵션은 어떻게 고르는지"(정성)**. `fetch_docs.py`의 `URLS`에 비용 산정 도메인에
집중한 문서를 채워뒀다:

| 문서 | 다루는 내용 |
|---|---|
| `compute-on-aws-how-to-choose` | EC2 vs Lambda vs ECS/EKS/Fargate, 워크로드 특성별 서비스 선택 기준 |
| `wellarchitected-cost-optimization-pillar` | AWS Well-Architected 비용 최적화 원칙 |
| `AWSEC2/.../instance-types.html` | 인스턴스 패밀리/사이즈를 워크로드에 맞게 고르는 기준 |
| `savingsplans/.../what-is-savings-plans.html` | Savings Plans로 할인받는 조건과 방식 |
| `AWSEC2/.../using-spot-instances.html` | Spot Instance를 언제 쓸 수 있는지, 중단 리스크 |
| `lambda/.../provisioned-concurrency.html` | Lambda 콜드스타트 해결과 그 비용 트레이드오프 |
| `aws-cost-optimization` | AWS 비용 최적화 총론 |
| `*-pricing.md` (EC2/Lambda/Fargate) | 구매 옵션(온디맨드/예약/스팟)을 언제 골라야 하는지의 설명 (숫자 자체는 이제 `pricing.py`가 담당) |

## 요금 계산기(`calculate_cost`) 관련 주의

- `pricing.py`가 **AWS Price List Bulk API**(공식, 인증 불필요)에서 실시간 단가를 가져온다. AWS가 가격을 바꿔도 다음 호출부터 바로 반영됨.
  - **Lambda / Fargate**: 가격표 파일이 작아서(1~2MB) 계산할 때마다 바로 받아온다 (1시간 메모리 캐시).
  - **EC2**: 전체 가격표가 480MB라 매번 받을 수 없어서, 지원하는 4개 인스턴스 타입(`t3.micro`, `t3.medium`, `m5.large`, `m5.xlarge`)만 스트리밍으로 걸러 `data/ec2_price_cache.json`에 저장하고 24시간마다 자동 갱신한다. `refresh_ec2_prices.py`로 수동 갱신도 가능.
  - 실시간 조회가 실패하면(네트워크 문제 등) `tools.py`의 `FALLBACK_*` 하드코딩 값으로 자동 폴백하고, 응답에 "근사치(실시간 조회 실패, 폴백)"라고 표시한다.
- 프리티어(무료 사용량)는 계산에 반영하지 않음.
- RAG(문서 검색)와 실시간 요금 API는 서로 다른 역할: 문서는 "언제/왜 이 서비스를 쓰는지"(정성적 가이드), API는 "얼마인지"(정량적 단가) — 실시간 API를 붙였다고 RAG가 필요 없어지는 게 아니라 상호보완적임.

## 스트리밍 (`/query/stream`)

- SSE(Server-Sent Events)로 `POST /query/stream`을 호출하면 `event: phase`(검색/계산 필요 여부) →
  `event: token`(텍스트 조각, 여러 번) → `event: done`(thread_id) 순으로 흘러온다.
- **최종 답변이 나오는 노드의 토큰만** 스트리밍한다. supervisor가 검색/계산 중 뭐가 필요한지 정하는 순간 최종 답변이
  어디서 나올지도 정해지기 때문:
  - 둘 다 필요 → `synthesizer`가 합치는 답변을 스트리밍 (retrieval_agent/cost_agent는 병렬로 도는 중간 단계라
    스트리밍 대상에서 제외함 — 안 그러면 두 서브그래프의 노드 이름이 둘 다 "agent"라 텍스트가 섞여 나옴)
  - 하나만 필요 → 그 에이전트의 답변을 그대로 스트리밍
- 구현 원리: LangGraph 서브그래프 안쪽 LLM 호출까지 스트리밍 이벤트가 전파되려면, 노드 함수가 그래프로부터
  받은 `config`를 서브그래프 `.invoke()`/내부 LLM `.invoke()` 호출에 그대로 넘겨줘야 한다 (`graph.py`의
  모든 노드 함수가 `config` 파라미터를 받아서 그대로 전달하는 이유).
- **버그 하나 고침**: `claude-sonnet-5`는 확장 사고(extended thinking)가 기본으로 켜져 있는데, 스트리밍 상태에서
  ReAct 루프가 2번째 턴을 돌 때(도구 호출 결과를 다시 보낼 때) 사고 블록이 깨져서
  `anthropic.BadRequestError: messages.1.content.0.thinking.thinking: Field required`가 났음. 이 프로젝트는
  깊은 추론이 필요한 게 아니라 도구 호출+계산 위주라 `thinking={"type": "disabled"}`로 꺼서 해결함.
- Streamlit UI(`streamlit_app.py`)도 이 엔드포인트로 갈아타서 답변이 타이핑되듯 나옴.

## 알려진 제약

- `search_aws_docs`, `calculate_cost` 도구 함수가 파일 상단에서 벡터스토어를 지연 초기화(lazy) 하는데, 동시 호출 시 경쟁 조건이 있어 락으로 방지함 (langgraph 코드리뷰에서 발견했던 것과 동일 패턴).
- `synthesizer`가 둘 다 필요할 때만 LLM을 호출하도록 최적화했지만, `supervisor`는 모든 질문마다 LLM 호출 1번이 고정으로 붙음 (규칙 기반으로 바꾸면 절약 가능, 지금은 LLM 기반으로 확정).
- (해결됨, 08-07) EC2 캐시가 없거나 오래된 상태에서 첫 계산 요청이 들어오면 그 요청이 480MB 다운로드를 떠안아 느려지던 문제 — `app.py`의 `lifespan`에서 서버 기동 시점에 미리 캐시를 준비하도록 고침. 아래 "겪은 버그" 참고.

## 대화 히스토리 영속 저장 + 서랍형 UI

`MemorySaver`(메모리에만 저장, 서버 재시작하면 날아감) 대신 **SQLite 기반 체크포인터**를 써서
`checkpoints.sqlite` 파일에 저장한다 — 서버를 껐다 켜도(혹은 배포 후 컨테이너를 재시작해도) 같은
`thread_id`로 물어보면 이전 대화를 그대로 이어간다. 여기에 사이드바 "서랍" UI까지 붙여서, 새로고침(F5)해도
예전 대화 목록에서 클릭해 다시 열어볼 수 있다.

### 동기(SqliteSaver) vs 비동기(AsyncSqliteSaver) — 왜 둘 다 있나

- `/query`(일반 응답), 평가 스크립트(`evaluate_comparison.py`)는 그래프를 **동기(`.invoke()`)**로 호출한다 →
  **`SqliteSaver`**(동기 전용)로 충분함.
- `/query/stream`(SSE 토큰 스트리밍)은 `astream_events()`라는 **비동기 전용 API**를 쓴다 — LangGraph에
  이거랑 동급의 동기 버전이 없어서, 토큰 단위 실시간 스트리밍을 하려면 비동기가 필수다. `SqliteSaver`를
  비동기 실행 중에 쓰면 `"The SqliteSaver does not support async methods"` 에러가 난다.
- 그래서 `build_agent_graph(checkpointer=...)`가 체크포인터를 외부에서 주입받게 만들고: 평가 스크립트는
  기본값(동기 `SqliteSaver` 자동 생성)을 그대로 쓰고, `app.py`의 `lifespan`은 **`AsyncSqliteSaver`**를
  직접 만들어서 넘긴다. 둘 다 같은 `checkpoints.sqlite` 파일을 보므로 데이터는 하나로 합쳐진다.
- **비동기가 무조건 더 좋은 건 아님** — 답변 전체 완성 시간은 동기/비동기 둘 다 동일하고, 체감 반응성(첫
  토큰까지의 시간)만 비동기가 빠르다. 대신 코드 복잡도와 버그 발생 가능성은 비동기 쪽이 훨씬 높다(아래
  버그 참고). "실시간 타이핑 효과"라는 UX를 위해 일부러 감수한 트레이드오프.

### 겪은 버그 3개

1. `sqlite3.connect()`로 만든 파일 경로에 파일이 없는 상태에서 Docker 볼륨 마운트(`-v host:container`)를
   하면, Docker가 그 경로를 **자동으로 디렉토리로 생성**해버린다 (파일인지 폴더인지 모르니까). 그러면
   컨테이너 안에서 `sqlite3.connect()`가 "unable to open database file" 에러를 냄. **해결**: 마운트 전에
   호스트에 `touch checkpoints.sqlite`로 빈 파일을 미리 만들어둬야 함.
2. `langgraph-checkpoint-sqlite`(2.0.11)가 내부적으로 `aiosqlite.Connection.is_alive()`를 호출하는데,
   최신 `aiosqlite`(0.22.1)에서 이 메서드가 없어져서 `AttributeError` 발생. **해결**: `aiosqlite==0.20.0`으로
   버전 고정.
3. (08-07) `pricing.py`의 `refresh_ec2_cache()`가 살아있는 네트워크 스트림(`resp.raw`)을 `products` 섹션용,
   `terms.OnDemand` 섹션용으로 **두 번** 훑도록 짜여있었는데, 네트워크 스트림은 한 번 읽으면 되감을 수
   없다. `ijson`이 내부적으로 청크 단위로 버퍼링해서 읽다 보니, 첫 번째 훑기가 끝난 시점에 스트림 위치가
   이미 그만큼 앞서가 있어서, 두 번째 훑기가 어긋난 위치부터 파싱을 시작해 `ijson.common.IncompleteJSONError:
   premature EOF`가 났다(코드 버그이지 네트워크 문제가 아니었음 — 재현이 100% 결정적이었던 게 단서).
   **해결**: 응답을 한 번만 내려받아 `tempfile.TemporaryFile()`(되감기 가능)에 쓰고, 그 로컬 파일 위에서
   두 번 훑도록 변경.
   또한 캐시가 없거나 오래된 상태에서 사용자의 첫 계산 요청이 480MB 다운로드를 떠안지 않도록,
   `app.py`의 `lifespan`에서 서버 기동 시점에 `pricing.fetch_ec2_prices()`를 한 번 호출해 미리 데워둔다.

### 서랍 UI 구현 — 그리고 뒤늦게 발견한 프라이버시 문제

- `app.py`에 `GET /threads/{thread_id}`(특정 대화의 전체 메시지) 엔드포인트, `streamlit_app.py` 사이드바에
  그 대화로 재진입하는 버튼을 추가.
- 회원가입/로그인은 없음 — `thread_id`가 랜덤 UUID라 그 값을 아는 사람만 그 대화에 접근 가능한 구조.
- **초기 설계의 문제(08-07 발견 및 수정)**: 처음엔 `GET /threads`로 DB에 있는 **모든** `thread_id`를
  한꺼번에 나열해서 사이드바 목록을 채웠다. 로컬 1인 테스트 땐 문제가 안 보였는데, 배포해서 여러 명이
  같은 서버에 접속하는 상황을 가정하면 — A가 질문 몇 개를 하고 나가도, 그다음 접속한 B의 사이드바에
  A의 질문 미리보기가 그대로 노출되는 구조였다(로그인이 없으니 "내 것만 보여주기"라는 개념 자체가
  없었던 것). **해결**: `GET /threads`(전체 나열) 엔드포인트를 아예 삭제하고, 대신 각 브라우저 세션이
  자기가 만든 `thread_id`만 `st.session_state.my_thread_ids`에 기억해서 그 목록만 서버에 물어보도록
  변경. 서버 DB(`checkpoints.sqlite`)엔 여전히 모든 사용자의 대화가 다 저장되지만(의도된 동작), "누가
  봐도 되는 thread_id 목록"을 서버가 통째로 내어주지 않게 됨. 트레이드오프: 사이드바 목록 자체는 이제
  브라우저 새로고침하면 초기화된다(그 대화 내용 자체는 thread_id만 알면 여전히 열람 가능).

**Docker 배포 시 주의**: `checkpoints.sqlite`도 `vectordb/`처럼 볼륨 마운트를 안 하면 컨테이너 재시작 때
같이 날아간다 (아래 `docker-compose.yml` 참고).

## FastAPI + Streamlit 같이 배포 (`docker-compose.yml`)

Dockerfile은 FastAPI(`api`)만 실행하도록 되어 있어서, 링크 하나로 채팅 화면까지 보여주려면 Streamlit도
같이 띄워야 한다. 이미지는 하나만 빌드하고, `docker-compose.yml`이 그 이미지를 **두 개의 컨테이너**로
서로 다른 커맨드로 실행한다:

```bash
docker compose up --build
```

- `api`: `uvicorn app:app`으로 8000번, `vectordb`/`checkpoints.sqlite` 볼륨 마운트
- `ui`: `streamlit run streamlit_app.py`로 8501번, `API_URL=http://api:8000`로 `api` 컨테이너를 호출
  (컴포즈 내부 네트워크에서는 서비스 이름이 곧 호스트명이라 `localhost`가 아니라 `api`를 씀)

브라우저로 `http://localhost:8501` 접속하면 진짜 채팅 화면이 뜬다 (`http://EC2주소:8000`만 열면 API 문서
화면만 보여서 데모용으론 부족함).

## 서비스 브랜딩 — "가늠" (Ganeum)

서비스명을 "가늠"(estimate/gauge, "얼마나 필요한지 가늠하다")으로 정했다. 로고는 구름(AWS=클라우드) 안에
지폐 다발을 줄로 묶어 홀쭉하게 만든 모양으로, "비용을 다이어트시켜 최적화한다"는 컨셉을 형상화했다.

### 로고 이미지 — 체크무늬 배경이 진짜 투명이 아니었던 문제

AI로 생성한 원본 이미지가 "투명 배경"으로 안내됐지만, 실제로는 알파 채널이 아니라 **뷰어가 투명을 표시할 때
쓰는 회색/흰색 체크무늬가 색깔 픽셀로 그대로 구워져 있는 상태**였다(PNG인데도 알파값이 전 픽셀 255=완전
불투명). 그대로 쓰면 헤더에 체크무늬 사각형이 그대로 보임.

**해결**: 체크무늬는 회색조(R≈G≈B, 채도 낮음)이고 실제 로고(구름=파란색, 지폐=크림색, 줄/글자=네이비)는
전부 유채색이라는 점을 이용해, 이미지 가장자리에서부터 회색조 픽셀만 BFS로 flood-fill해 투명 처리하고
(글자 안쪽처럼 테두리에 안 닿는 고립된 체크무늬 잔여 영역은 작은 연결 요소(connected component)로 따로
잡아 제거), 실제 내용이 있는 영역만 알파 유지 → 여백을 크롭해 `static/logo.png`로 저장했다. 마젠타 등
튀는 색 배경에 합성해서 투명 처리가 제대로 됐는지 시각적으로 검증함.

### UI 스타일

Streamlit 헤더/배경에 하늘색 그라데이션(`#CFE9F7` → `#FBFDFE`)과 은은한 흰 구름 도형(`position: fixed`
타원 3개), Poppins 폰트를 적용해 밝고 화사한 톤을 냈다 (banapresso.com 참고). 로고는 `st.markdown`의
raw HTML로 넣는데, 이미지를 base64 data URI로 인코딩해 `<img src="data:image/png;base64,...">`로 넣는다
— raw `<svg>`/`<img>` 태그를 그대로 markdown에 넣으면 Streamlit의 markdown 파서가 내부 태그를 밖으로
새어나가게 만드는 버그가 있어서(중복 텍스트 렌더링), base64 인코딩으로 우회함.

## 기능 추가 계획

(현재 없음 — 다음 항목은 로드맵 참고: EC2 배포, CI/CD `deploy:` job)

