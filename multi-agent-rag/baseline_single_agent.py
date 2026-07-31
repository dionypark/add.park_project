"""비교 평가 전용 baseline — multi-agent-rag와 완전히 같은 도구(search_aws_docs, calculate_cost)를
하나의 ReAct 에이전트에 몰아넣은 싱글 에이전트 버전.

graph.py(계층형 멀티 에이전트)와 도구/모델은 완전히 동일하고 구조(supervisor+retrieval_agent+cost_agent+
synthesizer vs 에이전트 1개)만 다르게 해서, "구조 차이 자체의 효과"만 순수하게 비교하기 위한 대조군이다.
evaluate_comparison.py에서만 쓰고, FastAPI/Streamlit으로 감싸지 않는다(배포용 아님).
"""
from typing import Annotated

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

import config
from tools import calculate_cost, search_aws_docs

# graph.py의 RETRIEVAL_PROMPT + COST_PROMPT를 한 에이전트 기준으로 합친 것.
SYSTEM_PROMPT = (
    "당신은 AWS 서비스 선택과 비용 최적화를 도와주는 어드바이저입니다. "
    "필요에 따라 아래 두 도구를 상황에 맞게 사용하세요.\n"
    "- search_aws_docs: 어떤 서비스를 언제 써야 하는지, 선택 기준이나 근거가 필요할 때 검색하세요. "
    "필요하면 검색어를 바꿔가며 여러 번 검색하세요.\n"
    "- calculate_cost: 서비스명과 사용량(요청 수, 실행시간, 메모리, 인스턴스 타입 등)이 파악되면 "
    "예상 요금을 계산하세요. 사용량이 명시 안 됐으면 search_aws_docs로 참고할 만한 기준을 찾아보거나, "
    "합리적인 가정을 명시하고 계산하세요.\n"
    "문서에서 찾은 내용만 근거로 답하고 출처(파일명-섹션)를 포함하세요. "
    "계산 결과가 있으면 계산 근거와 가정을 답변에 포함하세요."
)


class State(TypedDict):
    messages: Annotated[list, add_messages]


def build_baseline_graph():
    tools = [search_aws_docs, calculate_cost]
    llm = ChatAnthropic(model=config.GENERATION_MODEL, thinking={"type": "disabled"}).bind_tools(tools)

    def agent(state: State):
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        return {"messages": [llm.invoke(messages)]}

    graph_builder = StateGraph(State)
    graph_builder.add_node("agent", agent)
    graph_builder.add_node("tools", ToolNode(tools))
    graph_builder.add_edge(START, "agent")
    graph_builder.add_conditional_edges("agent", tools_condition)
    graph_builder.add_edge("tools", "agent")

    return graph_builder.compile(checkpointer=MemorySaver())
