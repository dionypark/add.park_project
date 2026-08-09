# 최종 포트폴리오 — Multi-Agent RAG

> CD 테스트 커밋 (2026-08-07) — 이 줄이 EC2에 반영되면 GitHub Actions 자동 배포 성공.

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
| 멀티턴 | ✅ `SqliteSaver`/`AsyncSqliteSaver`(영속 저장) + 계정(회원가입/로그인) 기반 서랍 UI |
| 스트리밍 | ✅ `/query/stream` (SSE, 최종 답변만 토큰 단위로 흘려보냄) |


## 실행 방법

```bash
cd multi-agent-rag
source .venv/bin/activate
pip install -r requirements.txt    # ijson(EC2 요금표 파싱), bcrypt/extra-streamlit-components(회원가입·로그인)
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

## 답변 품질 개선 (08-07) — 문서 의존도를 낮추고, 아키텍처+견적 상담을 지원

파일럿 테스트 중 발견한 두 가지 답변 품질 문제를 고쳤다.

**1. `retrieval_agent`가 문서에 없으면 무조건 "모른다"고 답하던 문제.** `RETRIEVAL_PROMPT`에
"문서에서 찾은 내용만 근거로 답하라"는 문장이 있었는데, 이 때문에 `search_aws_docs`가 커버 안 하는
질문(예: "S3가 뭐야?", "DynamoDB가 뭐야?", "메모리 부족 안 나게 하려면?")엔 Claude가 원래 알고 있는
내용도 답을 거부했다. 새 문서를 크롤링해서 RAG 저장소를 넓히는 대신(Claude 자체가 이미 AWS/서버
운영 지식을 갖고 있으므로 중복 작업), **문서 우선 검색 → 없으면 일반 지식으로 답하되
"(문서 근거 없음, 일반 지식)"이라고 명확히 구분 표시**하도록 프롬프트를 바꿨다. `SUPERVISOR_PROMPT`의
`needs_search` 판단 기준도 "AWS 서비스가 뭔지" 뿐 아니라 "어떻게 설정/운영하는지"(Docker, systemd,
swap 메모리 등 DevOps 질문)까지 포함하도록 넓혔다.

**2. `supervisor`가 계산 의도를 놓치는 문제.** "t3.medium 한 달 내내 켜두면 얼마 나와?"처럼 "계산해줘"라고
명시하지 않은 질문은 `needs_calculation=false`로 잘못 판단해서, 계산 없이 "AWS 공식 페이지에서
확인하세요"라고만 답하는 경우가 있었다. `SUPERVISOR_PROMPT`에 "얼마 나와/비용이 얼마/켜두면 얼마"
같은 뉘앙스도 계산 의도로 판단하라는 기준과 예시를 추가해서 고쳤다.

**3. 아키텍처 설계 + 종합 견적 지원.** "이런 서비스를 만들려는데 뭘 써야 하고 얼마 드는지"처럼 프로젝트
전체를 설명하는 질문에 대응하도록 `COST_PROMPT`/`RETRIEVAL_PROMPT`/`SYNTHESIZER_PROMPT`를 보강했다:
`cost_agent`가 구성요소별로 `calculate_cost`를 반복 호출해 항목별 요금+합계를 내고,
`calculate_cost`가 지원 안 하는 서비스(S3/RDS/DynamoDB/CloudFront 등)는 일반 지식으로 대략 추정하되
"(대략적 추정치, 실시간 API 아님)"이라고 표시하도록 했다. `retrieval_agent`는 서비스 조합과 구체적인
설정 옵션(인스턴스 타입, 스토리지 용량 등)까지 추천하고, `synthesizer`가 "① 추천 아키텍처 → ②
항목별 비용 표 + 합계" 순서로 정리해서 합친다.

**4. (겪은 버그) `max_tokens` 기본값(1024)이 너무 작아서 긴 답변(아키텍처+비용표 등)이 중간에 잘림.**
`langchain_anthropic`의 `ChatAnthropic`은 `max_tokens`를 명시 안 하면 1024로 고정되는데, 이 프로젝트
답변엔 너무 작았다. `retrieval_agent`/`cost_agent`/`synthesizer`의 LLM 인스턴스에 전부
`max_tokens=4096`을 명시해서 해결.

**5. (겪은 버그) 문서에 없는 애매한 질문에서 `retrieval_agent`/`cost_agent`가 검색을 무한정 반복하며
멈춘 것처럼 느려짐.** `search_aws_docs`를 몇 번이고 검색어만 바꿔가며 계속 호출할 수 있는데, "언제
그만 검색할지"에 대한 제한이 코드에 없었다 — 문서에 진짜 없는 내용이면 검색을 반복해도 결과가 안
나오니 계속 재시도만 하다 응답이 몇 분씩 걸리는 문제였다(파일럿 테스터 피드백으로 발견). **해결**:
(1) `RETRIEVAL_PROMPT`/`COST_PROMPT`에 "검색은 최대 2번까지만 시도하고 안 되면 그만두고 일반 지식으로
답변을 마무리하라"는 지시를 추가하고, (2) 모델이 그 지시를 안 지킬 경우를 대비해 서브그래프
`invoke()`에 `recursion_limit=8`을 걸어서 하드 제한을 뒀다. 제한에 걸리면(`GraphRecursionError`)
"검색을 여러 번 시도했지만 못 찾았다"는 안내 메시지로 우아하게 종료하도록 처리. 문서 범위 밖 질문(예:
AWS Outposts/Ground Station처럼 우리 RAG가 안 다루는 서비스)으로 테스트했을 때 30초 내로 안정적으로
답변이 끝나는 것 확인.

## RAG 문서 확장 (08-07) — 실제 스펙 데이터 보강

`docs-aws-amazon-com-awsec2-latest-userguide-instance-types-html.md`가 "인스턴스 타입이 뭔지" 개념
설명만 있고 실제 t3.small 등 개별 스펙(vCPU/RAM)은 다른 페이지로 링크만 걸어둔 채 안 긁어와서, 관련
질문에 구체적으로 답을 못 하는 문제가 있었다(파일럿 테스터 피드백). `ec2-instance-type-specs-t3-m5.md`를
새로 추가해서 T3(버스터블)/M5(범용) 패밀리의 사이즈별 vCPU/RAM/네트워크 스펙과 용도별 선택 기준을
표로 정리해뒀다. 문서 개수를 무작정 늘리기보다("몇백 개" 식으로), 일반 지식 폴백으로 이미 커버되는
부분은 그대로 두고 **정확한 수치가 중요한 스펙 데이터 위주로 타겟팅해서 보강**하는 방향으로 접근함.

**추가 보강(같은 날)**: 동료 테스터가 "t3.small 관련 질문에 답을 못 한다"고 준 피드백을 검토해서, 그중
① **T3 CPU 크레딧/베이스라인 성능 메커니즘**(왜 저렴한지, 언제 성능이 떨어지는지, T3 Unlimited 옵션)과
② **워크로드/프레임워크별 최소 권장 사이즈**(Spring Boot/Node.js/Docker 멀티컨테이너/PyTorch 추론 등,
부트캠프에서 실제 자주 쓰는 스택 기준) 두 섹션을 같은 문서에 추가했다. 반면 "인스턴스별 $ 가격을
문서에 직접 박아넣자"는 제안은 **의도적으로 반영 안 함** — 이 프로젝트는 애초에 "하드코딩된 가격표는
AWS가 가격을 바꾸면 무용지물"이라는 이유로 `pricing.py`(실시간 Price List API 조회)를 만든 것이었어서,
문서에 정적인 $ 숫자를 넣는 건 그 설계 원칙과 정면으로 충돌한다. **숫자(가격)는 계속 API가 담당하고,
문서는 안 바뀌는 구조/메커니즘/가이드라인만 담당**하는 역할 분리를 유지함.

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
   호스트에 `touch checkpoints.sqlite users.sqlite`로 빈 파일을 미리 만들어둬야 함(회원 DB인
   `users.sqlite`도 08-07에 추가되면서 마찬가지로 볼륨 마운트 대상이 됨).
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

### 서랍 UI — 3단계로 진화한 과정

1. **1차 (thread_id만)**: `app.py`에 `GET /threads/{thread_id}` 추가, 회원가입/로그인 없이 `thread_id`
   (랜덤 UUID)를 아는 사람만 그 대화에 접근 가능한 구조. 사이드바 목록은 `GET /threads`로 DB의
   **모든** thread_id를 통째로 나열해서 채웠음.
2. **2차 (08-07, 프라이버시 버그 수정)**: 1차 구조는 여러 명이 같은 서버에 접속하면 A의 질문 미리보기가
   B의 사이드바에도 그대로 노출되는 문제가 있었음(로그인이 없으니 "내 것만 보여주기"라는 개념 자체가
   없었던 것). `GET /threads`(전체 나열)를 삭제하고, 각 브라우저 세션이 자기가 만든 thread_id만
   `st.session_state`에 기억해서 그 목록만 물어보도록 임시 조치. 단점: 새로고침하면 목록이 초기화됨.
3. **3차 (08-07, 진짜 회원가입/로그인으로 교체 — 파일럿 테스트 대비)**: 세션 기반은 새로고침/기기 변경 시
   목록이 끊기는 한계가 있어서, 계정 기반으로 다시 바꿈. 아래 "회원가입/로그인" 절 참고.

### 회원가입/로그인 (`auth.py`)

- 새 모듈 `auth.py`가 `users.sqlite`(`users`/`sessions`/`user_threads` 3개 테이블)로 계정을 관리한다.
  비밀번호는 평문 저장 없이 `bcrypt`로 해싱, 로그인하면 랜덤 세션 토큰(`secrets.token_urlsafe`)을 발급한다
  (thread_id와 같은 발상: 토큰 자체가 "이 사람이 로그인했다"는 증거).
- `app.py`: `POST /auth/signup`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` 추가.
  `/query`, `/query/stream`, `/threads/{thread_id}`, `GET /my-threads`는 이제 전부
  `Authorization: Bearer <토큰>` 헤더 없으면 401. `user_threads` 테이블이 "이 user_id가 이
  thread_id를 만들었다"를 기록해서, `/threads/{thread_id}`는 **소유자 본인이 맞는지도** 검사한다
  (403) — thread_id를 안다고 무조건 열리던 1차 구조보다 한 단계 더 안전해짐.
