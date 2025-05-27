import requests

url = "https://your-api-id.execute-api.region.amazonaws.com/prod/message"
payload = {"message": "Hello from local"}
requests.post(url, json=payload)
