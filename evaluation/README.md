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

## 예비 결과 (질문 10개 기준, 2026-07-31)

30문항으로 확장했다가 토큰 사용량이 너무 커서 20문항(카테고리당 10개)으로 다시 줄였고, Anthropic API
사용량 한도로 실행이 중단되어(2026-08-01 00:00 UTC 리셋 이후 재실행 예정) 아래는 초기 10문항
(검색 5 + 계산 5) 기준 예비 결과다.

| | contains_dollar_amount | contains_expected_keyword | llm_judge |
|---|---|---|---|
| `langgraph-v1` | 0.50 | 0.40 | 0.70 |
| `multi-agent-rag-v1` | 0.60 | 0.50 | 0.90 |
| `single-agent-baseline-v1` | 0.60 | 0.60 | 0.90 |

카테고리별로 나누면:

**search_only (5문항)** — `single-agent-baseline`과 `multi-agent-rag`가 완전 동률(0.60/0.20/0.80).
구조 차이가 결과에 영향을 안 줌.

**needs_calc (5문항)** — `contains_dollar_amount`/`llm_judge`가 `langgraph`(0.60/0.70)에서
baseline·multi-agent(둘 다 1.00/1.00)로 크게 뜀. **계산기 도구 추가의 효과가 뚜렷함.**
반면 `contains_expected_keyword`는 baseline(0.60)이 multi-agent(0.40)보다 높았는데, `llm_judge`가
둘 다 만점(1.00)인 걸 보면 실제 오답이 아니라 답변 문구 차이로 보인다.

**잠정 결론**: 이번 소규모(n=5/카테고리) 예비 테스트에서는, **구조(멀티 에이전트) 자체의 효과보다
계산기 도구 추가의 효과가 훨씬 뚜렷했다.** 구조 차이는 통계적으로 유의미하다고 보기엔 표본이 작아
20문항(카테고리당 n=10) 결과로 재검증 필요 — 결과 나오는 대로 이 섹션을 갱신할 예정.
