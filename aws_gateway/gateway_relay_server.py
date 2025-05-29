import requests
import json
import os
HTTP_API_ENDPOINT=os.getenv("HTTP_API_ENDPOINT")
data = {"from": "local", "value": "hello"}
resp = requests.post(HTTP_API_ENDPOINT,
                     data=json.dumps(data),
                     headers={"Content-Type": "application/json"})
print(resp.status_code, resp.text)