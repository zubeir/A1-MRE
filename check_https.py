import requests
hosts = ['https://localhost:7860','https://127.0.0.1:7860','https://10.0.0.79:7860']
for host in hosts:
    try:
        r = requests.get(host, verify=False, timeout=5)
        print(host, '->', r.status_code)
    except Exception as e:
        print(host, 'ERROR:', type(e).__name__, e)
