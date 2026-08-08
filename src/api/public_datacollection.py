from utils.db import get_db

def handle(request):
    db = get_db()
    try:
        if request.method == 'GET':
            with db.cursor() as cur:
                cur.execute(
                    "SELECT id, dtype, title, description, is_public, view_count, submit_count, "
                    "creator_id, updated_by_id, created_at, updated_at "
                    "FROM yyt_datacollection WHERE is_public >= 2 ORDER BY updated_at DESC"
                )
                rows = cur.fetchall()
            data = []
            for r in rows:
                data.append({
                    'id': r['id'],
                    'type': r['dtype'],
                    'title': r['title'],
                    'description': (r['description'] or '')[:100],
                    'public': r['is_public'],
                    'views': r['view_count'],
                    'submits': r['submit_count'],
                    'creator_id': r['creator_id'],
                    'updated_by_id': r['updated_by_id'],
                    'created_at': r['created_at'],
                    'updated_at': r['updated_at'],
                })
            return {"code": 0, "data": data}
    finally:
        db.close()
