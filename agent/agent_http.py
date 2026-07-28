import asyncio
import os
import sys

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI

load_dotenv(override=True)

MCP_HTTP_URL = os.environ.get("MCP_HTTP_URL", "http://127.0.0.1:8500/mcp")
MCP_API_KEY = os.environ["MCP_API_KEY"]


async def build_agent():
    model = ChatOpenAI(
        model=os.environ["COMPASS_MODEL"],
        base_url=os.environ["COMPASS_BASE_URL"],
        api_key=os.environ["COMPASS_API_KEY"],
    )

    mcp_client = MultiServerMCPClient(
        {
            "employee_salary": {
                "transport": "streamable_http",
                "url": MCP_HTTP_URL,
                "headers": {"Authorization": f"Bearer {MCP_API_KEY}"},
            }
        }
    )
    tools = await mcp_client.get_tools()

    return create_agent(model, tools)


async def main():
    agent = await build_agent()
    print("Connected. Ask a question about employees/salaries (Ctrl+C to quit).\n")

    while True:
        question = input("> ").strip()
        if not question:
            continue
        result = await agent.ainvoke({"messages": [("user", question)]})
        print(result["messages"][-1].content, "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
