from news_analyser.agent import Agent
from news_analyser.providers import DeepSeekProvider
import asyncio
import json
from langchain_core.messages import BaseMessage

async def main():
    agent = Agent(DeepSeekProvider())
    response, error = await agent.invoke(
"""
Understanding 
""")

    # # Convert result to JSON-serializable format
    # def make_serializable(data):
    #     if isinstance(data, dict):
    #         return {k: make_serializable(v) for k, v in data.items()}
    #     elif isinstance(data, list):
    #         return [make_serializable(item) for item in data]
    #     elif isinstance(data, BaseMessage):
    #         return data.dict()  # Convert AIMessage/HumanMessage to dict
    #     return data

    # serializable_result = make_serializable(result)
    print(response)
    print(error)

if __name__ == "__main__":
    asyncio.run(main())
