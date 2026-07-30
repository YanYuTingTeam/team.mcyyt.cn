from flask import jsonify
from utils.db import get_db

def handle(request):
    token = request.cookies.get('yyt_token')
    if token:
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute("DELETE FROM yyt_session WHERE token = %s", (token,))
            db.commit()
        finally:
            db.close()
    resp = jsonify({"code": 0, "message": "ok"})
    resp.delete_cookie('yyt_token')
    return resp
