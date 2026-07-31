import secrets
from utils.db import get_db

def make_token():
    return secrets.token_hex(32)

def get_client_info(request):
    ip = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip() or request.remote_addr or ''
    ua = (request.headers.get('User-Agent') or '')[:255]
    return ip[:64], ua

def check_login(request):
    token = request.cookies.get('yyt_token')
    if not token:
        return None
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT u.id, u.email, u.name, u.role, u.skill, u.apikey, u.created_at "
                "FROM yyt_session s JOIN yyt_user u ON s.user_id = u.id "
                "WHERE s.token = %s AND s.expire_time > NOW()",
                (token,)
            )
            return cur.fetchone()
    finally:
        db.close()

def check_apikey(request):
    key = request.headers.get('X-API-Key') or request.args.get('apikey')
    if not key:
        return None
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, email, name, role, skill, apikey, created_at FROM yyt_user WHERE apikey = %s",
                (key,)
            )
            row = cur.fetchone()
            if row:
                ip, _ = get_client_info(request)
                cur.execute(
                    "INSERT INTO yyt_api_log (user_id, ip, path) VALUES (%s, %s, %s)",
                    (row['id'], ip, request.path[:128])
                )
                db.commit()
            return row
    finally:
        db.close()
