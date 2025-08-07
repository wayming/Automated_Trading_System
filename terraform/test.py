import requests
import json
import os
HTTP_API_ENDPOINT=os.getenv("HTTP_API_ENDPOINT")
print(HTTP_API_ENDPOINT)
resp = requests.post(
    HTTP_API_ENDPOINT,
    json={
        "stock_code": "ADSK",
        "stock_name": "Autodesk",
        "analysis": {
            "short_term": {
            "score": "+5",
            "driver": "Berenberg price目标调整至$325（原$299）",
            "risk": "评级维持Hold，市场反应可能有限"
            },
            "mid_term": {
            "score": "+15",
            "driver": "FactSet统计分析师平均评级为overweight，平均目标价$339存在上行空间",
            "risk": "需验证Q3财报是否匹配预期"
            },
            "long_term": {
            "score": "+25",
            "driver": "建筑/工程行业数字化转型趋势",
            "risk": "竞争对手（如Adobe）的3D设计工具替代风险"
            }
        },
        "alerts": [
            "当前股价$310（8/25收盘价）已接近Berenberg目标价",
            "宏观环境可能影响企业软件采购预算"
        ]
    }
)

print(resp.status_code, resp.text)