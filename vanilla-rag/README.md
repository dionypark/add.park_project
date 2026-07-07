# 6주차 — AWS 서비스 선택/비용 최적화 어드바이저 (RAG)

Gemini API를 LLM으로 사용한 RAG 챗봇. AWS 공식 문서/Well-Architected Framework/요금 안내를 근거로 "트래픽 적은 개인 프로젝트인데 뭐 써야해?" 같은 질문에 답한다.

## 구조

```
data/aws_docs/*.md   AWS 문서 샘플 (EC2, Lambda, Fargate, Well-Architected, 선택 가이드)
chunking.py          마크다운 헤더 기반 청킹
build_vectordb.py    문서 → 임베딩 → ChromaDB 저장 (최초 1회, 이후 자동 스킵)
rag_query.py         검색 → Gemini 답변 생성
app.py               FastAPI REST API (/ask, /health)
evaluate_ragas.py     RAGAS 평가 (faithfulness, answer_relevancy, context_precision, context_recall)
```

인덱싱(문서 임베딩)과 쿼리(질문 응답)를 별도 스크립트로 분리했고, 임베딩은 벡터DB(`vectordb/`)에 영구 저장해 재사용한다 (매번 재임베딩하지 않음).

## 실행 방법

```bash
cd vanilla-rag
source .venv/bin/activate          # 가상환경 켜기
cp .env.example .env               # .env에 GOOGLE_API_KEY 입력 필요
python build_vectordb.py           # 최초 1회: 문서 임베딩+저장
python rag_query.py "질문"          # CLI로 질문/답변 테스트
uvicorn app:app --reload           # REST API 서버
python evaluate_ragas.py           # RAGAS 평가
```

## 사용한 것

- LLM/임베딩: Gemini API (`google-genai` SDK)
- 벡터DB: ChromaDB (`PersistentClient`)
- API 서버: FastAPI
- 평가: RAGAS
