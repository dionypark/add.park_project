# 6주차 — AWS 서비스 선택/비용 최적화 어드바이저 (RAG)

Claude API를 LLM으로, 허깅페이스 오픈소스 모델을 임베딩으로 사용한 RAG 챗봇. AWS 공식 문서/Well-Architected Framework/요금 안내를 근거로 "트래픽 적은 개인 프로젝트인데 뭐 써야해?" 같은 질문에 답한다.

## 과제 요구사항 대조

| 요구사항 | 상태 |
|---|---|
| LLM으로 문서 로딩→응답 생성 RAG 구축 | ✅ (LLM 자유 선택 허용 확인 후 Claude 사용) |
| FastAPI로 REST API 배포 | ✅ `app.py` |
| RAGAS 등으로 평가 | ✅ `evaluate_ragas.py` |
| Graph RAG (선택) | ❌ 미구현 |

## 구조

```
data/aws_docs/*.md   AWS 문서 샘플 (EC2, Lambda, Fargate, Well-Architected, 선택 가이드)
chunking.py          마크다운 헤더 기반 청킹
build_vectordb.py    문서(Synthetic Data) → 임베딩(로컬 허깅페이스 모델) → ChromaDB 저장 (최초 1회, 이후 자동 스킵)
rag_query.py         검색(로컬 임베딩) → Claude 답변 생성
app.py               FastAPI REST API (/ask, /health)
evaluate_ragas.py     RAGAS 평가 — Gemini를 별도 채점자(judge)로 사용 (자기 답을 자기가 채점하지 않도록)
```

인덱싱(문서 임베딩)과 쿼리(질문 응답)를 별도 스크립트로 분리했고, 임베딩은 벡터DB(`vectordb/`)에 영구 저장해 재사용한다 (매번 재임베딩하지 않음).

## 실행 방법

```bash
cd vanilla-rag
source .venv/bin/activate          # 가상환경 켜기
cp .env.example .env               # .env에 GOOGLE_API_KEY, ANTHROPIC_API_KEY 입력 필요
python build_vectordb.py           # 최초 1회: 문서 임베딩+저장
python rag_query.py "질문"          # CLI로 질문/답변 테스트
uvicorn app:app --reload           # REST API 서버
python evaluate_ragas.py           # RAGAS 평가
```

## 사용한 것

- LLM(답변 생성): Claude API (`anthropic` SDK, `claude-sonnet-5`)
- 임베딩: 허깅페이스 오픈소스 모델 (`jhgan/ko-sroberta-multitask`, 로컬 실행, API 호출 없음)
- 평가 채점자: Gemini API (`gemini-2.5-flash`) — 답변 생성 모델과 독립적인 평가자
- 벡터DB: ChromaDB (`PersistentClient`)
- API 서버: FastAPI

임베딩 모델을 바꾸면 `vectordb/`를 삭제하고 `build_vectordb.py`를 다시 실행해야 한다 (모델마다 벡터 차원이 달라서 기존 데이터와 호환되지 않음).

## 왜 이렇게 구성했나

- **임베딩과 생성 LLM을 분리**: Anthropic은 임베딩 API 자체가 없어서, 임베딩은 허깅페이스 로컬 모델로, 답변 생성만 Claude로 나눔.
- **평가 채점자는 Gemini 유지**: 답변을 만든 모델(Claude)이 자기 답을 스스로 채점하면 편향될 수 있어, 독립적인 모델(Gemini)을 평가자로 둠.
- **서버 시작 시 웜업(warm-up)**: `app.py`의 `lifespan`에서 서버가 요청을 받기 전에 임베딩 모델 로드 + ChromaDB 연결을 미리 끝내둔다(콜드 스타트 방지). 이전에는 이 무거운 초기화가 매 요청마다(심지어 첫 요청뿐 아니라 계속) 반복됐음.
