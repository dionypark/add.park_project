# KTB AI실무개발 트랙 — 미니 프로젝트

카카오테크 부트캠프 AI실무개발 _ADD 개인프로젝트 RAG -> LangChain -> LangGraph

| 주차 | 폴더 | 내용 | 상태 |
|---|---|---|---|
| 6주차 | [`vanilla-rag/`](./vanilla-rag) | huggingface imbedding model + Anthropic API 기반 순수 RAG (AWS 서비스 선택/비용 최적화 어드바이저) | 완료 |
| 7주차 | [`langchain/`](./langchain) | LangChain 마이그레이션 | 완료 |
| 8주차 | [`langgraph/`](./langgraph) | LangGraph 마이그레이션 (ReAct 에이전트, 멀티턴) | 완료 |
| 최종 포폴 | [`multi-agent-rag/`](./multi-agent-rag) | 계층형 멀티 에이전트(supervisor+retrieval+cost) + 실시간 AWS 요금 API | 진행 중 |
| 평가 | [`evaluation/`](./evaluation) | langgraph vs single-agent-baseline vs multi-agent-rag 3자 비교 (LangSmith Dataset/Evaluator 기반) | 진행 중 |

각 폴더는 독립적으로 실행 가능하며, 자세한 내용은 폴더 안의 README를 참고.

## 진행 계획 (커밋 기록 기준)

| 날짜 | 내용 | 상태 |
|---|---|---|
| 2026-07-07 | 6주차 `vanilla-rag` 구현 (+ 7/8주차·최종 포폴 폴더 뼈대) | 완료 |
| 2026-07-08 | 임베딩을 허깅페이스 로컬 모델로, 답변 생성을 Claude로 교체 + 웹 채팅 UI 추가 | 완료 |
| 2026-07-09 | 7주차 `langchain` 마이그레이션 구현 + 코드 리뷰 반영 | 완료 |
| 2026-07-14 | 8주차 `langgraph` ReAct 에이전트 구현 + Streamlit UI 교체 | 완료 |
| 2026-07-22 | 폴더명 정리(`langchain`/`langgraph`) + 실제 AWS 문서로 데이터 교체 | 완료 |
| 2026-07-26 (일) | Docker 컨테이너 패키징 + Docker Compose 실행, AWS EC2 배포(외부 접근 가능하도록 구성) | 밀림 → 08-06로 재조정 |
| 2026-07-28 | 최종 포폴 `multi-agent-rag`(구 cascade-rag-agent) 멀티 에이전트(supervisor+retrieval+cost) 구현, AWS Price List API로 Lambda/EC2/Fargate 실시간 요금 조회 연동(EC2는 로컬 캐싱), 구조에 안 맞던 폴더명(cascade→multi-agent-rag) 정정 | 완료 |
| 2026-07-31 | `/query/stream`(SSE) 스트리밍 응답 추가, 비용 산정 도메인 문서 5종 보강(인스턴스 선택/Savings Plans/Spot/Provisioned Concurrency), `langgraph`(싱글+도구1개) vs `single-agent-baseline`(싱글+도구2개) vs `multi-agent-rag`(멀티+도구2개) 3자 비교용 LangSmith 평가 하네스 구축 — 30문항으로 확장했다가 토큰 사용량이 커서 20문항(카테고리당 10개)으로 재조정, evaluator 3종 | 완료(평가 실행은 API 사용량 한도로 08-01 이후 재개) |
| 2026-08-01 (토) | LangSmith 3자 비교 평가 결과 분석·정리. 10문항 예비 실행에서 **"멀티 에이전트 구조 자체보다 계산기 도구 추가가 더 큰 효과"**라는 걸 확인함 — 이 관찰이 실제로 20문항 규모에서도 유지되는지 검증하고, `evaluation/README.md`에 결과를 정직하게(과장 없이) 기록 | 예정 |
| 2026-08-02 | Thread-Id 기반 히스토리 영속 저장 구현 — 지금 `MemorySaver`는 서버 껐다 켜면 대화가 날아감. 실제 상용 LLM 서비스처럼 thread-id별 대화를 DB에 영속 저장해서 서랍(사이드바) 형태로 이어보는 게 목표 | 예정 |
| 2026-08-06 (목) | Docker 컨테이너 패키징 + Docker Compose 실행. `multi-agent-rag`는 임베딩 모델(sentence-transformers) 때문에 이미지가 무거울 수 있어, 멀티스테이지 빌드로 줄일지 검토 | 예정 |
| 2026-08-09 (일) | GitHub Actions로 push 시 자동 빌드·배포되는 CI/CD 파이프라인 구축 | 예정 |
| 2026-08-16 (일) | **최종 포폴 `multi-agent-rag` AWS EC2 배포 완료 (배포 데드라인)** — 외부에서 접근 가능한 상태로 확인 | 예정 |

목표일: 2026-08-16(일) 배포 데드라인.
