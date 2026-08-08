from utils.db import get_db

def verify_email_code(email, code, purpose):
    """验证邮箱验证码, 成功返回 (True, None), 失败返回 (False, msg)"""
    if not email or not code:
        return False, '请输入验证码'
    if not (code.isdigit() and len(code) == 6):
        return False, '验证码格式错误'
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id FROM yyt_email_code "
                "WHERE email = %s AND code = %s AND purpose = %s AND used = 0 AND expire_at > NOW() "
                "ORDER BY id DESC LIMIT 1",
                (email, code, purpose)
            )
            row = cur.fetchone()
            if not row:
                return False, '验证码错误或已过期'
            cur.execute("UPDATE yyt_email_code SET used = 1 WHERE id = %s", (row['id'],))
            cur.execute(
                "DELETE FROM yyt_email_code WHERE email = %s AND purpose = %s",
                (email, purpose)
            )
        db.commit()
        return True, None
    finally:
        db.close()
