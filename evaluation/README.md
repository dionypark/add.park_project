# 3자 비교 평가 — langgraph vs single-agent-baseline vs multi-agent-rag

`multi-agent-rag`(최종 포폴)의 **계층형 멀티 에이전트 구조 자체가 실제로 효과가 있는지**를,
LangSmith Dataset/Evaluator 기반으로 정량 비교한 기록.

## 왜 이 실험을 했나

`multi-agent-rag`은 `langgraph`(8주차, 싱글 에이전트)에서 두 가지를 동시에 바꿨다:
1. **도구 추가**: `search_aws_docs` 하나뿐이던 `langgraph`에 `calculate_cost`(AWS Price List API 실시간 연동)를 추가
2. **구조 변경**: 에이전트 1개 → supervisor + retrieval_agent + cost_agent + synthesizer로 역할 분리

이 둘을 한꺼번에 비교하면 "뭐 때문에 좋아졌는지"가 섞여버린다. 그래서 **도구는 완전히 동일하고 구조만
싱글로 되돌린 대조군**(`single-agent-baseline`)을 하나 더 만들어서, 두 변화의 효과를 분리해서 봤다.

## 비교 대상 3개

| | 도구 | 구조 | 코드 위치 |
|---|---|---|---|
| `langgraph-v1` | `search_aws_docs`만 | 싱글 에이전트(ReAct) | [`../langgraph/graph.py`](../langgraph/graph.py) |
| `single-agent-baseline-v1` | `search_aws_docs` + `calculate_cost` | 싱글 에이전트(ReAct) | [`../multi-agent-rag/baseline_single_agent.py`](../multi-agent-rag/baseline_single_agent.py) |
| `multi-agent-rag-v1` | `search_aws_docs` + `calculate_cost` | supervisor + retrieval_agent + cost_agent + synthesizer | [`../multi-agent-rag/graph.py`](../multi-agent-rag/graph.py) |

## 실행 스크립트는 왜 여기 없고 각 프로젝트 폴더에 있나

`langgraph/`와 `multi-agent-rag/`에 동명의 `config.py`, `build_vectordb.py`가 있어서, 한 스크립트에서
두 프로젝트를 동시에 import하면 파이썬 모듈이 서로 충돌한다(먼저 로드된 쪽의 설정을 나머지가 잘못 가져다 씀).
그래서 실행 스크립트는 각자의 venv/프로젝트 안에 남겨두고, 이 폴더는 **평가 설계와 결과를 정리하는 문서**
역할만 한다.

- [`../langgraph/evaluate_comparison.py`](../langgraph/evaluate_comparison.py) — `langgraph-v1` 실행
- [`../multi-agent-rag/evaluate_comparison.py`](../multi-agent-rag/evaluate_comparison.py) — `multi-agent-rag-v1`, `single-agent-baseline-v1` 실행 (한 스크립트에서 순서대로)

두 스크립트 다 같은 이름의 LangSmith Dataset(`aws-advisor-comparison-eval`)을 공유해서, 결과는 LangSmith
웹에서 세 실험을 함께 비교할 수 있다.

## Dataset 구성

질문 20개 = **검색만 필요(search_only) 10개** + **계산 필요(needs_calc) 10개**, 각 example에
`metadata.category`로 태그. 계산 문항의 기대 답변(reference)은 AWS Price List Bulk API에서 직접
검증한 실시간 단가로 계산한 값을 사용했다(Lambda $0.0000002/요청·$0.0000166667/GB-초, EC2
t3.micro $0.0104/hr·t3.medium $0.0416/hr·m5.large $0.096/hr·m5.xlarge $0.192/hr, Fargate
$0.04048/vCPU-hr·$0.004445/GB-hr).

## Evaluator 3개

| 이름 | 방식 | 측정 대상 |
|---|---|---|
| `contains_expected_keyword` | 정규식(LLM 안 씀) | 기대 답변의 핵심 키워드 포함 여부 |
| `contains_dollar_amount` | 정규식(LLM 안 씀) | `$숫자` 형태의 실제 금액을 냈는지 — needs_calc에서 "계산기 유무 효과"를 저비용으로 판별 |
| `llm_judge_semantic_match` | LLM-as-judge (Claude) | 기대 답변과 의미상 일치하는지 0/0.5/1 |

지연시간·토큰 사용량은 별도 evaluator 없이 LangSmith 트레이싱이 자동 집계한다.

## 최종 결과 (질문 20개 기준, 2026-08-01 재실행)

전체 평균:

| | contains_dollar_amount | contains_expected_keyword | llm_judge |
|---|---|---|---|
| `langgraph-v1` | 0.50 | 0.50 | 0.65 |
| `single-agent-baseline-v1` | 0.70 | 0.50 | 0.93 |
| `multi-agent-rag-v1` | 0.55 | 0.55 | **0.97** |

카테고리별로 나누면:

**search_only (10문항)** — `contains_dollar_amount`는 이 카테고리에선 의미 없는 지표(질문 자체가
금액을 묻지 않으니 무시). 의미 있는 두 지표에서 `multi-agent-rag`가 `single-agent-baseline`을
일관되게 앞섬: keyword 0.70 vs 0.60, judge **0.95 vs 0.85**.

