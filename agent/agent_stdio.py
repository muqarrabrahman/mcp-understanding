import asyncio
import os
import pathlib
import sys

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

load_dotenv(override=True)

PROJECT_ROOT = pathlib.Path(__file__).parent.parent


async def build_agent():
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
