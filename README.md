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
| 2026-08-01 (토) | LangSmith 3자 비교 평가 20문항으로 완주. **계산기 도구 추가가 가장 큰 개선 요인**(needs_calc에서 구조 차이 없음)이고, **멀티 에이전트 구조도 search_only에서 소폭이지만 재현 가능한 이득**(supervisor가 불필요한 tool 호출을 걸러줌)을 확인 — `evaluation/README.md`에 실제 답변 비교까지 포함해 정리 | 완료 |
| 2026-08-04 | Thread-Id 기반 히스토리 영속 저장 구현(`MemorySaver`→`SqliteSaver`/`AsyncSqliteSaver`, 서랍형 사이드바 UI) + Docker/Docker Compose 패키징(FastAPI+Streamlit 컨테이너 2개, 볼륨 마운트로 재시작해도 데이터 유지) + 비용 산정 문서 6종 추가 | 완료 (08-02, 08-06 계획을 앞당겨 함께 완료) |
| 2026-08-04 | GitHub Actions CI 워크플로(`ci.yml`) 구축 — push/PR 시 `pip install` + `py_compile`로 빌드 확인 | 완료 (CD `deploy:` job은 EC2 수동 배포 검증 후 추가 예정) |
| 2026-08-05 | 서비스 브랜딩 — 이름 "가늠"(Ganeum, "얼마나 필요한지 가늠하다") 확정, 로고 제작(구름+지폐다발+묶은 줄 = "비용 다이어트/최적화" 형상화), Streamlit 헤더/배경(하늘색 그라데이션 + 구름 도형 + Poppins 폰트)에 적용 | 완료 |
| 2026-08-09 (일) | AWS EC2 인스턴스 생성 + 수동 배포 검증(SSH 접속 → Docker 설치 → `docker compose up --build`) | 예정 |
| 2026-08-16 (일) | **최종 포폴 `multi-agent-rag` AWS EC2 배포 완료 (배포 데드라인)** — GitHub Actions CD로 자동 배포까지 포함해 외부에서 접근 가능한 상태로 확인 | 예정 |

목표일: 2026-08-16(일) 배포 데드라인.
