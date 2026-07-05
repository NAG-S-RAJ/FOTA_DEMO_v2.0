import requests

s = requests.Session()
s.trust_env = True

r = s.get("https://fota-demo-test.onrender.com")

print(r.status_code)