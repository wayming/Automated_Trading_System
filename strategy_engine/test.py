import os
import json
import re
import requests

resp = """
摘要：
-------------------------------------------------
{
  "stock_code": "MMSC.BK",
  "stock_name": "Metro Systems Corporation",
  "analysis": {
    "short_term": {
      "score": "+15",
      "driver": "季度盈利116百万泰铢，显示公司短期盈利能力",
      "risk": "未披露具体业务增长来源，可能存在一次性收益"
    },
    "mid_term": {
      "score": "+25",
      "driver": "持续盈利表明基本面稳健，可能吸引中期投资者",
      "risk": "缺乏具体订单或项目细节，难以验证可持续性"
    },
    "long_term": {
      "score": "+10",
      "driver": "盈利记录可能反映行业需求稳定",
      "risk": "未提及技术创新或市场扩张计划，长期竞争力不明确"
    }
  },
  "alerts": [
    "未披露具体业务部门表现",
    "未提供未来业绩指引"
  ]
}
-------------------------------------------------

结论：
该季度盈利公告显示公司短期财务表现良好，但缺乏具体业务细节和未来指引限制了中长期评分的提升。投资者需关注后续业务细节披露以验证盈利质量。
"""
def extract_structured_response(response_text):
    pattern = r'^-{3,}\s*\n(.*?)\n-{3,}$'
    match = re.search(pattern, response_text, re.DOTALL | re.MULTILINE)
    if not match:
        print(f"No structure resposne found from {response_text}")
        return None
    
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON struct.\n{match.group(1)}\nError: {e}")
        return None

print(extract_structured_response(resp))
