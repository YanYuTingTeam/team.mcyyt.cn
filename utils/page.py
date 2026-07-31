import os
from flask import Response, redirect
from utils.auth import check_login, get_client_info
from utils.db import get_db

def serve_space(request):
    user = check_login(request)
    if not user:
        return redirect('/')
    ip, _ = get_client_info(request)
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("INSERT INTO yyt_visit (user_id, ip) VALUES (%s, %s)", (user['id'], ip))
        db.commit()
    except Exception:
        pass
    finally:
        db.close()
    page_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'pages', 'space.html')
    with open(page_path, 'r', encoding='utf-8') as f:
        return Response(f.read(), mimetype='text/html')
