"""LangGraph 기반 ReAct 에이전트.

alex-rag/graph.py는 START→retrieve→generate 고정 흐름이라 실제로는 분기가 없었다.
여기서는 검색을 Tool로 등록해서, LLM이 검색이 필요한지/몇 번 더 검색할지 스스로 판단하게 한다.
"""
from typing import Annotated

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

import config
from build_vectordb import build_vectordb

SYSTEM_PROMPT = (
    "당신은 AWS 서비스 선택과 비용 최적화를 도와주는 어드바이저입니다. "
    "필요하면 search_aws_docs 도구로 문서를 검색해서 근거를 찾은 뒤 답하세요. "
    "문서에서 찾은 내용만 근거로 답하고, 답변 끝에 참고한 출처(파일명-섹션)를 나열하세요. "
    "근거를 찾을 수 없으면 모른다고 답하세요."
)


class State(TypedDict):
    messages: Annotated[list, add_messages]


def _format_docs(docs) -> str:
    return "\n\n".join(
        f"[출처: {d.metadata.get('source', '')} - {d.metadata.get('header', '')}]\n{d.page_content}"
        for d in docs
    )


def build_search_tool():
    vectorstore = build_vectordb()
    retriever = vectorstore.as_retriever(search_kwargs={"k": config.TOP_K})

    @tool
    def search_aws_docs(query: str) -> str:
        """AWS 서비스 선택/비용 최적화 관련 문서를 검색한다. 질문에 답할 근거가 필요할 때 사용한다."""
        docs = retriever.invoke(query)
        if not docs:
            return "관련 문서를 찾지 못했습니다."
        return _format_docs(docs)

    return search_aws_docs


def build_agent_graph():
    search_aws_docs = build_search_tool()
    tools = [search_aws_docs]

    llm = ChatAnthropic(model=config.GENERATION_MODEL)
    llm_with_tools = llm.bind_tools(tools)

    def agent(state: State):
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    graph_builder = StateGraph(State)
    graph_builder.add_node("agent", agent)
    graph_builder.add_node("tools", ToolNode(tools))
    graph_builder.add_edge(START, "agent")
    graph_builder.add_conditional_edges("agent", tools_condition)
    graph_builder.add_edge("tools", "agent")

    return graph_builder.compile(checkpointer=MemorySaver())
