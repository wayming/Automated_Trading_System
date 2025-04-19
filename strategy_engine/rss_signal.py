import os
import feedparser
import requests
import time

# ========= 配置 =========
RSS_URL = "http://finance.ifeng.com/rss/stocknews.xml"
NUM_ARTICLES = 1
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
WEBSHARE_ROTATE_HTTP = os.getenv('WEBSHARE_ROTATE_HTTP')
WEBSHARE_ROTATE_HTTPS = os.getenv('WEBSHARE_ROTATE_HTTPS')

# 代理设置
PROXIES = {
    "http": WEBSHARE_ROTATE_HTTP,
    "https": WEBSHARE_ROTATE_HTTPS,
}


# ========= 提示模板 =========
def build_prompt(title, summary):
    return f"""
你是一位专业的金融分析师。请根据以下新闻标题和摘要，判断是否包含明确的“买入/卖出”信号,最多只对一只股票产生信号，如果没有相关股票，回复0.
如果有相关股票，则输出如下格式：

股票代码： SMFT(例如)
结论：强烈利多/一般利多/轻微利多/强烈利空/一般利空/轻微利空
理由：（用一句话说明原因）

标题：{title}
摘要：{summary}
"""

# ========= 调用 DeepSeek =========
def analyze_with_deepseek(prompt):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",  # 你也可以试 deepseek-coder
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data)
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error: {e}"

# ========= 主程序 =========
def main():

    test_url = "http://www.google.com"
    try:
        response = requests.get(test_url, proxies=PROXIES, timeout=10)
        print("代理测试成功!")
    except Exception as e:
        print(f"代理测试失败: {e}")
        sys.exit(1)  # 出现错误时退出程序

    print("📡 正在获取 Reuters 财经新闻...")

    try:
        rss_response = requests.get(RSS_URL, proxies=PROXIES, timeout=10)
        rss_response.raise_for_status()
        feed = feedparser.parse(rss_response.content)
        entries = feed.entries[:NUM_ARTICLES]
    except Exception as e:
        print(f"❌ 获取 RSS 失败: {e}")
        return


    print(entries)
    for i, entry in enumerate(entries):
        print(f"\n📄 新闻 {i+1}: {entry.title}")
        print(f"🔗 链接: {entry.link}")
        prompt = build_prompt(entry.title, entry.summary)
        print(prompt)
        result = analyze_with_deepseek(prompt)
        print(f"📊 DeepSeek 结果:\n{result}")
        time.sleep(1.5)

if __name__ == "__main__":
    main()
