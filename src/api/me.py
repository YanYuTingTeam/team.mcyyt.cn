from utils.auth import check_login

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    safe_user = {k: v for k, v in user.items() if k not in ('apikey', 'password_hash')}
    return {"code": 0, "data": safe_user}
