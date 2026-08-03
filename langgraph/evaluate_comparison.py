"""langgraph(싱글 에이전트, search_aws_docs 하나뿐)를 multi-agent-rag/evaluate_comparison.py와
같은 LangSmith Dataset("aws-advisor-comparison-eval")으로 평가한다.

두 프로젝트에 동명의 config.py/build_vectordb.py가 있어서 한 스크립트에서 같이 import하면
모듈이 충돌하기 때문에, EVAL_QUESTIONS/evaluator를 그대로 복제해서 독립 스크립트로 둔다
(질문/채점 기준을 동일하게 유지하는 게 이 복제의 목적).

실행: python evaluate_comparison.py (langgraph의 venv에서)
LangSmith에서 결과 비교: Dataset "aws-advisor-comparison-eval" 페이지에서
langgraph-v1 / single-agent-baseline-v1 / multi-agent-rag-v1 실험을 비교.
"""
import re
import uuid

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langsmith import Client
from langsmith.evaluation import evaluate

import config
from graph import build_agent_graph

DATASET_NAME = "aws-advisor-comparison-eval"

# multi-agent-rag/evaluate_comparison.py의 EVAL_QUESTIONS와 동일 - 비교 공정성을 위해 그대로 복제.
# 30문항에서 토큰 사용량 문제로 20문항(카테고리당 10개)으로 축소함 - 겹치는 주제/스타일 위주로 제외.
EVAL_QUESTIONS = [
    {
        "question": "트래픽이 거의 없는 개인 프로젝트인데 EC2, Lambda, Fargate 중 뭘 써야 해?",
        "answer": (
            "트래픽이 적고 간헐적이라면 요청 단위로만 과금되는 Lambda가 가장 경제적이다. "
            "다만 실행 시간이 15분을 넘거나 상시 연결이 필요하면 Fargate나 EC2를 고려해야 한다."
        ),
        "category": "search_only",
    },
    {
        "question": "EC2 온디맨드 대신 비용을 아끼고 싶으면 어떤 구매 옵션을 써야 해?",
        "answer": (
            "사용량이 꾸준하면 Savings Plans나 Reserved Instance로 On-Demand 대비 최대 70% 할인을 받을 수 있고, "
            "중단 가능한 워크로드면 Spot Instance로 최대 90%까지 할인받을 수 있다."
        ),
        "category": "search_only",
    },
    {
        "question": "Spot Instance는 어떤 워크로드에 적합해?",
        "answer": (
            "중단돼도 재시작 가능한 배치 작업, 데이터 분석, CI/CD 빌드처럼 내결함성이 있는 워크로드에 적합하다. "
            "상시 가용성이 필요한 프로덕션 서비스에는 부적합하다."
        ),
        "category": "search_only",
    },
    {
        "question": "Lambda Provisioned Concurrency는 언제 써야 해?",
        "answer": (
            "콜드 스타트에 민감한 지연시간 요구 서비스에서, 트래픽 패턴이 예측 가능할 때 "
            "미리 실행 환경을 준비해두는 용도로 사용한다. 상시 사용 시에는 온디맨드보다 비쌀 수 있다."
        ),
        "category": "search_only",
    },
    {
        "question": "Well-Architected Framework의 비용 최적화 기둥에서 강조하는 핵심 원칙은 뭐야?",
        "answer": "수요에 맞게 지출하기, 올바른 요금 모델 선택, 관리형 서비스 활용, 전체 비용(TCO) 측정 및 인식이 핵심 원칙이다.",
        "category": "search_only",
    },
    {
        "question": "배치 작업(batch processing)에는 어떤 컴퓨팅 서비스가 적합해?",
        "answer": "AWS Batch가 적합하다. 작업 볼륨과 요구사항에 맞게 컴퓨팅 리소스를 자동으로 프로비저닝하고 스케줄링/자원 할당을 대신 처리해준다.",
        "category": "search_only",
    },
    {
        "question": "머신러닝 학습(training)과 추론(inference)은 각각 어떤 컴퓨팅 특성이 필요해?",
        "answer": "학습은 GPU 등 고성능 연산 자원이 필요한 집중적인 단계이고, 추론은 저지연·고가용성이 필요한 상시 서비스 단계라 요구사항이 다르다.",
        "category": "search_only",
    },
    {
        "question": "Reserved Instance와 Savings Plans의 차이는 뭐야?",
        "answer": "Reserved Instance는 특정 인스턴스 구성에 대한 용량을 예약하는 방식이고, Savings Plans는 특정 컴퓨팅 사용량(달러/시간) 약정으로 인스턴스 패밀리나 리전 변경에 더 유연하게 대응할 수 있다.",
        "category": "search_only",
    },
    {
        "question": "t3, m5, c5 같은 EC2 인스턴스 패밀리는 어떤 기준으로 골라?",
        "answer": "t 시리즈는 버스터블 범용(저비용, 간헐적 워크로드), m 시리즈는 범용 균형형, c 시리즈는 컴퓨팅 최적화(CPU 집약적 워크로드)에 적합하다.",
        "category": "search_only",
    },
    {
        "question": "비용 최적화 기둥에서 '수요에 맞게 지출하기'는 구체적으로 뭘 의미해?",
        "answer": "Auto Scaling 등을 활용해 실제 필요한 만큼만 리소스를 사용하고, 사용하지 않는 유휴 리소스에 대한 지출을 줄이는 것을 의미한다.",
        "category": "search_only",
    },
    {
        "question": "Lambda로 월 100만 건 요청, 평균 실행시간 200ms, 메모리 512MB면 한 달 요금이 대략 얼마나 나와?",
        "answer": "약 $1.87 (요청 요금 $0.20 + 실행 시간 요금 $1.67).",
        "category": "needs_calc",
    },
    {
        "question": "EC2 t3.medium을 한 달 내내(730시간) 켜두면 요금이 얼마야?",
        "answer": "약 $30.37 (시간당 $0.0416 x 730시간).",
        "category": "needs_calc",
    },
    {
        "question": "Fargate에서 vCPU 0.5개, 메모리 1GB로 하루 8시간씩 한 달(30일) 운영하면 요금이 얼마나 나와?",
        "answer": "약 $5.93 (vCPU 요금 $4.86 + 메모리 요금 $1.07, 총 240시간 기준).",
        "category": "needs_calc",
    },
    {
        "question": "EC2 m5.large를 하루 12시간씩 한 달 운영하는 것과, m5.xlarge를 하루 6시간만 운영하는 것 중 어느 쪽이 더 저렴해?",
        "answer": "둘 다 약 $34.56로 동일하다 (m5.large 360시간 x $0.096 = m5.xlarge 180시간 x $0.192).",
        "category": "needs_calc",
    },
    {
        "question": "Lambda 월 500만 건 요청에 평균 100ms, 메모리 256MB로 실행하면 예상 요금은?",
        "answer": "약 $3.08 (요청 요금 $1.00 + 실행 시간 요금 $2.08).",
        "category": "needs_calc",
    },
    {
        "question": "Lambda로 월 200만 건 요청, 평균 실행시간 150ms, 메모리 1024MB(1GB)면 요금은?",
        "answer": "약 $5.40 (요청 요금 $0.40 + 실행 시간 요금 $5.00).",
        "category": "needs_calc",
    },
    {
        "question": "Fargate 1vCPU, 2GB 메모리로 하루 24시간(상시), 한 달 30일(720시간) 운영하면 요금이 얼마야?",
        "answer": "약 $35.55 (vCPU 요금 $29.15 + 메모리 요금 $6.40).",
        "category": "needs_calc",
    },
    {
        "question": "Lambda 월 10만 건 요청, 평균 500ms, 메모리 128MB면 요금은?",
        "answer": "약 $0.12 (요청 요금 $0.02 + 실행 시간 요금 $0.10).",
        "category": "needs_calc",
    },
    {
        "question": "Lambda 월 300만 건 요청, 평균 300ms, 메모리 2048MB(2GB)로 실행하면 예상 요금은?",
        "answer": "약 $30.60 (요청 요금 $0.60 + 실행 시간 요금 $30.00).",
        "category": "needs_calc",
    },
    {
        "question": "EC2 m5.xlarge를 하루 3시간만, 한 달(30일=90시간) 운영하면 요금이 얼마야?",
        "answer": "약 $17.28 (시간당 $0.192 x 90시간).",
        "category": "needs_calc",
    },
]

