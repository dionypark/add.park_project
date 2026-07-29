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


## 실행 방법

```bash
cd multi-agent-rag
source .venv/bin/activate
pip install -r requirements.txt    # ijson 추가됨 (EC2 요금표 스트리밍 파싱용)
cp .env.example .env    # ANTHROPIC_API_KEY, LANGCHAIN_API_KEY 입력 필요
python build_vectordb.py
python refresh_ec2_prices.py       # EC2 요금 캐시 최초 생성 (선택, 없으면 첫 EC2 계산 때 자동 생성)
uvicorn app:app --reload           # REST API 서버 (터미널 1)
streamlit run streamlit_app.py     # 채팅 UI (터미널 2)
```

## 요금 계산기(`calculate_cost`) 관련 주의

- `pricing.py`가 **AWS Price List Bulk API**(공식, 인증 불필요)에서 실시간 단가를 가져온다. AWS가 가격을 바꿔도 다음 호출부터 바로 반영됨.
  - **Lambda / Fargate**: 가격표 파일이 작아서(1~2MB) 계산할 때마다 바로 받아온다 (1시간 메모리 캐시).
  - **EC2**: 전체 가격표가 480MB라 매번 받을 수 없어서, 지원하는 4개 인스턴스 타입(`t3.micro`, `t3.medium`, `m5.large`, `m5.xlarge`)만 스트리밍으로 걸러 `data/ec2_price_cache.json`에 저장하고 24시간마다 자동 갱신한다. `refresh_ec2_prices.py`로 수동 갱신도 가능.
  - 실시간 조회가 실패하면(네트워크 문제 등) `tools.py`의 `FALLBACK_*` 하드코딩 값으로 자동 폴백하고, 응답에 "근사치(실시간 조회 실패, 폴백)"라고 표시한다.
- 프리티어(무료 사용량)는 계산에 반영하지 않음.
- RAG(문서 검색)와 실시간 요금 API는 서로 다른 역할: 문서는 "언제/왜 이 서비스를 쓰는지"(정성적 가이드), API는 "얼마인지"(정량적 단가) — 실시간 API를 붙였다고 RAG가 필요 없어지는 게 아니라 상호보완적임.

## 알려진 제약

- `search_aws_docs`, `calculate_cost` 도구 함수가 파일 상단에서 벡터스토어를 지연 초기화(lazy) 하는데, 동시 호출 시 경쟁 조건이 있어 락으로 방지함 (langgraph 코드리뷰에서 발견했던 것과 동일 패턴).
- `synthesizer`가 둘 다 필요할 때만 LLM을 호출하도록 최적화했지만, `supervisor`는 모든 질문마다 LLM 호출 1번이 고정으로 붙음 (규칙 기반으로 바꾸면 절약 가능, 지금은 LLM 기반으로 확정).
- EC2 캐시가 24시간 넘게 오래됐는데 갱신 시점에 마침 계산 요청이 들어오면, 그 1번의 호출은 480MB 다운로드 때문에 응답이 느려질 수 있음(수십 초 단위). 데모 전에 `refresh_ec2_prices.py`를 미리 한 번 돌려두는 걸 권장.

## 기능 추가 계획

- 대화 히스토리 저장 DB 구축 (실제 상용 LLM 서비스처럼 각각의 thread-id 를 통한 서랍형태 채팅창 목표)

