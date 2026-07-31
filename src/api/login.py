import bcrypt
from flask import jsonify
from utils.db import get_db
from utils.auth import make_token, get_client_info

def handle(request):
    if request.method != 'POST':
        return {"code": 405, "message": "method not allow"}
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    if not email or not password:
        return {"code": 400, "message": "邮箱或密码不能为空"}
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT * FROM yyt_user WHERE email = %s", (email,))
            user = cur.fetchone()
            if not user or not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
                return {"code": 401, "message": "邮箱或密码错误"}
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
