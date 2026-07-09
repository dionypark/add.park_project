# 7주차 — rangchain (LangChain 마이그레이션)

`vanilla-rag`의 손수 짠 RAG 파이프라인을 LangChain LCEL 체인으로 마이그레이션.

## 과제 요구사항 대조

| 요구사항 | 상태 |
|---|---|
| 개인 프로젝트 RAG를 LangChain 기반으로 마이그레이션 | ✅ `rag_query.py` (LCEL 체인) |
| FastAPI로 REST API 배포 | ✅ `app.py` |
| LangSmith로 Tracing + Dataset 기반 평가 | ✅ `evaluate_langsmith.py` (LangSmith API 키 필요) |

## vanilla-rag 대비 뭐가 바뀌었나 (살아있는 것 vs 죽는 것)

| 개념 | vanilla-rag (함수 호출) | rangchain (LangChain) |
|---|---|---|
| 검색 | `retrieve()` + 직접 ChromaDB 쿼리 | **죽음** → `vectorstore.as_retriever()` 객체가 대체 |
| 프롬프트 조립 | `build_prompt()` f-string | **죽음** → `ChatPromptTemplate` 객체가 대체 |
| 생성 호출 | `anthropic_client.messages.create()` 직접 호출 | **죽음** → `ChatAnthropic` 래퍼가 대체 |
| 출력 형식 | `response.content`에서 텍스트 블록 직접 추출 | **죽음** → `StrOutputParser()`가 표준화 |
| 흐름 제어 | 함수를 순서대로 호출 | **바뀜** → `RunnableParallel` + `RunnablePassthrough.assign`으로 조립된 LCEL 체인, `.invoke()` 한 번으로 실행 |
| 청킹 | `chunking.py` (헤더 기반) | **삶** → 그대로 재사용, `Document` 객체로만 감쌈 |
| 임베딩 모델 | 허깅페이스 로컬 (`ko-sroberta-multitask`) | **삶** → 동일 모델, `HuggingFaceEmbeddings` 래퍼로 사용 |
| 벡터DB | ChromaDB 직접 사용 (영구 저장 + 스킵 가드) | **삶** → 동일 원칙, `langchain_chroma.Chroma`로 사용 |
| 평가 | RAGAS (Gemini 채점자) | **바뀜** → LangSmith Dataset + Tracing (과제 요구사항이 명시적으로 LangSmith) |

## 구조

```
data/aws_docs/*.md     AWS 문서 샘플 (vanilla-rag와 동일)
chunking.py            헤더 기반 청킹 (vanilla-rag에서 그대로 재사용)
build_vectordb.py      문서 → Document 변환 → HuggingFace 임베딩 → langchain_chroma 영구 저장
rag_query.py           LCEL 체인 (retriever | prompt | ChatAnthropic | StrOutputParser)
app.py                 FastAPI REST API (/ask, /health)
evaluate_langsmith.py  LangSmith Dataset 생성 + Tracing + 평가
```

## 실행 방법

```bash
cd rangchain
source .venv/bin/activate
cp .env.example .env    # ANTHROPIC_API_KEY, LANGCHAIN_API_KEY 입력 필요
python build_vectordb.py
python rag_query.py "질문"
uvicorn app:app --reload
python evaluate_langsmith.py   # LangSmith 키 필요, LANGCHAIN_TRACING_V2=true로 켜야 트레이싱 됨
```

## 코드 리뷰로 발견/수정한 것

- 동시 요청 시 체인 초기화가 중복 실행될 수 있던 경쟁 조건 → 락으로 방지
- 벡터DB가 비어있어도 조용히 200을 반환하던 문제 → 503 + 명확한 에러 메시지로 수정
- 요청별 `top_k` 조절 기능이 빠져있던 것 → 복구 (가벼운 부분만 매 요청 재구성, 무거운 임베딩/LLM 로딩은 캐싱 유지)
- `data/aws_docs/*.md`를 수정해도 재인덱싱 안 되던 문제 → 문서 내용 fingerprint(해시) 비교로 변경 감지 시 자동 재인덱싱
- RAGAS 평가의 한국어 키워드 채점이 조사 때문에 사실상 무의미했던 문제 → 영문 기술 용어(Lambda, EC2, TCO 등) 우선 추출로 개선
- 평가 함수들의 방어적 접근(`.get()`) 보강, `target()` 예외 발생 시에도 평가가 중단되지 않도록 처리
- 첫 요청이 임베딩 모델 로드+DB 연결 비용을 떠안던 콜드 스타트 문제 → `lifespan`으로 서버 시작 시 웜업(`warm_up()`)하도록 수정

## 알려진 제약

- `evaluate_langsmith.py`의 LLM 채점자가 답변 생성 모델과 동일한 Claude를 사용함 (vanilla-rag의 RAGAS 평가는 Gemini로 독립 채점했던 것과 다름). 별도 모델로 채점하고 싶으면 judge용 모델만 교체하면 됨.
- LangSmith 키가 없으면 `LANGCHAIN_TRACING_V2=false`로 두어야 트레이싱 전송 실패 로그가 안 뜸.
- 이미 존재하는 LangSmith Dataset을 재사용할 때 스키마(입력/출력 키)를 검증하지 않음.
