import bcrypt
from flask import jsonify
from utils.db import get_db
from utils.auth import make_token, get_client_info
from utils.security import (
    check_auth_ban, login_attempt_incr, login_attempt_remaining,
    get_client_ip, ip_segment
)
from utils.email_verify import verify_email_code

def _need_device_verify(db, user_id, cur_ip_seg, cur_ua):
    """检测异地且异设备登录: 存在已有会话的 IP段不同 且 UA也不同"""
    with db.cursor() as cur:
        cur.execute(
            "SELECT ip, ua FROM yyt_session "
            "WHERE user_id = %s AND expire_time > NOW()",
            (user_id,)
        )
        sessions = cur.fetchall()
    for s in sessions:
        s_seg = ip_segment(s.get('ip') or '')
        s_ua = (s.get('ua') or '')[:255]
        if s_seg != cur_ip_seg and s_ua != cur_ua:
            return True
    return False

def handle(request):
    banned, btype, exp, _ = check_auth_ban(request)
    if banned:
        return {"code": 429, "message": "badly request"}
    if request.method != 'POST':
        return {"code": 405, "message": "method not allow"}
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''
    email_code = (data.get('email_code') or '').strip()
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
            # 检测异地异设备
            cur_ip, cur_ua = get_client_info(request)
            cur_seg = ip_segment(cur_ip)
            need_verify = _need_device_verify(db, user['id'], cur_seg, cur_ua)
            if need_verify and not email_code:
                return {"code": 202, "message": "检测到异地登录, 需要邮箱验证"}
            if need_verify and email_code:
                vok, vmsg = verify_email_code(email, email_code, 'login')
                if not vok:
                    return {"code": 403, "message": vmsg}
            token = make_token()
            cur.execute(
                "INSERT INTO yyt_session (token, user_id, ip, ua, expire_time) VALUES (%s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL 7 DAY))",
                (token, user['id'], cur_ip, cur_ua)
            )
        db.commit()
    finally:
        db.close()
    resp = jsonify({"code": 0, "message": "ok"})
    resp.set_cookie('yyt_token', token, max_age=7 * 24 * 3600, httponly=True, samesite='Lax')
    return resp
