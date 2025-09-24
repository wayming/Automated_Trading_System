class StockMCPAgent:
    """基于 LangChain 的 MCP Agent"""
    
    def __init__(self, server_command: list = ["python", sys.argv[0], "server"]):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)
        self.client = MCPClient("stdio", server_command=server_command)
        self.parser = JsonOutputParser()
        self.tools = None

    async def initialize(self):
        """初始化：连接 MCP 客户端，获取工具列表并绑定到 LLM"""
        await self.client.connect()
        tools_response = await self.client.list_tools()
        self.tools = tools_response.get("tools", [])
        self.llm = self.llm.bind_tools([
            {"name": tool["name"], "parameters": tool["inputSchema"]} for tool in self.tools
        ])

    async def invoke(self, user_input: str):
        """处理用户输入，支持多轮工具调用"""
        try:
            await self.initialize()
            current_input = user_input
            messages = [ChatPromptTemplate.from_messages([
                ("system", "你是股票分析助手，基于新闻和数据预测趋势。输出 JSON 格式：{'stock_symbol': 'string', 'prediction': 'string', 'reason': 'string'}"),
                ("user", "{input}")
            ]).format_messages(input=current_input)]
            results = []

            while True:
                response = await self.llm.ainvoke(messages)
                if not response.tool_calls:
                    return self.parser.parse(response.content), None

                for call in response.tool_calls:
                    tool_name = call["name"]
                    tool_args = call["args"]
                    try:
                        result = await self.client.call_tool(tool_name, tool_args)
                        results.append(result)
                    except Exception as e:
                        results.append({"error": f"Tool {tool_name} failed: {str(e)}"})

                current_input = f"{user_input}\n工具结果: {json.dumps(results, ensure_ascii=False)}"
                messages = [ChatPromptTemplate.from_messages([
                    ("system", "你是股票分析助手，基于新闻和数据预测趋势。输出 JSON 格式：{'stock_symbol': 'string', 'prediction': 'string', 'reason': 'string'}"),
                    ("user", "{input}")
                ]).format_messages(input=current_input)]

        except Exception as e:
            return None, f"Agent failed: {str(e)}"
        finally:
            await self.client.disconnect()

# ======================== 主程序 ========================

async def run_server():
    """运行 MCP 服务器"""
    db_connection = "postgresql://user:pass@localhost/stock_db"  # 替换为实际连接字符串
    server = StockMCPServer(db_connection)
    await server.run_stdio()  # 使用 stdio 传输，与客户端兼容

async def run_agent(news_text: str):
    """运行 Agent 并处理新闻输入"""
    agent = StockMCPAgent()
    result, error = await agent.invoke(news_text)
    if error:
        print(f"错误: {error}")
    else:
        print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        asyncio.run(run_server())
    elif len(sys.argv) > 2 and sys.argv[1] == "agent":
        asyncio.run(run_agent(sys.argv[2]))
    else:
        print("用法: python this_file.py server  # 运行服务器")
        print("     python this_file.py agent '新闻文本'  # 运行 Agent 示例")