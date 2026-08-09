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
from langgraph.errors import GraphRecursionError
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
    "당신은 AWS/서버 운영 어드바이저입니다. search_aws_docs 도구로 질문과 관련된 근거를 먼저 찾아보세요. "
    "**검색은 최대 2번까지만 시도하세요** (검색어를 한 번 바꿔서 재시도하는 것까지만 - 그 이상 계속 "
    "검색어를 바꿔가며 재시도하지 마세요). 2번 검색해도 명확한 근거를 못 찾으면 검색을 그만두고, 아래 "
    "'일반 지식으로 보완' 지침에 따라 답변을 마무리하세요 - 완벽한 근거를 찾을 때까지 검색을 반복하지 "
    "않는 것이 중요합니다. 문서에서 찾은 내용은 반드시 출처(파일명-섹션)를 밝히고 인용하세요.\n"
    "검색 문서에 없는 내용이라도 질문에 답할 수 있는 지식이 있으면(예: 특정 AWS 서비스가 뭔지, S3/EBS "
    "같은 서비스 개념, Docker/systemd/swap 메모리 설정 등 서버 운영/DevOps 지식) 알고 있는 대로 답하되, "
    "그 부분은 '(문서 근거 없음, 일반 지식)'이라고 명확히 표시해서 검색 결과와 구분하세요. "
    "모르는 내용을 지어내지는 마세요 - 정말 모르면 모른다고 하세요.\n"
    "질문이 '이런 서비스를 만들려는데 뭘 써야 하나'처럼 전체 아키텍처를 묻는다면, 필요한 AWS 서비스들과 "
    "구체적인 설정 옵션(인스턴스 타입, 스토리지 종류/용량, 리전 등)까지 구체적으로 추천하세요 - "
    "'EC2가 필요합니다' 정도로 뭉뚱그리지 말고, 그 프로젝트 규모에 맞는 실제 선택지를 제시하세요."
)


def build_retrieval_subgraph():
    llm = ChatAnthropic(model=config.GENERATION_MODEL, thinking={"type": "disabled"}, max_tokens=4096).bind_tools(
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
    "사용량이 명시 안 됐으면 search_aws_docs로 참고할 만한 기준을 **최대 2번까지만** 찾아보고, 그래도 "
    "안 나오면 검색을 그만두고 합리적인 가정을 명시해서 계산하세요 (완벽한 근거를 찾을 때까지 검색을 "
    "반복하지 마세요). 계산 결과와 그 가정을 답변에 포함하세요.\n"
    "질문이 '이런 서비스를 만들려는데 뭘 써야 하고 얼마 드는지'처럼 프로젝트 전체를 설명하며 여러 "
    "서비스가 필요한 경우, 구성요소별로 calculate_cost를 각각 반복 호출해서 항목별 요금을 구하고 "
    "마지막에 합계를 제시하세요. calculate_cost는 lambda/ec2/fargate만 지원합니다 - S3, RDS, "
    "DynamoDB, CloudFront 등 지원하지 않는 서비스는 일반적으로 알려진 단가로 대략 추정하되, 반드시 "
    "'(대략적 추정치, 실시간 API 아님)'이라고 표시해서 calculate_cost의 정확한 값과 구분하세요."
)


def build_cost_subgraph():
    tools = [search_aws_docs, calculate_cost]
    llm = ChatAnthropic(model=config.GENERATION_MODEL, thinking={"type": "disabled"}, max_tokens=4096).bind_tools(tools)

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


# 프롬프트로 "검색 최대 2번"이라고 지시해도 모델이 안 지킬 때를 대비한 하드 제한.
# 서브그래프는 agent->tools->agent->tools->... 순으로 도는데, 이 값은 "노드 실행 횟수"라서
# agent 3번 + tools 2번 정도(검색 2번 + 최종 답변 1번)면 넉넉하고, 그 이상이면 완전히 막힌 것으로 보고 끊는다.
_SUBGRAPH_RECURSION_LIMIT = 8


