import os
import uuid
import json
import hmac
import base64
import hashlib
import mimetypes
import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import formatdate
from urllib.parse import quote, urlparse, unquote
from concurrent.futures import ThreadPoolExecutor

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from config import CCW_CONFIG

_BUCKET = "zhishi"
_ENDPOINT = "oss-cn-beijing.aliyuncs.com"
_CDN = "m.ccw.site"
_MULTIPART_THRESHOLD = 50 * 1024 * 1024
_PART_SIZE = 10 * 1024 * 1024
_MAX_WORKERS = 4
_TOKEN_TTL = timedelta(hours=1)


class OSSUploader:
    """通过 CCW 凭证向阿里云 OSS 上传 / 删除文件."""

    def __init__(self, ccw_token=None, user_id=None, login_id=None, password=None):
        self.session = requests.Session()
        self.ccw_token = ccw_token or CCW_CONFIG.get('token')
        self.user_id = user_id or CCW_CONFIG.get('user_id')
        self._creds = None
        self._creds_expiry = None
        if not self.ccw_token and login_id and password:
            self.login(login_id, password)
        if not self.ccw_token or not self.user_id:
            raise ValueError("缺少 ccw_token / user_id，请传入参数或在 config.CCW_CONFIG 中配置")

    # ── 登录 ──────────────────────────────────────────
    def login(self, login_id, password):
        resp = self.session.post("https://sso.ccw.site/web/auth/login-by-password", json={
            "loginKey": login_id,
            "clientCode": "STUDY_COMMUNITY",
            "password": password,
            "extra": json.dumps({"device": "Server", "browser": "API", "scene": None})
        })
        resp.raise_for_status()
        body = resp.json().get('body', {})
        self.ccw_token = body.get('token')
        self.user_id = body.get('accountObjectId')
        if not self.ccw_token or not self.user_id:
            raise ValueError("登录失败: 响应中缺少 token 或 accountObjectId")

    # ── 凭证获取 (带缓存) ─────────────────────────────
    def _get_credentials(self, force_refresh=False):
        if not force_refresh and self._creds and self._creds_expiry and datetime.now(timezone.utc) < self._creds_expiry:
            return self._creds
        resp = self.session.post(
            "https://community-web.ccw.site/ccw-main/status",
            headers={'Cookie': f'token={self.ccw_token}'}
        )
        resp.raise_for_status()
        enc = resp.json().get('body', {}).get('data')
        if not enc:
            raise ValueError("获取 OSS Token 失败")
        self._creds = self._decrypt(enc)
        self._creds_expiry = datetime.now(timezone.utc) + _TOKEN_TTL
        return self._creds

    def _decrypt(self, enc_data):
        key = self.user_id[-16:].encode('utf-8')
        iv = self.user_id[:16].encode('utf-8')
        cipher = AES.new(key, AES.MODE_CBC, iv)
        raw = unpad(cipher.decrypt(base64.b64decode(enc_data)), AES.block_size)
        creds = json.loads(raw.decode('utf-8'))
        for f in ('accessKeyId', 'accessKeySecret', 'securityToken'):
            if f not in creds:
                raise ValueError(f"解密后缺少字段: {f}")
        return creds

    # ── 签名 ──────────────────────────────────────────
    @staticmethod
    def _sign(method, resource, creds, headers):
        oss_h = sorted((k.lower(), v) for k, v in headers.items() if k.lower().startswith('x-oss-'))
        canonical = ''.join(f'{k}:{v}\n' for k, v in oss_h)
        sts = f"{method}\n{headers.get('Content-MD5', '')}\n{headers.get('Content-Type', '')}\n{headers.get('Date', '')}\n{canonical}{resource}"
        sig = base64.b64encode(hmac.new(creds['accessKeySecret'].encode(), sts.encode(), hashlib.sha1).digest()).decode()
        return f"OSS {creds['accessKeyId']}:{sig}"

    @staticmethod
    def _date():
        return formatdate(timeval=None, localtime=False, usegmt=True)

    @staticmethod
    def _gen_key(prefix, file_path):
        ext = os.path.splitext(file_path)[1].lower() or '.bin'
        return f"{prefix.rstrip('/')}/{uuid.uuid4().hex}{ext}"

    # ── 上传 ──────────────────────────────────────────
    def upload(self, file_path, prefix=None, content_type=None, key=None):
        """上传文件，返回 dict(success/key/oss_url/cdn_url/size/...)"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(file_path)
        prefix = prefix or CCW_CONFIG.get('default_prefix', 'uploads')
        size = os.path.getsize(file_path)
        if not content_type:
            content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        if not key:
            key = self._gen_key(prefix, file_path)
        if size > _MULTIPART_THRESHOLD:
            return self._multipart(file_path, key, content_type, size)
        return self._simple(file_path, key, content_type, size)

    def _simple(self, file_path, key, content_type, size):
        creds = self._get_credentials()
        resource = f"/{_BUCKET}/{key}"
        h = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        md5 = base64.b64encode(h.digest()).decode()
        headers = {
            'Content-Type': content_type,
            'Content-MD5': md5,
            'Content-Length': str(size),
            'x-oss-security-token': creds['securityToken'],
            'Date': self._date(),
        }
        headers['Authorization'] = self._sign('PUT', resource, creds, headers)
        url = f"https://{_BUCKET}.{_ENDPOINT}/{quote(key)}"
        with open(file_path, 'rb') as f:
            resp = requests.put(url, data=f, headers=headers, timeout=300)
        if resp.status_code != 200:
            raise Exception(f"上传失败: {resp.status_code} {resp.text[:200]}")
        return self._result(key, size, content_type, md5)

    def _multipart(self, file_path, key, content_type, size):
        creds = self._get_credentials()
        resource = f"/{_BUCKET}/{key}"
        # 1. initiate
        ih = {'x-oss-security-token': creds['securityToken'], 'Date': self._date()}
        ih['Authorization'] = self._sign('POST', f"{resource}?uploads", creds, ih)
        resp = requests.post(f"https://{_BUCKET}.{_ENDPOINT}/{quote(key)}?uploads", headers=ih)
        if resp.status_code != 200:
            raise Exception(f"初始化分块失败: {resp.status_code}")
        upload_id = ET.fromstring(resp.text).find('UploadId').text
        # 2. upload parts
        total = (size + _PART_SIZE - 1) // _PART_SIZE
        parts = []
        lock = threading.Lock()

        def _part(num):
            start = (num - 1) * _PART_SIZE
            end = min(num * _PART_SIZE, size)
            with open(file_path, 'rb') as f:
                f.seek(start)
                data = f.read(end - start)
            ph = {
                'Content-Type': content_type,
                'Content-MD5': base64.b64encode(hashlib.md5(data).digest()).decode(),
                'Content-Length': str(len(data)),
                'x-oss-security-token': creds['securityToken'],
                'Date': self._date(),
            }
            ph['Authorization'] = self._sign('PUT', f"{resource}?partNumber={num}&uploadId={upload_id}", creds, ph)
            pr = requests.put(
                f"https://{_BUCKET}.{_ENDPOINT}/{quote(key)}?partNumber={num}&uploadId={upload_id}",
                data=data, headers=ph
            )
            if pr.status_code != 200:
                raise Exception(f"分块 {num} 失败: {pr.status_code}")
            with lock:
                parts.append({'PartNumber': num, 'ETag': pr.headers.get('ETag', '').strip('"')})

        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            list(pool.map(_part, range(1, total + 1)))
        # 3. complete
        parts.sort(key=lambda x: x['PartNumber'])
        xml_body = '<?xml version="1.0" encoding="UTF-8"?>\n<CompleteMultipartUpload>\n'
        for p in parts:
            xml_body += f'  <Part><PartNumber>{p["PartNumber"]}</PartNumber><ETag>{p["ETag"]}</ETag></Part>\n'
        xml_body += '</CompleteMultipartUpload>'
        ch = {
            'Content-Type': 'application/xml',
            'Content-Length': str(len(xml_body)),
            'x-oss-security-token': creds['securityToken'],
            'Date': self._date(),
        }
        ch['Authorization'] = self._sign('POST', f"{resource}?uploadId={upload_id}", creds, ch)
        cr = requests.post(
            f"https://{_BUCKET}.{_ENDPOINT}/{quote(key)}?uploadId={upload_id}",
            data=xml_body.encode(), headers=ch
        )
        if cr.status_code != 200:
            raise Exception(f"合并分块失败: {cr.status_code}")
        return self._result(key, size, content_type, None, multipart=True, parts=total)

    @staticmethod
    def _result(key, size, content_type, md5, multipart=False, parts=0):
        return {
            'success': True,
            'key': key,
            'oss_url': f"https://{_BUCKET}.{_ENDPOINT}/{key}",
            'cdn_url': f"https://{_CDN}/{key}",
            'size': size,
            'content_type': content_type,
            'md5': md5,
            'multipart': multipart,
            'parts': parts,
        }

    # ── 删除 ──────────────────────────────────────────
    def delete(self, url_or_key):
        """删除文件，参数可为完整 URL 或 object key"""
        key = self._extract_key(url_or_key)
        creds = self._get_credentials()
        resource = f"/{_BUCKET}/{key}"
        headers = {'x-oss-security-token': creds['securityToken'], 'Date': self._date()}
        headers['Authorization'] = self._sign('DELETE', resource, creds, headers)
        resp = requests.delete(f"https://{_BUCKET}.{_ENDPOINT}/{quote(key)}", headers=headers, timeout=30)
        return {'success': resp.status_code == 204, 'key': key, 'status': resp.status_code}

    @staticmethod
    def _extract_key(url_or_key):
        if not url_or_key.startswith('http'):
            return url_or_key.strip('/')
        return unquote(urlparse(url_or_key).path.lstrip('/'))
