import operator
import json
from typing import Annotated, Optional, TypedDict
from langchain_core.messages import HumanMessage, AIMessage
from typing import List
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from news_analyser.tooling import get_prices, get_indicators
from news_analyser.providers import LLMProvider
from news_analyser.prompts_template import *
from news_analyser.output_schema import *
from langchain_core.runnables import RunnableSequence
from langchain_core.output_parsers import JsonOutputParser

class AgentState(TypedDict):
    messages: Annotated[List[HumanMessage | AIMessage], operator.add]
    news_text: str
    affected_stock: Optional[str]
    prices: Optional[dict]
    indicators: Optional[dict]
    response: Optional[dict]
    error: Optional[str]

class Agent:
    def __init__(self, provider: LLMProvider):
        self.state = AgentState(messages=[], news_text="", affected_stock=None, prices=None, response=None)
        self.provider = provider
        self.llm = ChatOpenAI(
            model=provider.model_name,
            base_url=provider.base_url,
            api_key=provider.api_key)
        self.llm.bind_tools([get_prices, get_indicators])
        self.llm_identify = self.llm | JsonOutputParser()
        self.llm_predict = self.llm | JsonOutputParser()
        self.graph_builder = StateGraph(AgentState)
        self.graph_builder.add_node("agent_node", self.agent_node)
        self.graph_builder.add_node("tool_call_node", self.tool_call_node)
        self.graph_builder.add_node("prediction_node", self.prediction_node)
        self.graph_builder.set_entry_point("agent_node")
        self.graph_builder.add_edge("agent_node", "tool_call_node")
        self.graph_builder.add_edge("tool_call_node", "prediction_node")
        self.graph_builder.add_edge("prediction_node", END)
        self.graph = self.graph_builder.compile()

    async def invoke(self, news_text: str):
        """ invoke agent with news text """
        initial_state = AgentState(messages=[], news_text=news_text, affected_stock=None, prices=None, response=None)
        return await self.graph.ainvoke(initial_state)

    async def agent_node(self, state: AgentState):
        """ identify stock and call tool """
        formatted_prompt = IDENTIFY_PROMPT.format_prompt(
            news_text=state["news_text"],
            stock_identification_output_schema=json.dumps(STOCK_IDENTIFICATION_OUTPUT_SCHEMA, ensure_ascii=False)
        )
        try:
            print(formatted_prompt.to_messages())
            response = await self.llm_identify.ainvoke(formatted_prompt.to_messages())
            state["affected_stock"] = response["stock_symbol"]
            
            print(response)

            if not state["affected_stock"]:
                return {
                    "messages": [AIMessage(content="failed to identify stock")],
                    "error": "failed to identify stock"
                }

            tool_call = AIMessage(
                content="",
                tool_calls=[{
                    "name": "get_prices",
                    "args": {"stock_symbol": response["stock_symbol"]},
                    "id": "call_stock_info"
                }, {
                    "name": "get_indicators",
                    "args": {"stock_symbol": response["stock_symbol"]},
                    "id": "call_indicators"
                }]
            )
            return {"messages": [tool_call]}
        except Exception as e:
            return {
                "messages": [AIMessage(content=f"failed to identify stock: {str(e)}")],
                "error": "failed to identify stock"
            }

    async def tool_call_node(self, state: AgentState):
        """ tool call node: execute tool and store data """

        if state["error"]:
            return {"messages": [AIMessage(content="error: " + state["error"])]}

        last_message = state["messages"][-1]
        tool_calls = last_message.tool_calls if hasattr(last_message, "tool_calls") else []
        
        if not tool_calls:
            return {"messages": [AIMessage(content="no tool calls")]}

        results = []
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            for t in tools:
                if t.name == tool_name:
                    try:
                        result = await t.ainvoke(tool_args)
                        results.append(AIMessage(content=json.dumps(result), tool_call_id=tool_call["id"]))
                        if tool_name == "get_prices":
                            state["prices"] = result
                        elif tool_name == "get_indicators":
                            state["indicators"] = result
                    except Exception as e:
                        results.append(AIMessage(content=f"tool {tool_name} error: {str(e)}", tool_call_id=tool_call["id"]))
                    break
        
        return {"messages": results}

    async def prediction_node(self, state: AgentState):
        """ prediction node: generate prediction using LLM """

        if state["error"]:
            return {"messages": [AIMessage(content="error: " + state["error"])]}

        news_text = state["news_text"]
        affected_stock = state["affected_stock"]
        prices = state["prices"]
        indicators = state["indicators"]
        
        if not affected_stock or not prices or not indicators:
            return {
                "messages": [AIMessage(
                    content="error: missing stock, prices or indicators. " +
                    "affected_stock: " + affected_stock + ", " +
                    "prices: " + str(prices) + ", " +
                    "indicators: " + str(indicators)
                )],
                "error": "missing stock, prices or indicators"
            }
        
        formatted_prompt = PREDICTION_PROMPT.format_prompt(
            news_text=news_text,
            affected_stock=affected_stock,
            prices=json.dumps(prices, ensure_ascii=False),
            indicators=json.dumps(indicators, ensure_ascii=False),
            stock_prediction_output_schema=json.dumps(STOCK_PREDICTION_OUTPUT_SCHEMA, ensure_ascii=False)
        )
        
        try:
            response = await self.llm_predict.ainvoke(formatted_prompt.to_messages())
            return {"response": response}
        except Exception as e:
            return {
                "messages": [AIMessage(content=f"Prediction failed: {str(e)}")],
                "error": "Prediction failed: " + str(e),
                "response": {"error": str(e)}
            }