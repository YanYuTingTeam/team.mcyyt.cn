import re
from utils.db import get_db
from utils.auth import check_login


def _row_obj(r):
    return {"id": r["id"], "name": r["name"], "color": r.get("color") or "#ef5777"}


def _list(db):
    with db.cursor() as cur:
        cur.execute(
            "SELECT s.id, s.name, s.color, "
            "SUM(CASE WHEN FIND_IN_SET(s.name, REPLACE(REPLACE(IFNULL(u.skill,''), '，', ','), ' ', '')) THEN 1 ELSE 0 END) AS c "
            "FROM yyt_skill_meta s LEFT JOIN yyt_user u ON 1=1 "
            "GROUP BY s.id, s.name, s.color ORDER BY s.id ASC"
        )
        rows = cur.fetchall()
    return [
        {"id": r["id"], "name": r["name"], "color": r.get("color") or "#ef5777", "count": int(r.get("c") or 0)}
        for r in rows
    ]


def _rename_skill_in_users(db, old, new):
    if old == new:
        return
    with db.cursor() as cur:
        cur.execute("SELECT id, skill FROM yyt_user WHERE skill IS NOT NULL AND skill <> ''")
        rows = cur.fetchall()
        regex = re.compile(r'(?<![^,，])\s*' + re.escape(old) + r'\s*(?![^,，])')
        for r in rows:
            raw = r["skill"] or ""
            if old not in raw:
                continue
            parts = re.split(r"[,，]", raw)
            parts_new = [x.strip() for x in parts if x.strip()]
            updated = [new if x == old else x for x in parts_new]
            if updated != parts_new:
                cur.execute(
                    "UPDATE yyt_user SET skill = %s WHERE id = %s",
                    (",".join(updated), r["id"])
                )


def _remove_skill_from_users(db, name):
    with db.cursor() as cur:
        cur.execute("SELECT id, skill FROM yyt_user WHERE skill IS NOT NULL AND skill <> ''")
        for r in cur.fetchall():
            raw = r["skill"] or ""
            if name not in raw:
                continue
            parts = re.split(r"[,，]", raw)
            kept = [x.strip() for x in parts if x.strip() and x.strip() != name]
            new_val = ",".join(kept)
            if new_val != raw:
                cur.execute("UPDATE yyt_user SET skill = %s WHERE id = %s", (new_val, r["id"]))


def handle(request):
    user = check_login(request)
    if not user or (user.get("level") or 0) < 5:
        return {"code": 403, "message": "无权限"}
    db = get_db()
    try:
        if request.method == "GET":
            return {"code": 0, "message": "ok", "data": _list(db)}
        data = request.get_json(silent=True) or {}
        action = (data.get("action") or "").strip()
        if action == "add":
            name = (data.get("name") or "").strip()
            color = (data.get("color") or "#ef5777").strip()
            if not name:
                return {"code": 400, "message": "badly params"}
            with db.cursor() as cur:
                cur.execute("SELECT id FROM yyt_skill_meta WHERE name = %s", (name,))
                if cur.fetchone():
                    return {"code": 409, "message": "该能力名称已存在"}
                cur.execute("INSERT INTO yyt_skill_meta (name, color) VALUES (%s, %s)", (name, color))
                new_id = cur.lastrowid
            db.commit()
            return {"code": 0, "message": "ok", "data": {"id": new_id}}
        if action == "update":
            sid = int(data.get("id") or 0)
            name = (data.get("name") or "").strip()
            color = (data.get("color") or "#ef5777").strip()
            if not sid or not name:
                return {"code": 400, "message": "badly params"}
            with db.cursor() as cur:
                cur.execute("SELECT id, name FROM yyt_skill_meta WHERE id = %s", (sid,))
                row = cur.fetchone()
                if not row:
                    return {"code": 404, "message": "能力不存在"}
                cur.execute("SELECT id FROM yyt_skill_meta WHERE name = %s AND id <> %s", (name, sid))
                if cur.fetchone():
                    return {"code": 409, "message": "该能力名称已存在"}
                old_name = row["name"]
                cur.execute("UPDATE yyt_skill_meta SET name = %s, color = %s WHERE id = %s", (name, color, sid))
                _rename_skill_in_users(db, old_name, name)
            db.commit()
            return {"code": 0, "message": "ok"}
        if action == "delete":
            sid = int(data.get("id") or 0)
            if not sid:
                return {"code": 400, "message": "badly params"}
            with db.cursor() as cur:
                cur.execute("SELECT name FROM yyt_skill_meta WHERE id = %s", (sid,))
                row = cur.fetchone()
                if not row:
                    return {"code": 404, "message": "能力不存在"}
                cur.execute("DELETE FROM yyt_skill_meta WHERE id = %s", (sid,))
                _remove_skill_from_users(db, row["name"])
            db.commit()
            return {"code": 0, "message": "ok"}
        return {"code": 400, "message": "badly request"}
    finally:
        db.close()