- `streamlit_app.py`: 로그인 안 하면 로그인/회원가입 폼만 보여주고 나머지 UI는 `st.stop()`으로 막는다.
  로그인하면 세션 토큰을 브라우저 **쿠키**(`extra_streamlit_components.CookieManager`)에 저장해서,
  새로고침하거나 다른 기기로 접속해도(같은 계정으로 로그인만 하면) 대화 목록이 그대로 이어진다 —
  세션 기반이던 2차의 한계를 해결. 사이드바 "지난 대화"는 이제 `GET /my-threads`(로그인한 사용자
  본인 것만 서버가 필터링해서 리턴)를 호출한다.
- **겪은 버그**: `CookieManager.set()`으로 쿠키를 심자마자 바로 `st.rerun()`을 부르면, 브라우저 쪽
  컴포넌트(iframe)가 실제로 `document.cookie`를 쓰기 전에 화면이 다시 그려져서 쿠키가 안 써진 것처럼
  보이는 경쟁 조건이 있었다. **해결**: `set()`/`delete()` 직후 `time.sleep(0.5)`로 브라우저가 쿠키를
  실제로 쓸 시간을 준 다음 rerun. 또한 쿠키 읽기(`get_all()`)를 매 실행마다 새로 호출하지 않고,
  `CookieManager` 생성자가 이미 만들어둔 결과(`.get()`)를 재사용하도록 정리해 컴포넌트 호출 횟수를 줄임.

