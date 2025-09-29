from fastmcp import Client  # 而不是 FastMCPClient
import asyncio
import os

async def main():
    # URL 指向你的 MCP 服务器 endpoint
    async with Client(f"http://localhost:{os.getenv('MCP_SERVER_PORT', 50057)}/mcp") as client:
        # 列出工具
        tools = await client.list_tools()
        print("Tools:", tools)
        # 调用工具
        res = await client.call_tool("get_similar_articles", {"article_content": "测试内容"})
        print("Result:", res)

if __name__ == "__main__":
    asyncio.run(main())
