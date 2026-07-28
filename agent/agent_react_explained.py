import asyncio
import os
import pathlib
import sys

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

load_dotenv(override=True)

PROJECT_ROOT = pathlib.Path(__file__).parent.parent

# The graph built below (confirmed via app.get_graph()):
#
#      __start__
#          |
#          v
#      +-------+
#      | agent |<--------------+
#      |(reason)|               |
#      +---+---+               |
#          | tool_calls?       |
#      +---+----+              |
#      |        |              |
#     yes       no             |
#      |        |              |
#      v        v              |
#  +-------+  __end__          |
#  | tools |                   |
#  |(act)  |-------------------+
#  +-------+
#
# agent -> tools happens when the LLM's last message has tool_calls.
# agent -> __end__ happens when it doesn't (final answer, loop stops).
# tools -> agent is unconditional: after acting, always go back to reasoning.


async def build_graph():
    model = ChatOpenAI(
        model=os.environ["COMPASS_MODEL"],
        base_url=os.environ["COMPASS_BASE_URL"],
        api_key=os.environ["COMPASS_API_KEY"],
    )

    mcp_client = MultiServerMCPClient(
        {
            "employee_salary": {
                "transport": "stdio",
                "command": str(PROJECT_ROOT / "venv" / "Scripts" / "python.exe"),
                "args": [str(PROJECT_ROOT / "server_stdio.py")],
            }
        }
    )
    tools = await mcp_client.get_tools()
    model_with_tools = model.bind_tools(tools)

    # --- the "Reason" half of ReAct: ask the LLM what to do next ---
    def agent_node(state):
        response = model_with_tools.invoke(state["messages"])
        if response.tool_calls:
            names = [call["name"] for call in response.tool_calls]
            print(f"[agent node] reasoned that it needs tool(s): {names}")
        else:
            print("[agent node] reasoned that it already has the final answer")
        return {"messages": [response]}

    # --- the routing decision: loop back to acting, or stop? ---
    def route_after_agent(state):
        last_message = state["messages"][-1]
        return "tools" if last_message.tool_calls else END

    # --- the "Act" half of ReAct: actually run whatever tool(s) were requested ---
    tools_node = ToolNode(tools)

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")  # after acting, go back to reasoning

    return graph.compile()


async def main():
    app = await build_graph()
    print("Connected. Ask a question about employees/salaries (Ctrl+C to quit).\n")

    while True:
        question = input("> ").strip()
        if not question:
            continue
        result = await app.ainvoke({"messages": [("user", question)]})
        print("\n[final answer]", result["messages"][-1].content, "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
