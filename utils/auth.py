import secrets
from utils.db import get_db

def make_token():
    return secrets.token_hex(32)

def check_login(request):
    token = request.cookies.get('yyt_token')
    if not token:
        return None
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT u.id, u.email, u.name, u.role, u.skill, u.created_at "
                "FROM yyt_session s JOIN yyt_user u ON s.user_id = u.id "
                "WHERE s.token = %s AND s.expire_time > NOW()",
                (token,)
            )
            return cur.fetchone()
    finally:
        db.close()
