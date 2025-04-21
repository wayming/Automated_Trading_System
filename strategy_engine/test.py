from alpha_vantage.news_sentiment import NewsSentiment
api_key = "YOUR_KEY"
news = NewsSentiment(key=api_key)
data, _ = news.get_sector_news(sector='technology')
print(data[['title', 'url', 'time_published']].head())