import requests
import json

data = {"from": "local", "value": "hello"}
resp = requests.post("https://2t84a88xak.execute-api.ap-southeast-2.amazonaws.com/prod/push",
                     data=json.dumps(data),
                     headers={"Content-Type": "application/json"})
print(resp.status_code, resp.text)