import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params = StdioServerParameters(command="./venv/Scripts/python.exe", args=["server.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            resources = await session.list_resources()
            print("Static resources:")
            for r in resources.resources:
                print(" -", r.uri, "|", r.name, "|", r.mimeType)

            templates = await session.list_resource_templates()
            print("\nResource templates:")
            for t in templates.resourceTemplates:
                print(" -", t.uriTemplate, "|", t.name)

            prompts = await session.list_prompts()
            print("\nPrompts:")
            for p in prompts.prompts:
                print(" -", p.name, "| args:", [a.name for a in (p.arguments or [])])

            print("\n--- read employees://all ---")
            res = await session.read_resource("employees://all")
            print(res.contents[0].text[:300])

            print("\n--- read employees://3 ---")
            res = await session.read_resource("employees://3")
            print(res.contents[0].text)

            print("\n--- get_prompt salary_review_prompt(employee_id=2) ---")
            prompt_result = await session.get_prompt("salary_review_prompt", {"employee_id": "2"})
            for m in prompt_result.messages:
                print(m.role, ":", m.content.text)


asyncio.run(main())
