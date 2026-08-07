import os
import re
from flask import Response
from utils.auth import check_login, get_user_kick_reason
from utils.db import get_db

_KICK_PAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'pages', 'bye.html')
_BANNED_PAGE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'pages', 'banned.html')

PAGE_DEFAULTS = {
    'home': (0, 1), 'overview': (0, 1), 'todo': (1, 1), 'notice': (1, 1),
    'project': (1, 1), 'apis': (1, 1), 'logs': (1, 1),
    'datatools': (1, 1), 'mcsm': (4, 1), 'team': (5, 1),
    'invite_create': (4, 0), 'settings': (0, 1)
}

PAGE_ID_TO_KEY = {
    'pageHome': 'home',
    'pageOverview': 'overview',
    'pageLogs': 'logs',
    'pageDataTools': 'datatools',
    'pageTodo': 'todo',
    'pageTodoDetail': 'todo',
    'pageAddtodo': 'todo',
    'pageNotice': 'notice',
    'pageProject': 'project',
    'pageApis': 'apis',
    'pageMcsm': 'mcsm',
    'pageTeam': 'team',
    'pageSettings': 'settings',
}

_ui_cache = {'mtime': 0, 'html': ''}


def _load_html():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'assets', 'space_ui.html')
    mtime = os.path.getmtime(path)
    if _ui_cache['mtime'] == mtime and _ui_cache['html']:
        return _ui_cache['html']
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    _ui_cache['mtime'] = mtime
    _ui_cache['html'] = html
    return html


def _get_allowed_pages(user_level):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT page_key, min_level, show_in_nav FROM yyt_page_access")
            rows = {r['page_key']: r for r in cur.fetchall()}
    except Exception:
        rows = {}
    finally:
        db.close()
    allowed = set()
    for k, (ml, sn) in PAGE_DEFAULTS.items():
        r = rows.get(k)
        min_level = int(r['min_level']) if r else ml
        if user_level >= min_level:
            allowed.add(k)
    return allowed


def _split_pages(html):
    pattern = re.compile(r'<div class="page[^"]*" id="(page\w+)"')
    matches = list(pattern.finditer(html))
    if not matches:
        return html, [], ''

    before = html[:matches[0].start()]
    pages = []
    last_end = 0

    for m in matches:
        page_id = m.group(1)
        pos = m.start()
        depth = 0
        j = pos
        while j < len(html):
            if html[j] == '<':
                if html[j:j+4] == '<div':
                    depth += 1
                    j += 4
                    continue
                elif html[j:j+5] == '</div':
                    depth -= 1
                    j += 5
                    if depth == 0:
                        j += 1
                        break
                    continue
            j += 1
        page_html = html[pos:j]
        pages.append((page_id, page_html))
        last_end = j

    after = html[last_end:]
    return before, pages, after


def handle(request):
    user = check_login(request)
    if not user:
        if request.cookies.get('yyt_token'):
            with open(_BANNED_PAGE, 'r', encoding='utf-8') as f:
                return Response(f.read(), mimetype='text/html')
        return {"code": 401, "message": "未登录"}
    kick = user.get('_kick_reason', False)
    if kick:
        with open(_KICK_PAGE, 'r', encoding='utf-8') as f:
            return Response(f.read(), mimetype='text/html')
    user_level = user.get('level') or 0
    allowed = _get_allowed_pages(user_level)
    html = _load_html()
    before, pages, after = _split_pages(html)

    nav_pattern = re.compile(r'(<div class="nav-item[^"]*" data-page=")(\w+)(")')
    def _nav_filter(m):
        prefix, page_key, suffix = m.group(1), m.group(2), m.group(3)
        if page_key in allowed:
            return prefix + page_key + suffix
        return prefix + page_key + suffix + ' style="display:none"'

    before_filtered = nav_pattern.sub(_nav_filter, before)

    filtered_pages = ''
    for page_id, page_html in pages:
        page_key = PAGE_ID_TO_KEY.get(page_id, '')
        if not page_key or page_key in allowed:
            filtered_pages += page_html

    result = before_filtered + filtered_pages + after
    return Response(result, mimetype='text/html')
