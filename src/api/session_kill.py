from utils.auth import check_login
from utils.db import get_db
import re

_UA_PATTERNS = [
    ('Windows', re.compile(r'Windows NT', re.I)),
    ('Mac', re.compile(r'Mac OS X|Macintosh', re.I)),
    ('Linux', re.compile(r'Linux', re.I)),
    ('Android', re.compile(r'Android', re.I)),
    ('iPhone', re.compile(r'iPhone', re.I)),
    ('iPad', re.compile(r'iPad', re.I)),
]

def _parse_device(ua):
    if not ua:
        return '未知设备'
    for name, pat in _UA_PATTERNS:
        if pat.search(ua):
            return name
    return '其他'

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    data = request.get_json(silent=True) or {}
    sid = data.get('sid')
    if not sid:
        return {"code": 400, "message": "缺少会话ID"}
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT id, ip, ua FROM yyt_session WHERE id = %s AND user_id = %s",
                (sid, user['id'])
            )
            session = cur.fetchone()
            if not session:
                return {"code": 404, "message": "会话不存在"}
            cur.execute("DELETE FROM yyt_session WHERE id = %s AND user_id = %s", (sid, user['id']))
            title = '下线成功'
            device = _parse_device(session.get('ua'))
            ip = session.get('ip') or '未知IP'
            content = '已将 ' + ip + ' (' + device + ') 登出'
            cur.execute(
                "INSERT INTO yyt_notice (title, content, created_by) VALUES (%s, %s, %s)",
                (title, content, user['id'])
            )
        db.commit()
        return {"code": 0, "message": "ok"}
    finally:
        db.close()
