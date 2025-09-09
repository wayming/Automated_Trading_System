import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.prompts import ChatPromptTemplate

test_prompt = ChatPromptTemplate.from_messages([
    SystemMessage(content="""
www
"""),
    HumanMessage(content="xxx: {news_text}")
])


IDENTIFY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """
你是一个股票分析师,任务是从新闻文本中识别主要受影响的股票代码(单一股票). 受影响的股票仅限于港股,美股,a股或者澳股市场.
输出JSON格式,符合以下模式：
{stock_identification_output_schema}
只返回一个股票代码。如果新闻未明确提及股票,使用上下文推断.如新闻没有特别指向性的股票,则返回空字符串
"""),
    ("human", "新闻: {news_text}")
])

PREDICTION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """
你是一个股票预测专家。基于以下信息,预测股票在未来的涨跌趋势,输出JSON格式,符合以下模式：   
{stock_prediction_output_schema}
核心指令：

    输入：股票新闻/公告/财报

    输出:结构化分析,寻找相关性最强的股票,包括美股,港股,澳洲股票和a股。 强制包含[-100~+100]评分

    评分规则:
      短期(1-5天) → 资金博弈 & 市场情绪驱动
      中期(1-3月) → 基本面验证(订单/政策落地)
      长期(6M+) → 行业趋势 & 竞争格局变化

    评分格式:
        整数。正负号不省略。

    强度分级:
    评分区间	市场影响	典型场景
    [+80~+100]	产业级颠覆	技术突破/全球垄断
    [+50~+79]	公司质变	重大订单/并购
    [+20~+49]	显著利好	财报超预期/政策支持
    [±19]	中性波动	常规公告/资金博弈
    [-20~-49]	显著利空	业绩暴雷/监管处罚
    [-50~-79]	危机事件	财务造假/CEO被捕
    [-80~-100]	系统性风险	行业崩溃/战争影响

其他要求：
  最多返回一只股票
  输出模板, 必须严格按此格式。包括分割符。在分割符后给出具体分析结论。
  必须使用真实数据，不可以臆想创造数据。每条信息都要有双引号。
  禁止引用已发生的股价数据(如“今日涨停”“过去5天涨幅”)仅基于新闻内容预测未来走势。
  驱动因素必须可验证（如新闻中提到的订单金额、政策条款、技术突破细节）。
  如果找不到相关股票，不返回结构化数据。
"""),
    ("human", """
新闻: {news_text}
股票: {stock_symbol}
短期股价: {prices}
技术指标: {indicators}""")
])