**needs_calc (10문항)** — `langgraph`(dollar 0.90/judge 0.50)에서 baseline·multi-agent(둘 다
dollar 1.00/judge 1.00)로 큰 폭 상승. **계산기 도구 추가의 효과가 압도적이고, 구조 차이는 완전 동률.**
(langgraph가 계산기 없이도 dollar 0.90을 낸 건 어림짐작으로 숫자를 냈기 때문인데, judge가 0.50에
그친 걸 보면 절반은 틀린 어림짐작이었다는 뜻.)

### search_only에서 왜 multi-agent가 이겼나 (실제 답변 비교)

점수 차이가 난 문항들을 직접 열어보니, 우연이 아니라 **재현 가능한 이유**가 있었다:

- **"Spot Instance는 어떤 워크로드에 적합해?"** (계산 불필요한 순수 질문)
  - `multi-agent-rag`(judge=1.0): 검색 결과만으로 깔끔하게 답변
  - `single-agent-baseline`(judge=0.5): 안 물어봤는데 **Fargate 비용 계산**을 답변에 끼워 넣음
- **"배치 작업에는 어떤 컴퓨팅 서비스가 적합해?"** (역시 순수 질문)
  - `multi-agent-rag`(judge=1.0): "AWS Batch가 적합" + 근거 인용으로 끝
  - `single-agent-baseline`(judge=0.5): 또 뜬금없이 **월 $0.25 계산**을 붙임

`single-agent-baseline`은 `search_aws_docs`+`calculate_cost` 두 도구를 한 에이전트가 다 쥐고 있어서,
계산이 필요 없는 질문에서도 계산기 쪽으로 새는 경우가 있었다. 반면 `multi-agent-rag`는 **supervisor가
"이 질문은 needs_calculation=False"라고 먼저 걸러줘서**, `retrieval_agent`는 애초에 `calculate_cost`
자체를 안 갖고 있어 이런 이탈이 구조적으로 안 생긴다.

(반례도 있다: "EC2 구매 옵션" 문항은 반대로 baseline이 더 잘 답했다(1.0 vs 0.5) — 100% 일관된 법칙은
아니고, 답변 품질의 자연스러운 변동도 섞여 있다.)

### 결론

1. **가장 큰 개선 요인은 계산기(AWS Price List API) 도구 추가지, 구조가 아니다.** `needs_calc`에서
   구조 차이가 전혀 없었다는 게 직접적인 증거.
2. **구조(멀티 에이전트) 자체도 소폭이지만 실질적 이득이 있다** — `search_only`에서 baseline보다
   일관되게 나은 점수, 그리고 그 이유도 메커니즘으로 설명 가능(불필요한 tool 호출 방지). 다만 n=10/
   카테고리라 "확정적"이라기보단 "방향성 있는 관찰"로 보는 게 정직하다.
3. 종합하면 `multi-agent-rag`가 세 시스템 중 **가장 높은 llm_judge(0.97)**를 받았다.

## RAG는 여전히 필요한가 (API 도입 이후)

`needs_calc`에서 API 도입 효과가 워낙 커서("RAG 없어도 되는 거 아니냐") 반박이 들어올 수 있는데,
이 프로젝트가 애초에 RAG와 API를 아래 원칙으로 나눠 설계했기 때문에 반박이 성립하지 않는다:

1. **API 개선은 애초에 RAG가 담당하는 영역이 아니었다.** `needs_calc` 문항은 "월 100만 건, 200ms,
   512MB면 얼마?" 같은 순수 산술 질문이라, 계산기가 있으면 당연히 이긴다. RAG가 실패한 게 아니라
   이 카테고리 자체가 RAG의 역할이 아니었다.
2. **`search_only`(질문의 절반)에서는 지금도 RAG가 유일한 정보원이고, 실제로 일하고 있다.** 이 카테고리
   judge 점수가 0.65~0.95로 유의미하게 나온 게 그 증거 — `search_aws_docs`가 문서에서 실제 근거를
   찾아 답했기 때문이다. RAG를 빼면 이 절반의 질문은 답을 못 하거나 LLM이 그냥 아는 척(할루시네이션)
   해야 한다.
3. **API는 구조적으로 "숫자"만 줄 수 있지, "언제/왜/어떤 옵션"은 절대 줄 수 없다.** AWS Price List
   API는 `{서비스, SKU, 가격}` 데이터만 있다. "Spot Instance는 언제 써야 하나", "Reserved Instance와
   Savings Plans 차이" 같은 의사결정 지식은 API에 아예 존재하지 않고, AWS 공식 문서/백서에만 있어서
   RAG로만 접근 가능하다. API가 아무리 정확해져도 이 역할은 대체 불가능하다.
4. **RAG와 API는 애초에 양자택일이 아니라 같이 쓰라고 설계했다.** 실제 유저 질문은 "Fargate 언제 쓰고
   얼마야?"처럼 검색+계산이 동시에 필요한 경우가 흔하다. 이번 평가에서 카테고리를 나눠 본 건 비교를
   깔끔하게 하기 위해서일 뿐, `multi-agent-rag`의 supervisor는 애초에 두 조건이 다 해당되면
   `retrieval_agent`+`cost_agent`를 병렬로 같이 돌리고 `synthesizer`가 합치도록 설계돼 있다.

**한 줄 요약**: API는 "얼마"를 답하고 RAG는 "언제/왜"를 답한다 — 둘은 경쟁 관계가 아니라 서로 답할 수
없는 질문을 나눠 맡고 있다.
