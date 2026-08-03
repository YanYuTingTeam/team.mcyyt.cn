import os
import tempfile
from utils.auth import check_login
from utils.db import get_db

_col_ensured = False
def _ensure_col(db):
    global _col_ensured
    if _col_ensured:
        return
    try:
        with db.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM yyt_user LIKE 'avatar'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE yyt_user ADD COLUMN avatar VARCHAR(512) DEFAULT NULL AFTER panel_host")
                db.commit()
    except Exception:
        pass
    _col_ensured = True

ALLOWED_MIME = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
ALLOWED_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

def handle(request):
    user = check_login(request)
    if not user:
        return {"code": 401, "message": "未登录"}
    if request.method != 'POST':
        return {"code": 405, "message": "method not allowed"}
    f = request.files.get('avatar') or request.files.get('file')
    if not f:
        return {"code": 400, "message": "未收到文件"}
    mime = (f.mimetype or '').lower()
    ext = os.path.splitext(f.filename or '')[1].lower()
    if mime not in ALLOWED_MIME and ext not in ALLOWED_EXT:
        return {"code": 400, "message": "仅支持 jpg/png/webp/gif 格式"}
    if not ext:
        ext_map = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp', 'image/gif': '.gif'}
        ext = ext_map.get(mime, '.bin')
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext)
    try:
        f.save(tmp_path)
        from utils.upload import OSSUploader
        uploader = OSSUploader()
        result = uploader.upload(tmp_path, prefix=f"avatar/{user['id']}", content_type=mime or None)
        if not result.get('success'):
            return {"code": 500, "message": result.get('error', '上传失败')}
        cdn_url = result['cdn_url']
        db = get_db()
        try:
            _ensure_col(db)
            with db.cursor() as cur:
                cur.execute("UPDATE yyt_user SET avatar = %s WHERE id = %s", (cdn_url, user['id']))
            db.commit()
        finally:
            db.close()
        return {"code": 0, "data": {"avatar": cdn_url}}
    except Exception as e:
        print(f"[avatar_upload] fail: {e}")
        return {"code": 500, "message": "上传失败, 请稍后重试"}
    finally:
        try:
            os.close(tmp_fd)
            os.unlink(tmp_path)
        except Exception:
            pass