client = Client()


def get_or_create_dataset():
    existing = list(client.list_datasets(dataset_name=DATASET_NAME))
    if existing:
        dataset = existing[0]
        current_questions = {ex.inputs.get("question") for ex in client.list_examples(dataset_id=dataset.id)}
        missing = [ex for ex in EVAL_QUESTIONS if ex["question"] not in current_questions]
        if missing:
            client.create_examples(
                dataset_id=dataset.id,
                examples=[
                    {
                        "inputs": {"question": ex["question"]},
                        "outputs": {"answer": ex["answer"]},
                        "metadata": {"category": ex["category"]},
                    }
                    for ex in missing
                ],
            )
            print(f"기존 Dataset({dataset.id})에 신규 example {len(missing)}건 추가")
        else:
            print(f"기존 Dataset 사용, 추가할 신규 문항 없음: {dataset.id}")
        return dataset

    dataset = client.create_dataset(
        dataset_name=DATASET_NAME,
        description="langgraph(싱글, 도구1개) vs single-agent-baseline(싱글, 도구2개) vs multi-agent-rag(멀티, 도구2개) 비교용",
    )
    client.create_examples(
        dataset_id=dataset.id,
        examples=[
            {
                "inputs": {"question": ex["question"]},
                "outputs": {"answer": ex["answer"]},
                "metadata": {"category": ex["category"]},
            }
            for ex in EVAL_QUESTIONS
        ],
    )
    print(f"새 Dataset 생성 및 example {len(EVAL_QUESTIONS)}건 추가: {dataset.id}")
    return dataset


