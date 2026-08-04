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
| 멀티턴 | ✅ `MemorySaver` (langgraph와 동일) |
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
- EC2 캐시가 24시간 넘게 오래됐는데 갱신 시점에 마침 계산 요청이 들어오면, 그 1번의 호출은 480MB 다운로드 때문에 응답이 느려질 수 있음(수십 초 단위). 데모 전에 `refresh_ec2_prices.py`를 미리 한 번 돌려두는 걸 권장.

## 기능 추가 계획

- 대화 히스토리 저장 DB 구축 (실제 상용 LLM 서비스처럼 각각의 thread-id 를 통한 서랍형태 채팅창 목표)

- CI 테스트용 변경사항 