**Docker 배포 시 주의**: `checkpoints.sqlite`, `users.sqlite` 둘 다 `vectordb/`처럼 볼륨 마운트를 안 하면
컨테이너 재시작 때 같이 날아간다 (아래 `docker-compose.yml` 참고).

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

### EC2 수동 배포 중 겪은 버그 2개 (08-07)

1. **`sentence-transformers`가 딸려오는 `torch`가 기본으로 GPU(CUDA) 빌드** — 엔비디아 GPU 라이브러리가
   수백MB~600MB짜리로 여러 개 딸려와서(`nvidia-cublas-cu12` 594MB 등) 총 몇 GB를 차지함. GPU가 없는
   t3.small(EBS 20GiB)에서 빌드하다가 `OSError: [Errno 28] No space left on device`로 실패함.
   **해결**: `Dockerfile`에서 `requirements.txt` 설치 전에 CPU 전용 torch를
   `--index-url https://download.pytorch.org/whl/cpu`로 먼저 설치해두면, 이후 `sentence-transformers`가
   torch를 요구해도 "이미 설치됨"으로 보고 GPU 버전을 안 받아옴.
2. **다크모드 기기에서 로그인 폼 글씨가 거의 안 보임** — 기기가 다크모드면 Streamlit 기본 위젯(입력창,
   탭 텍스트)만 다크 테마로 바뀌는데, 커스텀 배경(하늘색 그라데이션)은 그대로라 대비가 깨져서 흰 글씨가
   흰 배경에 겹쳐 보임. 실제 아이폰 사파리(다크모드)에서 재현 확인. **해결**:
   `.streamlit/config.toml`에 `[theme] base = "light"`로 고정해서 기기 설정과 무관하게 항상 같은 밝은
   톤으로 나오게 함.