def retrieval_agent_node(state: State, config):
    # config를 그대로 넘겨야 서브그래프 내부 LLM 호출의 스트리밍 이벤트가
    # 바깥쪽 그래프의 astream_events로 전파된다. recursion_limit만 낮춰서 얹는다.
    sub_config = {**config, "recursion_limit": _SUBGRAPH_RECURSION_LIMIT}
    try:
        result = _get_retrieval_graph().invoke({"messages": state["messages"]}, sub_config)
        return {"search_result": _last_text(result["messages"])}
    except GraphRecursionError:
        return {"search_result": "검색을 여러 번 시도했지만 명확한 근거를 찾지 못했어요. 질문을 조금 더 구체적으로 해주시면 도움이 될 것 같아요."}


def cost_agent_node(state: State, config):
    sub_config = {**config, "recursion_limit": _SUBGRAPH_RECURSION_LIMIT}
    try:
        result = _get_cost_graph().invoke({"messages": state["messages"]}, sub_config)
        return {"cost_result": _last_text(result["messages"])}
    except GraphRecursionError:
        return {"cost_result": "계산에 필요한 근거를 찾는 데 반복 검색이 너무 길어져서 중단했어요. 인스턴스 타입이나 사용량을 좀 더 구체적으로 알려주시면 다시 계산해볼게요."}


# ---------------------------------------------------------------------------
# supervisor: 판단만 함, 직접 답을 만들지 않음.
# ---------------------------------------------------------------------------

class RouteDecision(BaseModel):
    needs_search: bool
    needs_calculation: bool


SUPERVISOR_PROMPT = (
    "사용자 질문을 보고 두 가지를 판단하세요.\n"
    "- needs_search: '언제/왜 이 서비스를 써야 하는지', '어떤 옵션이 있는지', '이게 뭔지', "
    "'어떻게 설정/운영하는지' 같은 개념/가이드/서버 운영 정보가 필요하면 true. AWS 서비스 자체에 대한 "
    "질문뿐 아니라 배포/운영/DevOps 관련 질문(예: 메모리 부족 대응, 프로세스 재시작 설정 등)도 포함한다.\n"
    "- needs_calculation: 구체적인 요금/비용/가격이 궁금한 질문이면 true. '계산해줘'라고 명시적으로 "
    "말하지 않아도 된다 - '얼마 나와', '비용이 얼마', '한 달에 얼마', '켜두면 얼마', '나가는지' 처럼 "
    "금액을 묻는 뉘앙스가 있으면 needs_calculation=true로 판단한다. 인스턴스 타입, 사용 시간, 요청 수 "
    "등 계산에 쓸 수 있는 구체적인 조건이 같이 언급되면 needs_calculation일 가능성이 특히 높다.\n"
    "두 값은 동시에 true일 수 있다 (예: '이 상황엔 뭘 써야 하고 얼마나 나와?' -> 둘 다 true, "
    "'이런 서비스를 만들려는데 뭘 써야 하고 비용은 어느 정도일지 알려줘'처럼 프로젝트 설명 + 설계 추천 "
    "+ 견적을 같이 요구하는 경우도 둘 다 true). 단순 인사말처럼 둘 다 불필요하면 둘 다 false로 둔다."
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
    "아래는 서로 다른 전문가 에이전트가 만든 결과입니다. 이를 하나의 자연스러운 답변으로 종합하세요. "
    "서비스/아키텍처 추천과 비용 산정이 같이 필요한 질문이라면, ① 추천 서비스/설정을 먼저 정리하고 "
    "② 그다음 항목별 예상 비용과 합계를 표나 목록으로 깔끔하게 정리하세요.\n\n"
    "[검색 결과]\n{search_result}\n\n[계산 결과]\n{cost_result}"
)

_synth_llm = None


def _get_synth_llm():
    global _synth_llm
    if _synth_llm is None:
        _synth_llm = ChatAnthropic(model=config.GENERATION_MODEL, thinking={"type": "disabled"}, max_tokens=4096)
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
