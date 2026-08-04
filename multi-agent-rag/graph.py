"""Multi-Agent RAG — 계층형(Hierarchical) 멀티 에이전트.

supervisor(판단만) -> retrieval_agent / cost_agent(둘 다 자기만의 ReAct 루프를 가진 진짜 에이전트,
필요하면 병렬 실행) -> synthesizer(둘 다 실행됐을 때만 실제로 LLM 호출해서 합침, 아니면 그대로 통과).

alex-rag/graph.py, langgraph/graph.py는 둘 다 "에이전트 1개"였는데, 여기서는
판단(supervisor)과 실행(retrieval_agent, cost_agent)을 서로 다른 에이전트로 분리했다.
"""
import os
import sqlite3
from typing import Annotated

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel
from typing_extensions import TypedDict

import config
from tools import calculate_cost, search_aws_docs

CHECKPOINT_DB_PATH = os.path.join(config.BASE_DIR, "checkpoints.sqlite")


class State(TypedDict):
    messages: Annotated[list, add_messages]
    needs_search: bool
    needs_calculation: bool
    search_result: str
    cost_result: str


class SubState(TypedDict):
    messages: Annotated[list, add_messages]


def _last_text(messages) -> str:
    """AIMessage.content가 문자열일 수도, (확장 사고 등) 블록 리스트일 수도 있어 둘 다 처리한다."""
    for msg in reversed(messages):
        if not isinstance(msg, AIMessage):
            continue
        content = msg.content
        if isinstance(content, str) and content:
            return content
        if isinstance(content, list):
            text = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
            if text:
                return text
    return ""


# ---------------------------------------------------------------------------
# retrieval_agent: 문서 검색 전담. 자기 안에서 검색을 몇 번이고 반복할 수 있음.
# ---------------------------------------------------------------------------

RETRIEVAL_PROMPT = (
    "당신은 AWS 문서 검색 전문가입니다. search_aws_docs 도구로 질문과 관련된 근거를 찾아 답하세요. "
    "필요하면 검색어를 바꿔가며 여러 번 검색하세요. 문서에서 찾은 내용만 근거로 답하고, "
    "출처(파일명-섹션)를 답변에 포함하세요."
)


def build_retrieval_subgraph():
    llm = ChatAnthropic(model=config.GENERATION_MODEL, thinking={"type": "disabled"}).bind_tools(
        [search_aws_docs]
    )

    def agent(state: SubState):
        messages = [SystemMessage(content=RETRIEVAL_PROMPT), *state["messages"]]
        return {"messages": [llm.invoke(messages)]}

    g = StateGraph(SubState)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode([search_aws_docs]))
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", tools_condition)
    g.add_edge("tools", "agent")
    return g.compile()


# ---------------------------------------------------------------------------
# cost_agent: 요금 계산 전담. 최신 단가가 필요하면 검색도 하고, 계산도 함.
# ---------------------------------------------------------------------------

COST_PROMPT = (
    "당신은 AWS 요금 계산 전문가입니다. 질문에서 서비스명과 사용량(요청 수, 실행시간, 메모리, "
    "인스턴스 타입 등)을 파악해서 calculate_cost 도구로 예상 요금을 계산하세요. "
    "사용량이 명시 안 됐으면 search_aws_docs로 참고할 만한 기준을 찾아보거나, "
    "합리적인 가정을 명시하고 계산하세요. 계산 결과와 그 가정을 답변에 포함하세요."
)


def build_cost_subgraph():
    tools = [search_aws_docs, calculate_cost]
    llm = ChatAnthropic(model=config.GENERATION_MODEL, thinking={"type": "disabled"}).bind_tools(tools)

    def agent(state: SubState):
        messages = [SystemMessage(content=COST_PROMPT), *state["messages"]]
        return {"messages": [llm.invoke(messages)]}

    g = StateGraph(SubState)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode(tools))
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", tools_condition)
    g.add_edge("tools", "agent")
    return g.compile()


_retrieval_graph = None
_cost_graph = None


def _get_retrieval_graph():
    global _retrieval_graph
    if _retrieval_graph is None:
        _retrieval_graph = build_retrieval_subgraph()
    return _retrieval_graph


def _get_cost_graph():
    global _cost_graph
    if _cost_graph is None:
        _cost_graph = build_cost_subgraph()
    return _cost_graph


def retrieval_agent_node(state: State, config):
    # config를 그대로 넘겨야 서브그래프 내부 LLM 호출의 스트리밍 이벤트가
    # 바깥쪽 그래프의 astream_events로 전파된다.
    result = _get_retrieval_graph().invoke({"messages": state["messages"]}, config)
    return {"search_result": _last_text(result["messages"])}


