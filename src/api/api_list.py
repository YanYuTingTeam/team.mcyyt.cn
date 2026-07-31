import os
import json
from utils.auth import check_login

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'apis.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {"apis": []}
    return {"code": 0, "data": data.get('apis', [])}
