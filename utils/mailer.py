import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from config import SMTP_CONFIG

_TPL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'mail_templates')

import re
_IF_RE = re.compile(r'\{%\s*if\s+([A-Z0-9_]+)\s*%\}([\s\S]*?)\{%\s*endif\s*%\}', re.IGNORECASE)

def _render_ifs(html, vars):
    def _sub(m):
        key = m.group(1).strip()
        body = m.group(2)
        val = vars.get(key, '')
        if val:
            return body
        return ''
    prev = None
    while prev != html:
        prev = html
        html = _IF_RE.sub(_sub, html)
    return html

def _load_tpl(name, vars=None):
    p = os.path.join(_TPL_DIR, name)
    try:
        with open(p, 'r', encoding='utf-8') as f:
            html = f.read()
    except Exception:
        return ''
    v = vars or {}
    html = _render_ifs(html, v)
    if v:
        for k, val in v.items():
            html = html.replace('{{' + k + '}}', str(val))
            html = html.replace('{% ' + k + ' %}', str(val))
    return html

def _send_html(to_email, subject, html):
    cfg = SMTP_CONFIG
    if not cfg.get('host') or not cfg.get('user') or not cfg.get('password'):
        return False, 'SMTP未配置'
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = formataddr((cfg.get('from_name', '@team'), cfg.get('from_addr') or cfg['user']))
    msg['To'] = to_email
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    try:
        if cfg.get('port') == 465:
            srv = smtplib.SMTP_SSL(cfg['host'], cfg['port'], timeout=15)
        else:
            srv = smtplib.SMTP(cfg['host'], cfg['port'], timeout=15)
            srv.starttls()
        srv.login(cfg['user'], cfg['password'])
        srv.sendmail(cfg.get('from_addr') or cfg['user'], to_email, msg.as_string())
        srv.quit()
        return True, 'ok'
    except Exception as e:
        return False, str(e)

def send_code_email(to_email, code, purpose):
    purpose_label = {'login': '登录', 'register': '注册', 'change_pwd': '修改密码'}.get(purpose, purpose or '验证')
    subject = f'[@team] {purpose_label}验证码: {code}'
    html = _load_tpl('email_code.html', {'PURPOSE': purpose_label, 'CODE': code})
    if not html:
        return False, '模板加载失败'
    return _send_html(to_email, subject, html)

def send_template_email(to_email, subject, tpl_name, vars=None):
    html = _load_tpl(tpl_name, vars or {})
    if not html:
        return False, '模板加载失败'
    return _send_html(to_email, subject, html)
