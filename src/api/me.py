from utils.auth import check_login

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    return {"code": 0, "data": user}
