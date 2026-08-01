import secrets
from utils.auth import check_login
from utils.db import get_db
from utils.security import (
    check_ban, check_email_rate, get_client_ip, ip_segment,
    _ua_hash_from_request
)
from utils.mailer import send_code_email

CODE_EXPIRE_MINUTES = 5

def handle(request):
    if request.method != 'POST':
        return {"code": 405, "message": "method not allow"}
    # 检查是否被 email 风控封禁
    banned, btype, exp, _ = check_ban(request, 'email')
    if banned:
        return {"code": 429, "message": "请求过于频繁, 请稍后再试"}
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    purpose = (data.get('purpose') or '').strip()
    if not email or purpose not in ('login', 'register'):
        return {"code": 400, "message": "参数错误"}
    # 风控检查
    ok, msg = check_email_rate(request)
    if not ok:
        return {"code": 429, "message": msg}
    # 登录场景: 验证邮箱是否已注册
    # 注册场景: 验证邮箱是否未被注册
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT id FROM yyt_user WHERE email = %s", (email,))
            exists = cur.fetchone()
            if purpose == 'login' and not exists:
                return {"code": 404, "message": "该邮箱未注册"}
            if purpose == 'register' and exists:
                return {"code": 409, "message": "该邮箱已注册"}
            # 生成验证码
            code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
            seg = ip_segment(get_client_ip(request))
            ua_hash = _ua_hash_from_request(request)
            cur.execute(
                "INSERT INTO yyt_email_code (email, code, purpose, ip_seg, ua_hash, expire_at) "
                "VALUES (%s, %s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL %s MINUTE))",
                (email, code, purpose, seg, ua_hash, CODE_EXPIRE_MINUTES)
            )
        db.commit()
    finally:
        db.close()
    # 发送邮件
    ok, err = send_code_email(email, code, purpose)
    if not ok:
        return {"code": 500, "message": "邮件发送失败: " + err}
    return {"code": 0, "message": "验证码已发送至邮箱"}
