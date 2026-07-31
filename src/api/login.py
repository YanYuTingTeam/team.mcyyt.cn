import bcrypt
from flask import jsonify
from utils.db import get_db
from utils.auth import make_token, get_client_info
from utils.security import (
    check_auth_ban, login_attempt_incr, login_attempt_remaining, ATTEMPT_MAX
)

def handle(request):
    banned, btype, exp, _ = check_auth_ban(request)
    if banned:
        return {"code": 429, "message": "badly request"}
    if request.method != 'POST':
        return {"code": 405, "message": "method not allow"}
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    if not email or not password:
        return {"code": 400, "message": "badly param"}
    remain_before = login_attempt_remaining(request)
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM yyt_user WHERE email = %s", (email,))
            user = cur.fetchone()
            ok = bool(user and bcrypt.checkpw(password.encode(), user['password_hash'].encode()))
            _, banned_now = login_attempt_incr(request, ok)
            if banned_now:
                return {"code": 429, "message": "badly request"}
            if not ok:
                return {"code": 401, "message": f"邮箱或密码错误"}
            token = make_token()
            ip, ua = get_client_info(request)
            cur.execute(
                "INSERT INTO yyt_session (token, user_id, ip, ua, expire_time) VALUES (%s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL 7 DAY))",
                (token, user['id'], ip, ua)
            )
        db.commit()
    finally:
        db.close()
    resp = jsonify({"code": 0, "message": "ok"})
    resp.set_cookie('yyt_token', token, max_age=7 * 24 * 3600, httponly=True, samesite='Lax')
    return resp
