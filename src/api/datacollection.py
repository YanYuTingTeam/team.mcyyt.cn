from utils.auth import check_login
from utils.db import get_db

TABLE = 'yyt_datacollection'
_DTYPE_MAP = {'survey': 'survey', 'quiz': 'quiz', 'doc': 'doc'}

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    db = get_db()
    try:
        _ensure_table(db)
        if request.method == 'GET':
            return _handle_list(db, user)
        if request.method == 'POST':
            return _handle_create(db, user, request)
        if request.method == 'PUT':
            return _handle_update(db, user, request)
        if request.method == 'DELETE':
            return _handle_delete(db, user, request)
    finally:
        db.close()

def _ensure_table(db):
    with db.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS yyt_datacollection ("
            "  id INT AUTO_INCREMENT PRIMARY KEY, dtype VARCHAR(16) NOT NULL DEFAULT 'survey',"
            "  title VARCHAR(255) NOT NULL, description TEXT DEFAULT NULL,"
            "  is_public TINYINT NOT NULL DEFAULT 1,"
            "  view_count INT NOT NULL DEFAULT 0, submit_count INT NOT NULL DEFAULT 0,"
            "  creator_id INT NOT NULL, updated_by_id INT DEFAULT NULL,"
            "  created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
            "  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,"
            "  KEY idx_creator (creator_id), KEY idx_public (is_public),"
            "  KEY idx_updated (updated_at)"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
        )
        db.commit()

def _row_to_dict(row, current_id):
    return {
        'id': row['id'],
        'type': row['dtype'],
        'title': row['title'],
        'description': (row['description'] or '')[:100],
        'public': row['is_public'],
        'views': row['view_count'],
        'submits': row['submit_count'],
        'creator_id': row['creator_id'],
        'updated_by_id': row['updated_by_id'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
        'can_edit': row['creator_id'] == current_id,
    }

def _handle_list(db, user):
    with db.cursor() as cur:
        cur.execute("SELECT * FROM yyt_datacollection ORDER BY updated_at DESC")
        rows = cur.fetchall()
    return {"code": 0, "data": [_row_to_dict(r, user['id']) for r in rows]}

def _handle_create(db, user, req):
    data = req.get_json(silent=True) or {}
    dtype = (data.get('type') or '').strip().lower()
    title = (data.get('title') or '').strip()
    if dtype not in _DTYPE_MAP:
        return {"code": 400, "message": "类型无效"}
    if not title:
        return {"code": 400, "message": "标题不能为空"}
    description = (data.get('description') or '').strip() or None
    is_public = min(int(data.get('public', 1) or 1), 2)
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO yyt_datacollection (dtype, title, description, is_public, creator_id, updated_by_id) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (dtype, title, description, is_public, user['id'], user['id'])
        )
        did = cur.lastrowid
    db.commit()
    return {"code": 0, "data": {"id": did}}

def _handle_update(db, user, req):
    data = req.get_json(silent=True) or {}
    did = int(data.get('id') or 0)
    if not did:
        return {"code": 400, "message": "参数错误"}
    with db.cursor() as cur:
        cur.execute("SELECT id, creator_id, title, description, is_public FROM yyt_datacollection WHERE id = %s", (did,))
        item = cur.fetchone()
    if not item:
        return {"code": 404, "message": "不存在"}
    if item['creator_id'] != user['id']:
        return {"code": 403, "message": "无权限"}
    title = (data.get('title') or '').strip()
    if not title:
        return {"code": 400, "message": "标题不能为空"}
    description = (data.get('description') or '').strip() or None
    is_public = min(int(data.get('public', item['is_public']) or item['is_public']), 2)
    with db.cursor() as cur:
        cur.execute(
            "UPDATE yyt_datacollection SET title=%s, description=%s, is_public=%s, updated_by_id=%s WHERE id=%s",
            (title, description, is_public, user['id'], did)
        )
    db.commit()
    return {"code": 0}

def _handle_delete(db, user, req):
    if req.method == 'DELETE':
        did = int(req.args.get('id') or 0)
    else:
        data = req.get_json(silent=True) or {}
        did = int(data.get('id') or 0)
    if not did:
        return {"code": 400, "message": "参数错误"}
    with db.cursor() as cur:
        cur.execute("SELECT id, creator_id FROM yyt_datacollection WHERE id = %s", (did,))
        item = cur.fetchone()
    if not item:
        return {"code": 404, "message": "不存在"}
    if item['creator_id'] != user['id']:
        return {"code": 403, "message": "无权限"}
    with db.cursor() as cur:
        cur.execute("DELETE FROM yyt_datacollection WHERE id = %s", (did,))
    db.commit()
    return {"code": 0}
