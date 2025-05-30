import requests
import json
import os
HTTP_API_ENDPOINT=os.getenv("HTTP_API_ENDPOINT")
resp = requests.post(
    HTTP_API_ENDPOINT,
    json={"from": "local", "value": "hello"}
)

print(resp.status_code, resp.text)