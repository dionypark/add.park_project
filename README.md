# KTB AI실무개발 트랙 — 미니 프로젝트

카카오테크 부트캠프 AI실무개발 _ADD 개인프로젝트 RAG -> LangChain -> LangGraph

| 주차 | 폴더 | 내용 | 상태 |
|---|---|---|---|
| 6주차 | [`vanilla-rag/`](./vanilla-rag) | huggingface imbedding model + Anthropic API 기반 순수 RAG (AWS 서비스 선택/비용 최적화 어드바이저) | 완료 |
| 7주차 | [`langchain/`](./langchain) | LangChain 마이그레이션 | 완료 |
| 8주차 | [`langgraph/`](./langgraph) | LangGraph 마이그레이션 (ReAct 에이전트, 멀티턴) | 완료 |
| 최종 포폴 | [`cascade-rag-agent/`](./cascade-rag-agent) | 난이도별 모델 라우팅 Cascade RAG Agent | 예정 |

각 폴더는 독립적으로 실행 가능하며, 자세한 내용은 폴더 안의 README를 참고.

## 진행 계획 (커밋 기록 기준)

| 날짜 | 내용 | 상태 |
|---|---|---|
| 2026-07-07 | 6주차 `vanilla-rag` 구현 (+ 7/8주차·최종 포폴 폴더 뼈대) | 완료 |
| 2026-07-08 | 임베딩을 허깅페이스 로컬 모델로, 답변 생성을 Claude로 교체 + 웹 채팅 UI 추가 | 완료 |
| 2026-07-09 | 7주차 `langchain` 마이그레이션 구현 + 코드 리뷰 반영 | 완료 |
| 2026-07-14 | 8주차 `langgraph` ReAct 에이전트 구현 + Streamlit UI 교체 | 완료 |
| 2026-07-22 | 폴더명 정리(`langchain`/`langgraph`) + 실제 AWS 문서로 데이터 교체 | 완료 |
| 2026-07-26 (일) | Docker 컨테이너 패키징 + Docker Compose 실행, AWS EC2 배포(외부 접근 가능하도록 구성) | 예정 |
| 2026-08-02 (일) 즈음 | GitHub Actions로 push 시 자동 빌드·배포되는 CI/CD 파이프라인 구축 | 예정 |
| 미정 | 최종 포폴 `cascade-rag-agent` 설계 및 구현 (난이도별 모델 라우팅) | 예정 |

목표일이 정해지면 마지막 줄에 채워 넣을 예정.
