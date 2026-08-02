from utils.auth import check_login
from utils.db import get_db

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    tid = (request.args.get('id') or '').strip()
    if not tid or not tid.isdigit():
        return {"code": 400, "message": "缺少待办ID"}
    tid = int(tid)
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT t.id, t.title, t.link, t.content, t.created_at, t.updated_at, t.is_global, "
                "u.id AS creator_id, u.name AS creator_name, u.avatar AS creator_avatar "
                "FROM yyt_todo t JOIN yyt_user u ON t.creator_id = u.id "
                "WHERE t.id = %s",
                (tid,)
            )
            todo = cur.fetchone()
            if not todo:
                return {"code": 404, "message": "待办不存在"}
            todo['is_creator'] = (todo['creator_id'] == user['id'])
            cur.execute(
                "SELECT r.tag_id AS id, t.name, t.color "
                "FROM yyt_todo_tag_rel r JOIN yyt_todo_tag t ON r.tag_id = t.id "
                "WHERE r.todo_id = %s",
                (tid,)
            )
            todo['tags'] = cur.fetchall()
            if todo['is_global']:
                todo['is_assigned'] = True
            else:
                cur.execute(
                    "SELECT user_id FROM yyt_todo_assign WHERE todo_id = %s AND user_id = %s",
                    (tid, user['id'])
                )
                todo['is_assigned'] = bool(cur.fetchone())
            cur.execute(
                "SELECT a.user_id, a.is_done, a.done_at, u.name, u.avatar "
                "FROM yyt_todo_assign a JOIN yyt_user u ON a.user_id = u.id "
                "WHERE a.todo_id = %s ORDER BY a.is_done DESC, u.name ASC",
                (tid,)
            )
            assigns = cur.fetchall()
        assignees = [{"id": r["user_id"], "name": r["name"], "avatar": r["avatar"]} for r in assigns]
        done_users = [{"id": r["user_id"], "name": r["name"], "avatar": r["avatar"], "done_at": str(r["done_at"]) if r["done_at"] else None} for r in assigns if r["is_done"]]
        my_assign = next((r for r in assigns if r["user_id"] == user['id']), None)
        my_done = bool(my_assign and my_assign["is_done"]) if my_assign else False
        my_done_at = str(my_assign["done_at"]) if my_assign and my_assign["done_at"] else None
        if todo['is_global'] and not my_assign:
            my_done = False
            my_done_at = None
        return {"code": 0, "data": {
            "todo": todo,
            "assignees": assignees,
            "done_users": done_users,
            "my_done": my_done,
            "my_done_at": my_done_at
        }}
    finally:
        db.close()