def _last_text(messages) -> str:
    """AIMessage.content가 문자열일 수도, 블록 리스트일 수도 있어 둘 다 처리한다."""
    for msg in reversed(messages):
        if not isinstance(msg, AIMessage):
            continue
        content = msg.content
        if isinstance(content, str) and content:
            return content
        if isinstance(content, list):
            text = "".join(
                part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"
            )
            if text:
                return text
    return ""


_graph = None


def target(inputs: dict) -> dict:
    global _graph
    if _graph is None:
        _graph = build_agent_graph()
    try:
        thread_id = str(uuid.uuid4())
        result = _graph.invoke(
            {"messages": [HumanMessage(content=inputs["question"])]},
            config={"configurable": {"thread_id": thread_id}},
        )
        return {"answer": _last_text(result["messages"])}
    except Exception as e:  # noqa: BLE001
        return {"answer": f"(생성 실패: {e})"}


def contains_expected_keyword(run, example):
    pred = run.outputs.get("answer", "")
    expected = example.outputs.get("answer", "")
    keywords = re.findall(r"[A-Za-z][A-Za-z0-9\-]+", expected)[:3]
    if not keywords:
        keywords = [w for w in expected.split() if len(w) >= 2][:2]
    hit = all(k in pred for k in keywords)
    return {"key": "contains_expected_keyword", "score": 1 if hit else 0, "comment": f"필수 키워드 {keywords} 포함 여부"}


def contains_dollar_amount(run, example):
    pred = run.outputs.get("answer", "")
    hit = bool(re.search(r"\$\s?\d", pred))
    return {"key": "contains_dollar_amount", "score": 1 if hit else 0, "comment": "답변에 $숫자 형태의 금액이 포함됐는지"}


_judge_llm = ChatAnthropic(model=config.GENERATION_MODEL, thinking={"type": "disabled"})
_JUDGE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "당신은 답변 품질을 평가하는 채점자입니다.\n"
            "아래 기대 답변(reference)과 모델 답변(prediction)을 비교하고,\n"
            "의미가 일치하면 1, 부분적으로만 일치하면 0.5, 무관하면 0을 점수로 매기세요.\n"
            "응답은 반드시 첫 줄에 0/0.5/1 중 하나의 숫자만, 둘째 줄부터 짧은 이유를 적으세요.",
        ),
        ("human", "질문: {question}\n\n기대 답변: {reference}\n\n모델 답변: {prediction}"),
    ]
)
_judge_chain = _JUDGE_PROMPT | _judge_llm | StrOutputParser()


def llm_judge(run, example):
    reply = _judge_chain.invoke(
        {
            "question": example.inputs.get("question", ""),
            "reference": example.outputs.get("answer", ""),
            "prediction": run.outputs.get("answer", ""),
        }
    )
    first_line = reply.strip().splitlines()[0].strip()
    try:
        score = float(first_line)
    except ValueError:
        score = 0
    return {"key": "llm_judge_semantic_match", "score": score, "comment": reply}


def run_evaluation():
    get_or_create_dataset()
    evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[contains_expected_keyword, contains_dollar_amount, llm_judge],
        experiment_prefix="langgraph-v1",
    )
    print("\n완료. LangSmith에서 Dataset 'aws-advisor-comparison-eval'의 실험들을 비교하세요.")


if __name__ == "__main__":
    run_evaluation()
