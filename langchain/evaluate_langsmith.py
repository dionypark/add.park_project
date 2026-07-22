"""LangSmith로 체인 실행을 Tracing하고 Dataset 기반으로 평가한다.

LANGCHAIN_TRACING_V2=true, LANGCHAIN_API_KEY가 .env에 설정되어 있어야 한다.
"""
import re

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langsmith import Client
from langsmith.evaluation import evaluate

import config
from rag_query import answer_question

DATASET_NAME = "langchain-aws-advisor-eval"

# 질문 - 정답(reference) 쌍. vanilla-rag의 평가셋과 동일하게 맞춰 두 단계 결과를 비교할 수 있게 함.
EVAL_QUESTIONS = [
    {
        "question": "트래픽이 거의 없는 개인 프로젝트인데 EC2, Lambda, Fargate 중 뭘 써야 해?",
        "answer": (
            "트래픽이 적고 간헐적이라면 요청 단위로만 과금되는 Lambda가 가장 경제적이다. "
            "다만 실행 시간이 15분을 넘거나 상시 연결이 필요하면 Fargate나 EC2를 고려해야 한다."
        ),
    },
    {
        "question": "EC2에서 비용을 아끼려면 어떤 요금제를 선택해야 해?",
        "answer": (
            "사용량이 꾸준하면 Reserved Instance나 Savings Plans로 On-Demand 대비 최대 70% 할인을 받을 수 있고, "
            "중단 가능한 상태 없는 작업이면 Spot Instance로 최대 90%까지 할인받을 수 있다."
        ),
    },
    {
        "question": "Lambda의 콜드 스타트란 뭐고 왜 문제가 될 수 있어?",
        "answer": (
            "콜드 스타트는 오랜만에 함수가 호출될 때 초기화 지연이 발생하는 현상으로, "
            "트래픽이 낮은 서비스에서 응답 지연에 민감한 경우 사용자 경험에 영향을 줄 수 있다."
        ),
    },
    {
        "question": "Well-Architected Framework의 비용 최적화 기둥에서 강조하는 핵심 원칙은 뭐야?",
        "answer": "수요에 맞게 지출하기, 올바른 요금 모델 선택, 관리형 서비스 활용, 전체 비용(TCO) 측정 및 인식이 핵심 원칙이다.",
    },
    {
        "question": "이미 Docker 컨테이너로 패키징된 앱을 서버 관리 없이 돌리고 싶으면 뭘 써야 해?",
        "answer": "AWS Fargate를 사용하면 ECS/EKS에서 컨테이너를 실행할 때 EC2 인스턴스를 직접 관리하지 않아도 된다.",
    },
]

client = Client()


def get_or_create_dataset():
    existing = list(client.list_datasets(dataset_name=DATASET_NAME))
    if existing:
        print(f"기존 Dataset 사용: {existing[0].id}")
        return existing[0]

    dataset = client.create_dataset(dataset_name=DATASET_NAME, description="AWS 어드바이저 RAG 답변 품질 평가용")
    client.create_examples(
        dataset_id=dataset.id,
        inputs=[{"question": ex["question"]} for ex in EVAL_QUESTIONS],
        outputs=[{"answer": ex["answer"]} for ex in EVAL_QUESTIONS],
    )
    print(f"새 Dataset 생성 및 example {len(EVAL_QUESTIONS)}건 추가: {dataset.id}")
    return dataset


def target(inputs: dict) -> dict:
    try:
        return {"answer": answer_question(inputs["question"])["answer"]}
    except Exception as e:  # noqa: BLE001
        # target()이 실패해도 run.outputs에 "answer" 키가 항상 있어야 평가자들이 안전하게 접근할 수 있다.
        return {"answer": f"(생성 실패: {e})"}


def contains_expected_keyword(run, example):
    pred = run.outputs.get("answer", "")
    expected = example.outputs.get("answer", "")
    # 기대 답변에서 영문/숫자 기술 용어(예: Lambda, EC2, TCO)를 우선 키워드로 뽑는다.
    # 한국어 조사가 안 붙는 고유명사라 채점이 훨씬 안정적이다. 없으면 기존 방식으로 대체.
    keywords = re.findall(r"[A-Za-z][A-Za-z0-9\-]+", expected)[:3]
    if not keywords:
        keywords = [w for w in expected.split() if len(w) >= 2][:2]
    hit = all(k in pred for k in keywords)
    return {"key": "contains_expected_keyword", "score": 1 if hit else 0, "comment": f"필수 키워드 {keywords} 포함 여부"}


_judge_llm = ChatAnthropic(model=config.GENERATION_MODEL)
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
    result = evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[contains_expected_keyword, llm_judge],
        experiment_prefix="langchain-v1",
    )
    print(result)


if __name__ == "__main__":
    run_evaluation()