def cost_agent_node(state: State, config):
    result = _get_cost_graph().invoke({"messages": state["messages"]}, config)
    return {"cost_result": _last_text(result["messages"])}


# ---------------------------------------------------------------------------
# supervisor: 판단만 함, 직접 답을 만들지 않음.
# ---------------------------------------------------------------------------

class RouteDecision(BaseModel):
    needs_search: bool
    needs_calculation: bool


SUPERVISOR_PROMPT = (
    "사용자 질문을 보고, AWS 문서 검색이 필요한지(needs_search)와 요금 계산이 필요한지"
    "(needs_calculation)를 판단하세요. 단순 인사말 등 둘 다 불필요하면 둘 다 false로 두세요."
)

_router_llm = None


def _get_router_llm():
    global _router_llm
    if _router_llm is None:
        _router_llm = ChatAnthropic(
            model=config.GENERATION_MODEL, thinking={"type": "disabled"}
        ).with_structured_output(RouteDecision)
    return _router_llm


def supervisor(state: State, config):
    question = state["messages"][-1].content
    decision = _get_router_llm().invoke(
        [SystemMessage(content=SUPERVISOR_PROMPT), ("human", question)], config
    )
    return {
        "needs_search": decision.needs_search,
        "needs_calculation": decision.needs_calculation,
        "search_result": "",
        "cost_result": "",
    }


def route_from_supervisor(state: State):
    dests = []
    if state["needs_search"]:
        dests.append("retrieval_agent")
    if state["needs_calculation"]:
        dests.append("cost_agent")
    return dests or ["retrieval_agent"]  # 둘 다 아니면 기본으로 검색 시도


# ---------------------------------------------------------------------------
# synthesizer: 둘 다 실행됐을 때만 실제로 LLM을 불러 합침. 하나만 실행됐으면 그대로 통과.
# ---------------------------------------------------------------------------

SYNTHESIZER_PROMPT = (
    "아래는 서로 다른 전문가 에이전트가 만든 결과입니다. 이를 하나의 자연스러운 답변으로 종합하세요.\n\n"
    "[검색 결과]\n{search_result}\n\n[계산 결과]\n{cost_result}"
)

_synth_llm = None


def _get_synth_llm():
    global _synth_llm
    if _synth_llm is None:
        _synth_llm = ChatAnthropic(model=config.GENERATION_MODEL, thinking={"type": "disabled"})
    return _synth_llm


def synthesizer(state: State, config):
    search_result = state.get("search_result", "")
    cost_result = state.get("cost_result", "")

    if search_result and cost_result:
        prompt = SYNTHESIZER_PROMPT.format(search_result=search_result, cost_result=cost_result)
        response = _get_synth_llm().invoke([HumanMessage(content=prompt)], config)
        final_text = _last_text([response]) or (
            response.content if isinstance(response.content, str) else str(response.content)
        )
    else:
        final_text = search_result or cost_result or "답변을 생성하지 못했습니다."

    return {"messages": [AIMessage(content=final_text)]}


def build_agent_graph(checkpointer=None):
    """checkpointer를 안 넘기면 동기용 SqliteSaver를 기본으로 만든다(평가 스크립트처럼
    이벤트 루프 없이 그냥 .invoke()만 쓰는 경우). FastAPI처럼 .astream_events() 같은
    비동기 메서드를 쓰려면, AsyncSqliteSaver를 만들어서 직접 넘겨줘야 한다 - SqliteSaver는
    동기 메서드만 지원해서 비동기 실행 중에 체크포인트를 못 남기고 에러가 난다."""
    graph_builder = StateGraph(State)
    graph_builder.add_node("supervisor", supervisor)
    graph_builder.add_node("retrieval_agent", retrieval_agent_node)
    graph_builder.add_node("cost_agent", cost_agent_node)
    graph_builder.add_node("synthesizer", synthesizer)

    graph_builder.add_edge(START, "supervisor")
    graph_builder.add_conditional_edges(
        "supervisor", route_from_supervisor, ["retrieval_agent", "cost_agent"]
    )
    graph_builder.add_edge("retrieval_agent", "synthesizer")
    graph_builder.add_edge("cost_agent", "synthesizer")

    if checkpointer is None:
        # SqliteSaver.from_conn_string()은 컨텍스트 매니저라 with 블록을 벗어나면 연결을 닫아버린다.
        # 프로세스가 사는 동안 계속 열려있어야 하니, sqlite3.connect를 직접 해서 넘긴다
        # (check_same_thread=False: 평가 스크립트가 여러 스레드에서 이 연결을 쓸 수 있어야 함).
        conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        checkpointer.setup()
    return graph_builder.compile(checkpointer=checkpointer)
