from utils.db import get_db
from utils.auth import check_login


def _ensure_table(db):
    try:
        with db.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS yyt_todo_tag (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(64) NOT NULL UNIQUE,
                    color VARCHAR(16) DEFAULT '#ef5777'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            db.commit()
    except Exception:
        pass


def _list(db):
    with db.cursor() as cur:
        cur.execute("SELECT id, name, color FROM yyt_todo_tag ORDER BY id ASC")
        rows = cur.fetchall()
    return [
        {"id": r["id"], "name": r["name"], "color": r.get("color") or "#ef5777"}
        for r in rows
    ]


def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    db = get_db()
    try:
        _ensure_table(db)
        if request.method == "GET":
            return {"code": 0, "message": "ok", "data": _list(db)}
        if (user.get("level") or 0) < 5:
            return {"code": 403, "message": "无权限"}
        data = request.get_json(silent=True) or {}
        action = (data.get("action") or "").strip()
        if action == "add":
            name = (data.get("name") or "").strip()
            color = (data.get("color") or "#ef5777").strip()
            if not name:
                return {"code": 400, "message": "badly params"}
            with db.cursor() as cur:
                cur.execute("SELECT id FROM yyt_todo_tag WHERE name = %s", (name,))
                if cur.fetchone():
                    return {"code": 409, "message": "该Tag名称已存在"}
                cur.execute("INSERT INTO yyt_todo_tag (name, color) VALUES (%s, %s)", (name, color))
                new_id = cur.lastrowid
            db.commit()
            return {"code": 0, "message": "ok", "data": {"id": new_id}}
        if action == "update":
            tid = int(data.get("id") or 0)
            name = (data.get("name") or "").strip()
            color = (data.get("color") or "#ef5777").strip()
            if not tid or not name:
                return {"code": 400, "message": "badly params"}
            with db.cursor() as cur:
                cur.execute("SELECT id FROM yyt_todo_tag WHERE id = %s", (tid,))
                if not cur.fetchone():
                    return {"code": 404, "message": "Tag不存在"}
                cur.execute("SELECT id FROM yyt_todo_tag WHERE name = %s AND id <> %s", (name, tid))
                if cur.fetchone():
                    return {"code": 409, "message": "该Tag名称已存在"}
                cur.execute("UPDATE yyt_todo_tag SET name = %s, color = %s WHERE id = %s", (name, color, tid))
            db.commit()
            return {"code": 0, "message": "ok"}
        if action == "delete":
            tid = int(data.get("id") or 0)
            if not tid:
                return {"code": 400, "message": "badly params"}
            with db.cursor() as cur:
                cur.execute("SELECT id FROM yyt_todo_tag WHERE id = %s", (tid,))
                if not cur.fetchone():
                    return {"code": 404, "message": "Tag不存在"}
                cur.execute("DELETE FROM yyt_todo_tag WHERE id = %s", (tid,))
                cur.execute("UPDATE yyt_todo SET tag_id = NULL WHERE tag_id = %s", (tid,))
            db.commit()
            return {"code": 0, "message": "ok"}
        return {"code": 400, "message": "badly request"}
    finally:
        db.close()