## CD — GitHub Actions로 자동 배포 (`ci.yml`)

`build-check`(기존 CI) 뒤에 `deploy` job을 추가했다. `main`에 실제로 push됐을 때만
(`if: github.event_name == 'push' && github.ref == 'refs/heads/main'`, PR 상태에선 안 돌아감)
`appleboy/ssh-action`으로 EC2에 SSH 접속해서 `git pull` + `docker compose up --build -d`를 실행한다.
Docker Hub 같은 이미지 저장소는 안 씀 — EC2가 최신 소스코드를 직접 받아서 그 자리에서 이미지를 새로
빌드하는 구조(수동 배포 때와 완전히 같은 방식, 사람이 하던 걸 GitHub Actions가 대신 함).

접속 정보(`EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`)는 코드에 안 넣고 **GitHub 저장소 Settings → Secrets
and variables → Actions**에 등록해서 워크플로 안에서 `${{ secrets.XXX }}`로만 참조한다 — pem 키 내용이
그대로 코드에 커밋되는 걸 막기 위함.

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

**모바일 반응형(08-07)**: `@media (max-width: 480px)` 미디어 쿼리로 좁은 화면에서 로고 크기(240px→170px)와
구름 도형 크기를 줄여 화면을 덜 차지하게 했다. Streamlit이 기본으로 뷰포트 메타 태그와 사이드바의
모바일 오버레이 동작(좁은 화면에서 사이드바가 전체화면 드로어로 바뀜)을 제공해서, 레이아웃 자체를 다시
짤 필요 없이 폰트/이미지 크기 조정만으로 충분했다. 실제 iPhone 크기(375px 너비)에서 로그인 폼/채팅
화면 모두 스크린샷으로 확인함.

## 기능 추가 계획

(현재 없음 — 다음 항목은 로드맵 참고: EC2 배포, CI/CD `deploy:` job)

