import secrets
from utils.auth import check_login
from utils.db import get_db
from config import MCSM_CONFIG

_TOKEN_TTL = 20
_ensured = False

def _ensure_table():
    global _ensured
    if _ensured:
        return
    try:
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS yyt_mcsm_token ("
                    "token VARCHAR(64) PRIMARY KEY, "
                    "apikey VARCHAR(255), "
                    "panel_host VARCHAR(255), "
                    "expire_time DATETIME, "
                    "KEY idx_expire (expire_time)"
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                )
                cur.execute("DELETE FROM yyt_mcsm_token WHERE expire_time < NOW()")
            db.commit()
        finally:
            db.close()
    except Exception:
        pass
    _ensured = True

def issue_token(user):
    _ensure_table()
    token = secrets.token_hex(24)
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO yyt_mcsm_token (token, apikey, panel_host, expire_time) "
                "VALUES (%s, %s, %s, DATE_ADD(NOW(), INTERVAL %s SECOND))",
                (token, user.get('apikey'), user.get('panel_host'), _TOKEN_TTL)
            )
        db.commit()
    finally:
        db.close()
    return token

def consume_token(token):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT apikey, panel_host FROM yyt_mcsm_token "
                "WHERE token = %s AND expire_time > NOW()",
                (token,)
            )
            return cur.fetchone()
    finally:
        db.close()

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    return {"code": 0, "data": {
        "panel_suffix": MCSM_CONFIG.get('panel_suffix', ''),
        "panel_host": user.get('panel_host'),
        "token": issue_token(user),
        "is_admin": (user.get('level') or 0) >= 1
    }}
