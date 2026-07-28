"""에이전트들이 공유해서 쓰는 도구 모음.

search_aws_docs: retrieval_agent가 씀 (벡터 검색)
calculate_cost: cost_agent가 씀 (AWS Price List API 실시간 단가 + 계산)

요금은 pricing.py를 통해 AWS Price List Bulk API에서 실시간으로 가져온다(Lambda/Fargate는
매번, EC2는 로컬 캐시를 통해). 실시간 조회가 실패하면(네트워크 문제, AWS 스키마 변경 등)
아래 하드코딩된 근사치로 폴백한다 - 이 값들은 2026-07 기준 실제 API 값과 대조 확인된 값이다.
"""
import threading

from langchain_core.tools import tool

import config
import pricing
from build_vectordb import build_vectordb

# 실시간 조회 실패 시 폴백으로 쓰는 근사치 (us-east-1, on-demand, x86 기준, 2026-07 API 대조 확인)
FALLBACK_LAMBDA_PRICE_PER_REQUEST = 0.20 / 1_000_000  # $0.20 / 100만 요청
FALLBACK_LAMBDA_PRICE_PER_GB_SECOND = 0.0000166667

FALLBACK_EC2_HOURLY_RATES = {
    "t3.micro": 0.0104,
    "t3.medium": 0.0416,
    "m5.large": 0.096,
    "m5.xlarge": 0.192,
}

FALLBACK_FARGATE_PRICE_PER_VCPU_HOUR = 0.04048
FALLBACK_FARGATE_PRICE_PER_GB_HOUR = 0.004445

_retriever = None
_retriever_lock = threading.Lock()


def _get_retriever():
    global _retriever
    if _retriever is None:
        with _retriever_lock:
            if _retriever is None:
                vectorstore = build_vectordb()
                _retriever = vectorstore.as_retriever(search_kwargs={"k": config.TOP_K})
    return _retriever


def _format_docs(docs) -> str:
    return "\n\n".join(
        f"[출처: {d.metadata.get('source', '')} - {d.metadata.get('header', '')}]\n{d.page_content}"
        for d in docs
    )


@tool
def search_aws_docs(query: str) -> str:
    """AWS 서비스 선택/비용 최적화 관련 문서를 검색한다. 질문에 답할 근거나 최신 요금 설명이 필요할 때 사용한다."""
    docs = _get_retriever().invoke(query)
    if not docs:
        return "관련 문서를 찾지 못했습니다."
    return _format_docs(docs)


@tool
def calculate_cost(
    service: str,
    monthly_requests: int = 0,
    avg_duration_ms: float = 0,
    memory_mb: int = 128,
    ec2_instance_type: str = "t3.micro",
    hours_per_month: int = 730,
    vcpu: float = 0.25,
) -> str:
    """AWS 서비스(Lambda/EC2/Fargate)의 예상 월 요금을 실제 단가 기준으로 계산한다.
    Lambda: monthly_requests, avg_duration_ms, memory_mb 사용.
    EC2: ec2_instance_type, hours_per_month 사용.
    Fargate: vcpu, memory_mb, hours_per_month 사용."""
    service = service.lower().strip()

    if service == "lambda":
        live = pricing.fetch_lambda_prices()
        source = "실시간 AWS Price List API"
        price_per_request = FALLBACK_LAMBDA_PRICE_PER_REQUEST
        price_per_gb_second = FALLBACK_LAMBDA_PRICE_PER_GB_SECOND
        if live:
            price_per_request = live["price_per_request"]
            price_per_gb_second = live["price_per_gb_second"]
        else:
            source = "근사치(실시간 조회 실패, 폴백)"

        request_cost = monthly_requests * price_per_request
        gb_seconds = monthly_requests * (avg_duration_ms / 1000) * (memory_mb / 1024)
        duration_cost = gb_seconds * price_per_gb_second
        total = request_cost + duration_cost
        return (
            f"Lambda 예상 월 요금: 약 ${total:.2f} ({source})\n"
            f"- 요청 요금: ${request_cost:.2f} ({monthly_requests:,}건 x ${price_per_request:.8f})\n"
            f"- 실행 시간 요금: ${duration_cost:.2f} ({gb_seconds:,.1f} GB-초 x ${price_per_gb_second})\n"
            f"(us-east-1, x86, on-demand 기준, 프리티어 미반영)"
        )

    if service == "ec2":
        live = pricing.fetch_ec2_prices()
        source = "실시간 AWS Price List API"
        rates = live if live else FALLBACK_EC2_HOURLY_RATES
        if not live:
            source = "근사치(실시간 조회 실패, 폴백)"

        rate = rates.get(ec2_instance_type)
        if rate is None:
            return f"'{ec2_instance_type}'은 지원하지 않는 인스턴스 타입입니다. 지원: {list(FALLBACK_EC2_HOURLY_RATES)}"
        total = rate * hours_per_month
        return (
            f"EC2({ec2_instance_type}) 예상 월 요금: 약 ${total:.2f} ({source})\n"
            f"- 시간당 ${rate} x {hours_per_month}시간\n"
            f"(us-east-1, on-demand 기준)"
        )

    if service == "fargate":
        live = pricing.fetch_fargate_prices()
        source = "실시간 AWS Price List API"
        price_per_vcpu_hour = FALLBACK_FARGATE_PRICE_PER_VCPU_HOUR
        price_per_gb_hour = FALLBACK_FARGATE_PRICE_PER_GB_HOUR
        if live:
            price_per_vcpu_hour = live["price_per_vcpu_hour"]
            price_per_gb_hour = live["price_per_gb_hour"]
        else:
            source = "근사치(실시간 조회 실패, 폴백)"

        vcpu_cost = vcpu * price_per_vcpu_hour * hours_per_month
        mem_cost = (memory_mb / 1024) * price_per_gb_hour * hours_per_month
        total = vcpu_cost + mem_cost
        return (
            f"Fargate 예상 월 요금: 약 ${total:.2f} ({source})\n"
            f"- vCPU 요금: ${vcpu_cost:.2f} ({vcpu} vCPU x {hours_per_month}시간)\n"
            f"- 메모리 요금: ${mem_cost:.2f} ({memory_mb}MB x {hours_per_month}시간)\n"
            f"(us-east-1, on-demand 기준)"
        )

    return f"'{service}'는 지원하지 않는 서비스입니다. 지원: lambda, ec2, fargate"
