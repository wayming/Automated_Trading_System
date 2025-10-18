from fastmcp import Client  # 而不是 FastMCPClient
import asyncio
import os

async def main():
    # MCP endpoint
    async with Client(f"http://localhost:{os.getenv('MCP_SERVER_PORT', 50057)}/mcp") as client:
        # List tools
        tools = await client.list_tools()
        print("Tools:", tools)
        # Call tool
        res = await client.call_tool("get_similar_articles", {"article_content": "测试内容"})
        print("Result:", res)

if __name__ == "__main__":
    asyncio.run(main())
