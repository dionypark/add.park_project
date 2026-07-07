"""RAGAS로 RAG 파이프라인을 평가한다.

faithfulness, answer_relevancy, context_precision, context_recall을 측정한다.
"""
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness

import config
from rag_query import retrieve, answer_question

# 질문 - 정답(reference) 쌍. 각 질문이 어느 문서를 근거로 답해야 하는지 알고 있는 상태로 구성.
EVAL_SET = [
    {
        "question": "트래픽이 거의 없는 개인 프로젝트인데 EC2, Lambda, Fargate 중 뭘 써야 해?",
        "reference": (
            "트래픽이 적고 간헐적이라면 요청 단위로만 과금되는 Lambda가 가장 경제적이다. "
            "다만 실행 시간이 15분을 넘거나 상시 연결이 필요하면 Fargate나 EC2를 고려해야 한다."
        ),
    },
    {
        "question": "EC2에서 비용을 아끼려면 어떤 요금제를 선택해야 해?",
        "reference": (
            "사용량이 꾸준하면 Reserved Instance나 Savings Plans로 On-Demand 대비 최대 70% 할인을 받을 수 있고, "
            "중단 가능한 상태 없는 작업이면 Spot Instance로 최대 90%까지 할인받을 수 있다."
        ),
    },
    {
        "question": "Lambda의 콜드 스타트란 뭐고 왜 문제가 될 수 있어?",
        "reference": (
            "콜드 스타트는 오랜만에 함수가 호출될 때 초기화 지연이 발생하는 현상으로, "
            "트래픽이 낮은 서비스에서 응답 지연에 민감한 경우 사용자 경험에 영향을 줄 수 있다."
        ),
    },
    {
        "question": "Well-Architected Framework의 비용 최적화 기둥에서 강조하는 핵심 원칙은 뭐야?",
        "reference": (
            "수요에 맞게 지출하기, 올바른 요금 모델 선택, 관리형 서비스 활용, 전체 비용(TCO) 측정 및 인식이 핵심 원칙이다."
        ),
    },
    {
        "question": "이미 Docker 컨테이너로 패키징된 앱을 서버 관리 없이 돌리고 싶으면 뭘 써야 해?",
        "reference": (
            "AWS Fargate를 사용하면 ECS/EKS에서 컨테이너를 실행할 때 EC2 인스턴스를 직접 관리하지 않아도 된다."
        ),
    },
]


def build_dataset() -> EvaluationDataset:
    samples = []
    for item in EVAL_SET:
        question = item["question"]
        hits = retrieve(question)
        result = answer_question(question)
        samples.append(
            SingleTurnSample(
                user_input=question,
                retrieved_contexts=[h["text"] for h in hits],
                response=result["answer"],
                reference=item["reference"],
            )
        )
    return EvaluationDataset(samples=samples)


def run_evaluation():
    dataset = build_dataset()

    judge_llm = LangchainLLMWrapper(
        ChatGoogleGenerativeAI(model=config.GENERATION_MODEL, google_api_key=config.GOOGLE_API_KEY)
    )
    judge_embeddings = LangchainEmbeddingsWrapper(
        GoogleGenerativeAIEmbeddings(model=f"models/{config.EMBEDDING_MODEL}", google_api_key=config.GOOGLE_API_KEY)
    )

    result = evaluate(
        dataset=dataset,
        metrics=[Faithfulness(), AnswerRelevancy(), ContextPrecision(), ContextRecall()],
        llm=judge_llm,
        embeddings=judge_embeddings,
    )

    df = result.to_pandas()
    print(df)
    df.to_csv("ragas_results.csv", index=False)
    print("\n평균 점수:")
    print(df[["faithfulness", "answer_relevancy", "context_precision", "context_recall"]].mean())


if __name__ == "__main__":
    run_evaluation()
