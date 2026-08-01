import os
import uuid
import hashlib
import base64
import json
import re
import time
import sys
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urlparse, unquote
import mimetypes
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import requests
from rich.progress import (
    Progress, 
    SpinnerColumn, 
    TextColumn, 
    BarColumn, 
    DownloadColumn, 
    TransferSpeedColumn,
    TimeRemainingColumn,
    MofNCompleteColumn
)
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich import box
from rich.layout import Layout
from rich.columns import Columns
from rich.prompt import Prompt, Confirm
from rich.status import Status
import math
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import getpass
from email.utils import formatdate

class CCWOSSUploader:
    def __init__(self):
        self.ccw_token = None
        self.user_id = None
        self.encrypted_token = None
        self.token_expiry = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.console = Console()
        self.chunk_size = 1024 * 1024 * 5
        self.max_workers = 4
        self.bucket_name = "zhishi"
        self.oss_endpoint = "oss-cn-beijing.aliyuncs.com"
        
    def password_login(self, login_id, password):
        """密码登录方式"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task("正在通过密码登录...", total=None)
            
            login_url = "https://sso.ccw.site/web/auth/login-by-password"
            login_data = {
                "loginKey": login_id,
                "clientCode": "STUDY_COMMUNITY", 
                "password": password,
                "extra": json.dumps({
                    "device": "Windows 10",
                    "browser": "Firefox 142",
                    "scene": None
                })
            }
            
            try:
                response = self.session.post(login_url, json=login_data)
                response.raise_for_status()
                
                result = response.json()
                if result.get('code') == '200' and 'body' in result:
                    body = result['body']
                    self.ccw_token = body.get('token')
                    self.user_id = body.get('accountObjectId')
                    
                    if self.ccw_token and self.user_id:
                        return True
                    else:
                        self.console.print("登录响应中缺少必要字段", style="bold red")
                        return False
                else:
                    self.console.print(f"登录失败: {result.get('msg', '未知错误')}", style="bold red")
                    return False
                    
            except Exception as e:
                self.console.print(f"登录请求失败: {str(e)}", style="bold red")
                return False
    
    def token_login(self, ccw_token, user_id):
        """直接使用Token登录"""
        self.ccw_token = ccw_token
        self.user_id = user_id
        self.console.print(f"已设置CCW Token", style="bold green")
        self.console.print(f"用户ID: {self.user_id}", style="cyan")
        self.console.print(f"Token: {self.ccw_token[:20]}...", style="cyan")
        return True
    
    def get_encrypted_token(self, force_refresh=False):
        """获取加密的OSS Token，支持自动刷新"""
        if not force_refresh and self.token_expiry and datetime.now(timezone.utc) < self.token_expiry:
            return self.encrypted_token
        
        if not self.ccw_token or not self.user_id:
            self.console.print("请先登录", style="bold red")
            return None
        
        status_url = "https://community-web.ccw.site/ccw-main/status"
        headers = {
            'Cookie': f'token={self.ccw_token}'
        }
        
        try:
            response = self.session.post(status_url, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            if result.get('code') == '200' and 'body' in result:
                encrypted_data = result['body'].get('data')
                if encrypted_data:
                    self.encrypted_token = encrypted_data
                    self.token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
                    return encrypted_data
                else:
                    self.console.print("响应中未找到加密数据", style="bold red")
                    return None
            else:
                self.console.print(f"获取OSS Token失败: {result.get('msg', '未知错误')}", style="bold red")
                return None
                
        except Exception as e:
            self.console.print(f"获取OSS Token请求失败: {str(e)}", style="bold red")
            return None
    
    def _decrypt_credentials(self, encrypted_data: str) -> dict:
        """解密OSS凭证"""
        try:
            if len(self.user_id) < 16:
                raise ValueError("用户ID必须至少16个字符")
            
            key = self.user_id[-16:].encode('utf-8')
            iv = self.user_id[:16].encode('utf-8')
            
            encrypted_bytes = base64.b64decode(encrypted_data)
            
            cipher = AES.new(key, AES.MODE_CBC, iv)
            decrypted_bytes = cipher.decrypt(encrypted_bytes)
            
            try:
                unpadded_data = unpad(decrypted_bytes, AES.block_size)
            except ValueError:
                unpadded_data = decrypted_bytes.rstrip(b'\x00')
            
            try:
                credentials = json.loads(unpadded_data.decode('utf-8'))
            except json.JSONDecodeError:
                text_data = unpadded_data.decode('utf-8', errors='ignore')
                credentials = self._extract_credentials_from_text(text_data)
            
            required_fields = ['accessKeyId', 'accessKeySecret', 'securityToken']
            for field in required_fields:
                if field not in credentials:
                    raise ValueError(f"缺少必要字段: {field}")
            
            return credentials
            
        except Exception as e:
            raise ValueError(f"解密失败: {str(e)}")
    
    def _extract_credentials_from_text(self, text: str) -> dict:
        """从文本中提取凭证信息"""
        credentials = {}
        
        patterns = {
            'accessKeyId': r'accessKey[Ii]d["\']?\s*[:=]\s*["\']?([^"\'\s,]+)',
            'accessKeySecret': r'accessKeySecret["\']?\s*[:=]\s*["\']?([^"\'\s,]+)',
            'securityToken': r'securityToken["\']?\s*[:=]\s*["\']?([^"\'\s,]+)',
            'expiration': r'expiration["\']?\s*[:=]\s*["\']?([^"\'\s,]+)'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, text)
            if match:
                credentials[key] = match.group(1)
        
        return credentials
    
    def _extract_object_key_from_url(self, url: str) -> str:
        """从URL中提取object key"""
        try:
            # 解析URL
            parsed_url = urlparse(url)
            
            # 支持多种URL格式：
            # 1. OSS URL: https://zhishi.oss-cn-beijing.aliyuncs.com/path/to/file
            # 2. CDN URL: https://m.ccw.site/path/to/file
            # 3. 直接object key: path/to/file
            
            # 如果是OSS URL
            if parsed_url.netloc == f"{self.bucket_name}.{self.oss_endpoint}":
                # 移除URL编码
                object_key = unquote(parsed_url.path.lstrip('/'))
                return object_key
            
            # 如果是CDN URL
            elif parsed_url.netloc == "m.ccw.site":
                # 移除URL编码
                object_key = unquote(parsed_url.path.lstrip('/'))
                return object_key
            
            # 如果直接是object key（没有http://或https://前缀）
            elif not parsed_url.scheme or parsed_url.scheme == '':
                # 尝试作为object key处理
                object_key = url.strip('/')
                # 检查是否包含bucket名称，如果包含则移除
                if object_key.startswith(f"{self.bucket_name}/"):
                    object_key = object_key[len(f"{self.bucket_name}/"):]
                return object_key
            
            else:
                # 其他格式的URL，尝试提取路径
                object_key = unquote(parsed_url.path.lstrip('/'))
                return object_key
                
        except Exception as e:
            self.console.print(f"解析URL失败: {str(e)}", style="yellow")
            # 如果不是有效的URL，直接返回原字符串（可能是object key）
            return url.strip('/')
    
    def delete_file(self, url_or_key: str, confirm_before_delete: bool = True) -> dict:
        """
        删除指定的OSS文件
        
        参数:
            url_or_key: 文件URL或object key
            confirm_before_delete: 是否在删除前确认
        
        返回:
            包含删除结果的字典
        """
        # 获取加密的OSS Token
        encrypted_token = self.get_encrypted_token()
        if not encrypted_token:
            return {
                "success": False,
                "error": "无法获取OSS Token，请检查登录状态",
                "object_key": None
            }
        
        try:
            # 解析出object key
            object_key = self._extract_object_key_from_url(url_or_key)
            
            if not object_key:
                return {
                    "success": False,
                    "error": "无法解析出有效的object key",
                    "original_input": url_or_key
                }
            
            # 显示要删除的文件信息
            self.console.print(f"\n[bold cyan]删除文件信息:[/bold cyan]")
            self.console.print(f"原始输入: {url_or_key}")
            self.console.print(f"Object Key: {object_key}")
            self.console.print(f"OSS URL: https://{self.bucket_name}.{self.oss_endpoint}/{object_key}")
            self.console.print(f"CDN URL: https://m.ccw.site/{object_key}")
            
            # 如果需要确认
            if confirm_before_delete:
                confirm = self.console.input("\n[bold yellow]⚠ 确定要删除这个文件吗? (y/n): [/bold yellow]").strip().lower()
                if confirm != 'y':
                    return {
                        "success": False,
                        "error": "用户取消了删除操作",
                        "object_key": object_key,
                        "cancelled": True
                    }
            
            # 解密凭证
            credentials = self._decrypt_credentials(encrypted_token)
            
            # 构建删除请求的URL
            url = f"https://{self.bucket_name}.{self.oss_endpoint}/{quote(object_key)}"
            
            # 构建请求头
            headers = {
                'x-oss-security-token': credentials['securityToken'],
                'Date': self._get_date_header()
            }
            
            # 生成签名
            signature = self._generate_signature('DELETE', object_key, credentials, headers, self.bucket_name)
            headers['Authorization'] = f'OSS {credentials["accessKeyId"]}:{signature}'
            
            # 发送删除请求
            self.console.print(f"\n[bold yellow]正在删除文件...[/bold yellow]")
            response = requests.delete(url, headers=headers, timeout=10)
            
            # 解析响应
            if response.status_code == 204:
                # 204 No Content 表示删除成功
                result = {
                    "success": True,
                    "object_key": object_key,
                    "oss_url": f"https://{self.bucket_name}.{self.oss_endpoint}/{object_key}",
                    "cdn_url": f"https://m.ccw.site/{object_key}",
                    "status_code": response.status_code,
                    "message": "文件删除成功",
                    "deleted_at": datetime.now(timezone.utc).isoformat()
                }
                self.console.print(f"[bold green]✓ 文件删除成功![/bold green]")
                return result
                
            elif response.status_code == 404:
                # 文件不存在
                result = {
                    "success": False,
                    "error": "文件不存在或已被删除",
                    "object_key": object_key,
                    "status_code": response.status_code,
                    "response": response.text
                }
                self.console.print(f"[bold yellow]⚠ 文件不存在或已被删除[/bold yellow]")
                return result
                
            else:
                # 其他错误
                error_msg = f"删除失败: {response.status_code} - {response.text[:200]}"
                result = {
                    "success": False,
                    "error": error_msg,
                    "object_key": object_key,
                    "status_code": response.status_code,
                    "response": response.text
                }
                self.console.print(f"[bold red]✗ {error_msg}[/bold red]")
                return result
                
        except Exception as e:
            error_msg = f"删除文件时发生错误: {str(e)}"
            result = {
                "success": False,
                "error": error_msg,
                "object_key": url_or_key,
                "exception": str(e)
            }
            self.console.print(f"[bold red]✗ {error_msg}[/bold red]")
            return result
    
    def batch_delete(self, urls_or_keys: list, confirm_before_delete: bool = True) -> list:
        """
        批量删除文件
        
        参数:
            urls_or_keys: 文件URL或object key列表
            confirm_before_delete: 是否在删除前确认
        
        返回:
            删除结果列表
        """
        if not urls_or_keys:
            return []
        
        self.console.print(f"\n[bold cyan]批量删除操作[/bold cyan]")
        self.console.print(f"共 {len(urls_or_keys)} 个文件")
        
        # 显示要删除的文件列表
        table = Table(title="待删除文件列表", box=box.ROUNDED)
        table.add_column("序号", style="cyan", width=6)
        table.add_column("文件标识", style="green", width=60)
        table.add_column("解析结果", style="yellow", width=40)
        
        object_keys = []
        for i, url_or_key in enumerate(urls_or_keys, 1):
            object_key = self._extract_object_key_from_url(url_or_key)
            object_keys.append(object_key)
            
            # 缩短显示
            display_input = url_or_key[:57] + "..." if len(url_or_key) > 60 else url_or_key
            display_key = object_key[:37] + "..." if len(object_key) > 40 else object_key
            
            table.add_row(str(i), display_input, display_key)
        
        self.console.print(table)
        
        # 如果需要确认
        if confirm_before_delete:
            confirm = self.console.input(f"\n[bold red]⚠ 确定要删除这 {len(urls_or_keys)} 个文件吗? (y/n): [/bold red]").strip().lower()
            if confirm != 'y':
                self.console.print("[yellow]用户取消了批量删除操作[/yellow]")
                return []
        
        results = []
        success_count = 0
        fail_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TimeRemainingColumn(),
        ) as progress:
            main_task = progress.add_task(f"批量删除文件", total=len(urls_or_keys))
            
            for i, (url_or_key, object_key) in enumerate(zip(urls_or_keys, object_keys), 1):
                progress.update(main_task, description=f"正在删除文件 {i}/{len(urls_or_keys)}")
                
                try:
                    # 调用单个删除方法，但不再次确认
                    result = self.delete_file(url_or_key, confirm_before_delete=False)
                    
                    if result.get("success"):
                        success_count += 1
                        progress.console.print(f"[green]✓ 删除成功: {object_key[:50]}...[/green]")
                    else:
                        fail_count += 1
                        if result.get("cancelled"):
                            progress.console.print(f"[yellow]⚠ 跳过: {object_key[:50]}...[/yellow]")
                        else:
                            progress.console.print(f"[red]✗ 删除失败: {object_key[:50]}... - {result.get('error', '未知错误')[:50]}[/red]")
                    
                    results.append(result)
                    
                except Exception as e:
                    fail_count += 1
                    error_result = {
                        "success": False,
                        "error": str(e),
                        "object_key": object_key,
                        "original_input": url_or_key
                    }
                    results.append(error_result)
                    progress.console.print(f"[red]✗ 删除异常: {object_key[:50]}... - {str(e)[:50]}[/red]")
                
                progress.update(main_task, advance=1)
        
        # 显示统计结果
        self.console.print(f"\n[bold cyan]批量删除完成[/bold cyan]")
        self.console.print(f"成功: {success_count} 个")
        self.console.print(f"失败: {fail_count} 个")
        
        return results
    
    def delete_from_file(self, file_path: str, confirm_before_delete: bool = True) -> list:
        """
        从文件中读取URL或object key进行批量删除
        
        参数:
            file_path: 包含URL或object key的文件路径（每行一个）
            confirm_before_delete: 是否在删除前确认
        
        返回:
            删除结果列表
        """
        if not os.path.exists(file_path):
            self.console.print(f"[bold red]文件不存在: {file_path}[/bold red]")
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 过滤空行和注释行
            urls_or_keys = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    urls_or_keys.append(line)
            
            if not urls_or_keys:
                self.console.print(f"[yellow]文件中没有有效的URL或object key[/yellow]")
                return []
            
            self.console.print(f"[green]从文件 {file_path} 中读取到 {len(urls_or_keys)} 个文件标识[/green]")
            
            # 调用批量删除
            return self.batch_delete(urls_or_keys, confirm_before_delete)
            
        except Exception as e:
            self.console.print(f"[bold red]读取文件失败: {str(e)}[/bold red]")
            return []
    
    def _generate_object_key(self, file_path: str) -> str:
        """生成简洁的object key，不包含原始文件名"""
        _, file_extension = os.path.splitext(file_path)
        file_extension = file_extension.lower() if file_extension else '.bin'
        file_uuid = str(uuid.uuid4()).replace('-', '')
        return f"creator-college/videos/{file_uuid}{file_extension}"
    
    def _safe_filename(self, filename: str) -> str:
        """将文件名转换为安全的字符串"""
        filename = re.sub(r'[^\w\u4e00-\u9fa5.-]', '_', filename)
        return filename.strip('_')
    
    def _encode_filename_header(self, filename: str) -> str:
        """编码文件名用于Content-Disposition头"""
        encoded = filename.encode('utf-8')
        ascii_chars = []
        for byte in encoded:
            if 32 <= byte <= 126 and byte not in [34, 92]:
                ascii_chars.append(chr(byte))
            else:
                ascii_chars.append(f'%{byte:02X}')
        return ''.join(ascii_chars)
    
    def _create_content_disposition_header(self, filename: str) -> str:
        """创建Content-Disposition头，支持中文文件名"""
        encoded_filename = self._encode_filename_header(filename)
        utf8_filename = quote(filename.encode('utf-8'), safe='')
        return f'attachment; filename="{encoded_filename}"; filename*=UTF-8\'\'{utf8_filename}'
    
    def _calculate_file_hash_stream(self, file_path: str, chunk_size: int = 8192) -> str:
        """流式计算文件的MD5哈希值"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _get_date_header(self):
        """获取RFC 1123格式的日期字符串"""
        return formatdate(timeval=None, localtime=False, usegmt=True)
    
    def upload_file_stream(self, file_path, custom_object_key=None, content_type=None, retry_count=3, show_progress=True):
        """流式上传文件到OSS，带进度条显示"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        for attempt in range(retry_count):
            try:
                encrypted_token = self.get_encrypted_token(force_refresh=(attempt > 0))
                if not encrypted_token:
                    if attempt == retry_count - 1:
                        raise Exception("无法获取有效的OSS Token")
                    continue
                
                credentials = self._decrypt_credentials(encrypted_token)
                
                if custom_object_key:
                    object_key = custom_object_key
                else:
                    object_key = self._generate_object_key(file_path)
                
                file_size = os.path.getsize(file_path)
                file_name = os.path.basename(file_path)
                original_filename = os.path.basename(file_path)
                
                if content_type is None:
                    content_type, _ = mimetypes.guess_type(file_path)
                    if content_type is None:
                        content_type = 'application/octet-stream'
                
                if show_progress:
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[bold blue]计算文件MD5..."),
                        BarColumn(),
                        "[progress.percentage]{task.percentage:>3.0f}%",
                        TimeRemainingColumn(),
                    ) as progress:
                        hash_md5 = hashlib.md5()
                        total_bytes = 0
                        task = progress.add_task("计算MD5", total=file_size)
                        
                        with open(file_path, "rb") as f:
                            while True:
                                chunk = f.read(8192)
                                if not chunk:
                                    break
                                hash_md5.update(chunk)
                                total_bytes += len(chunk)
                                progress.update(task, completed=total_bytes)
                else:
                    hash_md5 = hashlib.md5()
                    with open(file_path, "rb") as f:
                        while True:
                            chunk = f.read(8192)
                            if not chunk:
                                break
                            hash_md5.update(chunk)
                
                content_md5 = base64.b64encode(hash_md5.digest()).decode('utf-8')
                
                headers = {
                    'Content-Type': content_type,
                    'Content-MD5': content_md5,
                    'Content-Length': str(file_size),
                    'x-oss-security-token': credentials['securityToken'],
                    'Date': self._get_date_header(),
                    'Content-Disposition': self._create_content_disposition_header(original_filename)
                }
                
                bucket_name = "zhishi"
                url = f"https://{bucket_name}.oss-cn-beijing.aliyuncs.com/{quote(object_key)}"
                
                signature = self._generate_signature('PUT', object_key, credentials, headers, bucket_name)
                headers['Authorization'] = f'OSS {credentials["accessKeyId"]}:{signature}'
                
                if show_progress:
                    class FileReaderWithProgress:
                        def __init__(self, file_path, progress, task_id, chunk_size=1024 * 1024):
                            self.file = open(file_path, 'rb')
                            self.progress = progress
                            self.task_id = task_id
                            self.chunk_size = chunk_size
                            self.bytes_read = 0
                            
                        def read(self, size=-1):
                            if size == -1:
                                size = self.chunk_size
                            chunk = self.file.read(size)
                            if chunk:
                                self.bytes_read += len(chunk)
                                self.progress.update(self.task_id, advance=len(chunk))
                            return chunk
                        
                        def close(self):
                            self.file.close()
                    
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[bold blue]上传文件..."),
                        BarColumn(),
                        "[progress.percentage]{task.percentage:>3.0f}%",
                        DownloadColumn(),
                        TransferSpeedColumn(),
                        TimeRemainingColumn(),
                    ) as progress:
                        upload_task = progress.add_task(f"上传 {file_name}", total=file_size)
                        
                        file_reader = FileReaderWithProgress(file_path, progress, upload_task, self.chunk_size)
                        
                        try:
                            response = requests.put(
                                url, 
                                data=file_reader, 
                                headers=headers,
                                stream=True,
                                timeout=(30, 300)
                            )
                        finally:
                            file_reader.close()
                else:
                    # 无进度条模式
                    with open(file_path, 'rb') as f:
                        file_content = f.read()
                    
                    session = requests.Session()
                    adapter = requests.adapters.HTTPAdapter(
                        pool_connections=10,
                        pool_maxsize=10,
                        max_retries=3
                    )
                    session.mount('http://', adapter)
                    session.mount('https://', adapter)
                    
                    response = session.put(url, data=file_content, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    oss_url = f"https://zhishi.oss-cn-beijing.aliyuncs.com/{object_key}"
                    cdn_url = f"https://m.ccw.site/{object_key}"
                    return {
                        "success": True,
                        "object_key": object_key,
                        "oss_url": oss_url,
                        "cdn_url": cdn_url,
                        "original_filename": original_filename,
                        "file_size": file_size,
                        "content_type": content_type,
                        "upload_time": datetime.now(timezone.utc).isoformat(),
                        "md5": content_md5
                    }
                elif response.status_code == 403 and attempt < retry_count - 1:
                    self.console.print("Token可能过期，尝试刷新...", style="yellow")
                    continue
                else:
                    error_msg = f"文件上传失败: {response.status_code} - {response.text[:200]}"
                    return {
                        "success": False,
                        "error": error_msg,
                        "status_code": response.status_code
                    }
                    
            except Exception as e:
                if attempt < retry_count - 1:
                    self.console.print(f"上传失败，尝试重试 ({attempt + 1}/{retry_count}): {str(e)[:100]}", style="yellow")
                    time.sleep(1)
                else:
                    raise
    
    def upload_file_fast(self, file_path, custom_object_key=None, content_type=None, retry_count=3, show_progress=True):
        """高速上传文件，使用分块并发传输"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        for attempt in range(retry_count):
            try:
                encrypted_token = self.get_encrypted_token(force_refresh=(attempt > 0))
                if not encrypted_token:
                    if attempt == retry_count - 1:
                        raise Exception("无法获取有效的OSS Token")
                    continue
                
                credentials = self._decrypt_credentials(encrypted_token)
                
                if custom_object_key:
                    object_key = custom_object_key
                else:
                    object_key = self._generate_object_key(file_path)
                
                file_size = os.path.getsize(file_path)
                file_name = os.path.basename(file_path)
                original_filename = os.path.basename(file_path)
                
                if content_type is None:
                    content_type, _ = mimetypes.guess_type(file_path)
                    if content_type is None:
                        content_type = 'application/octet-stream'
                
                if file_size > 100 * 1024 * 1024:
                    if show_progress:
                        self.console.print(f"文件较大 ({self._format_size(file_size)})，使用分块计算MD5...", style="cyan")
                    
                    if show_progress:
                        with Progress(
                            SpinnerColumn(),
                            TextColumn("[bold blue]计算大文件MD5..."),
                            BarColumn(),
                            "[progress.percentage]{task.percentage:>3.0f}%",
                            TimeRemainingColumn(),
                            transient=True,
                        ) as progress:
                            total_bytes = 0
                            task = progress.add_task("计算MD5", total=file_size)
                            hash_md5 = hashlib.md5()
                            
                            with open(file_path, "rb") as f:
                                while True:
                                    chunk = f.read(8192)
                                    if not chunk:
                                        break
                                    hash_md5.update(chunk)
                                    total_bytes += len(chunk)
                                    progress.update(task, completed=total_bytes)
                    else:
                        hash_md5 = hashlib.md5()
                        with open(file_path, "rb") as f:
                            for chunk in iter(lambda: f.read(8192), b""):
                                hash_md5.update(chunk)
                    
                    content_md5 = base64.b64encode(hash_md5.digest()).decode('utf-8')
                else:
                    if show_progress:
                        with Progress(
                            SpinnerColumn(),
                            TextColumn("[bold blue]计算文件MD5..."),
                            BarColumn(),
                            "[progress.percentage]{task.percentage:>3.0f}%",
                            TimeRemainingColumn(),
                            transient=True,
                        ) as progress:
                            hash_md5 = hashlib.md5()
                            total_bytes = 0
                            task = progress.add_task("计算MD5", total=file_size)
                            
                            with open(file_path, "rb") as f:
                                while True:
                                    chunk = f.read(8192)
                                    if not chunk:
                                        break
                                    hash_md5.update(chunk)
                                    total_bytes += len(chunk)
                                    progress.update(task, completed=total_bytes)
                            
                            content_md5 = base64.b64encode(hash_md5.digest()).decode('utf-8')
                    else:
                        hash_md5 = hashlib.md5()
                        with open(file_path, "rb") as f:
                            for chunk in iter(lambda: f.read(8192), b""):
                                hash_md5.update(chunk)
                        content_md5 = base64.b64encode(hash_md5.digest()).decode('utf-8')
                
                if file_size > 50 * 1024 * 1024:
                    return self._multipart_upload(file_path, object_key, credentials, file_name, original_filename, file_size, content_type, content_md5, show_progress)
                else:
                    return self._simple_upload_fast(file_path, object_key, credentials, file_name, original_filename, file_size, content_type, content_md5)
                    
            except Exception as e:
                if attempt < retry_count - 1:
                    self.console.print(f"上传失败，尝试重试 ({attempt + 1}/{retry_count}): {str(e)[:100]}", style="yellow")
                    time.sleep(1)
                else:
                    raise
    
    def _simple_upload_fast(self, file_path, object_key, credentials, file_name, original_filename, file_size, content_type, content_md5):
        """快速简单上传（小文件）"""
        headers = {
            'Content-Type': content_type,
            'Content-MD5': content_md5,
            'Content-Length': str(file_size),
            'x-oss-security-token': credentials['securityToken'],
            'Date': self._get_date_header(),
            'Content-Disposition': self._create_content_disposition_header(original_filename)
        }
        
        bucket_name = "zhishi"
        url = f"https://{bucket_name}.oss-cn-beijing.aliyuncs.com/{quote(object_key)}"
        
        signature = self._generate_signature('PUT', object_key, credentials, headers, bucket_name)
        headers['Authorization'] = f'OSS {credentials["accessKeyId"]}:{signature}'
        
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=10,
            max_retries=3
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        response = session.put(url, data=file_content, headers=headers, timeout=30)
        
        if response.status_code == 200:
            oss_url = f"https://zhishi.oss-cn-beijing.aliyuncs.com/{object_key}"
            cdn_url = f"https://m.ccw.site/{object_key}"
            return {
                "success": True,
                "object_key": object_key,
                "oss_url": oss_url,
                "cdn_url": cdn_url,
                "original_filename": original_filename,
                "file_size": file_size,
                "content_type": content_type,
                "upload_time": datetime.now(timezone.utc).isoformat(),
                "md5": content_md5
            }
        else:
            error_msg = f"文件上传失败: {response.status_code} - {response.text[:200]}"
            return {
                "success": False,
                "error": error_msg,
                "status_code": response.status_code
            }
    
    def _multipart_upload(self, file_path, object_key, credentials, file_name, original_filename, file_size, content_type, content_md5, show_progress=True):
        """分块上传大文件（支持断点续传）"""
        bucket_name = "zhishi"
        
        upload_id = self._initiate_multipart_upload(object_key, credentials, bucket_name, content_type, original_filename)
        if not upload_id:
            raise Exception("初始化分块上传失败")
        
        part_size = 10 * 1024 * 1024
        total_parts = (file_size + part_size - 1) // part_size
        
        if show_progress:
            self.console.print(f"分块上传: {total_parts} 个分块，每个 {self._format_size(part_size)}", style="cyan")
        
        uploaded_parts = []
        lock = threading.Lock()
        
        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%",
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            ) as progress:
                main_task = progress.add_task(f"上传 {file_name}", total=file_size)
                
                def upload_part(part_number, start, end):
                    """上传单个分块"""
                    try:
                        with open(file_path, 'rb') as f:
                            f.seek(start)
                            part_data = f.read(end - start)
                        
                        etag = self._upload_part(object_key, upload_id, part_number, part_data, 
                                                credentials, bucket_name, content_type)
                        
                        with lock:
                            uploaded_parts.append({
                                'PartNumber': part_number,
                                'ETag': etag
                            })
                            progress.update(main_task, advance=len(part_data))
                        
                        return True
                    except Exception as e:
                        if show_progress:
                            self.console.print(f"分块 {part_number} 上传失败: {str(e)}", style="red")
                        return False
                
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = []
                    for i in range(total_parts):
                        start = i * part_size
                        end = min((i + 1) * part_size, file_size)
                        part_number = i + 1
                        
                        future = executor.submit(upload_part, part_number, start, end)
                        futures.append(future)
                    
                    results = [future.result() for future in futures]
                    
                    if not all(results):
                        raise Exception("部分分块上传失败")
        else:
            # 无进度条模式
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for i in range(total_parts):
                    start = i * part_size
                    end = min((i + 1) * part_size, file_size)
                    part_number = i + 1
                    
                    future = executor.submit(self._upload_part_sync, object_key, upload_id, part_number, 
                                           start, end, file_path, credentials, bucket_name, content_type, uploaded_parts, lock)
                    futures.append(future)
                
                results = [future.result() for future in futures]
                
                if not all(results):
                    raise Exception("部分分块上传失败")
        
        if show_progress:
            self.console.print("所有分块上传完成，正在合并...", style="green")
        
        uploaded_parts.sort(key=lambda x: x['PartNumber'])
        
        success = self._complete_multipart_upload(object_key, upload_id, uploaded_parts, 
                                                 credentials, bucket_name)
        
        if success:
            oss_url = f"https://zhishi.oss-cn-beijing.aliyuncs.com/{object_key}"
            cdn_url = f"https://m.ccw.site/{object_key}"
            return {
                "success": True,
                "object_key": object_key,
                "oss_url": oss_url,
                "cdn_url": cdn_url,
                "original_filename": original_filename,
                "file_size": file_size,
                "content_type": content_type,
                "upload_time": datetime.now(timezone.utc).isoformat(),
                "md5": content_md5,
                "multipart": True,
                "parts": total_parts
            }
        else:
            raise Exception("分块上传合并失败")
    
    def _upload_part_sync(self, object_key, upload_id, part_number, start, end, file_path, credentials, bucket_name, content_type, uploaded_parts, lock):
        """同步上传分块（用于无进度条模式）"""
        try:
            with open(file_path, 'rb') as f:
                f.seek(start)
                part_data = f.read(end - start)
            
            etag = self._upload_part(object_key, upload_id, part_number, part_data, 
                                    credentials, bucket_name, content_type)
            
            with lock:
                uploaded_parts.append({
                    'PartNumber': part_number,
                    'ETag': etag
                })
            
            return True
        except Exception as e:
            return False
    
    def _initiate_multipart_upload(self, object_key, credentials, bucket_name, content_type, original_filename):
        """初始化分块上传"""
        url = f"https://{bucket_name}.oss-cn-beijing.aliyuncs.com/{quote(object_key)}?uploads"
        
        headers = {
            'x-oss-security-token': credentials['securityToken'],
            'Date': self._get_date_header(),
            'Content-Disposition': self._create_content_disposition_header(original_filename)
        }
        
        signature = self._generate_signature('POST', f"{object_key}?uploads", credentials, headers, bucket_name)
        headers['Authorization'] = f'OSS {credentials["accessKeyId"]}:{signature}'
        
        response = requests.post(url, headers=headers)
        
        if response.status_code == 200:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.text)
            upload_id = root.find('UploadId').text
            return upload_id
        else:
            self.console.print(f"初始化分块上传失败: {response.status_code} - {response.text}", style="red")
            return None
    
    def _upload_part(self, object_key, upload_id, part_number, part_data, credentials, bucket_name, content_type):
        """上传分块"""
        url = f"https://{bucket_name}.oss-cn-beijing.aliyuncs.com/{quote(object_key)}?partNumber={part_number}&uploadId={upload_id}"
        
        part_md5 = base64.b64encode(hashlib.md5(part_data).digest()).decode('utf-8')
        
        headers = {
            'Content-Type': content_type,
            'Content-MD5': part_md5,
            'Content-Length': str(len(part_data)),
            'x-oss-security-token': credentials['securityToken'],
            'Date': self._get_date_header()
        }
        
        signature = self._generate_signature('PUT', 
                                            f"{object_key}?partNumber={part_number}&uploadId={upload_id}", 
                                            credentials, headers, bucket_name)
        headers['Authorization'] = f'OSS {credentials["accessKeyId"]}:{signature}'
        
        response = requests.put(url, data=part_data, headers=headers)
        
        if response.status_code == 200:
            etag = response.headers.get('ETag', '').strip('"')
            return etag
        else:
            raise Exception(f"分块上传失败: {response.status_code} - {response.text}")
    
    def _complete_multipart_upload(self, object_key, upload_id, parts, credentials, bucket_name):
        """完成分块上传"""
        url = f"https://{bucket_name}.oss-cn-beijing.aliyuncs.com/{quote(object_key)}?uploadId={upload_id}"
        
        xml_parts = '<?xml version="1.0" encoding="UTF-8"?>\n<CompleteMultipartUpload>\n'
        for part in parts:
            xml_parts += f'  <Part>\n    <PartNumber>{part["PartNumber"]}</PartNumber>\n    <ETag>{part["ETag"]}</ETag>\n  </Part>\n'
        xml_parts += '</CompleteMultipartUpload>'
        
        headers = {
            'Content-Type': 'application/xml',
            'Content-Length': str(len(xml_parts)),
            'x-oss-security-token': credentials['securityToken'],
            'Date': self._get_date_header()
        }
        
        signature = self._generate_signature('POST', f"{object_key}?uploadId={upload_id}", 
                                            credentials, headers, bucket_name)
        headers['Authorization'] = f'OSS {credentials["accessKeyId"]}:{signature}'
        
        response = requests.post(url, data=xml_parts.encode('utf-8'), headers=headers)
        
        if response.status_code == 200:
            return True
        else:
            self.console.print(f"完成分块上传失败: {response.status_code} - {response.text}", style="red")
            return False
    
    def _calculate_multipart_md5(self, file_path, chunk_size=8192, show_progress=True):
        """分块计算大文件的MD5"""
        hash_md5 = hashlib.md5()
        
        if show_progress:
            file_size = os.path.getsize(file_path)
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]计算大文件MD5..."),
                BarColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%",
                TimeRemainingColumn(),
                transient=True,
            ) as progress:
                total_bytes = 0
                task = progress.add_task("计算MD5", total=file_size)
                
                with open(file_path, "rb") as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        hash_md5.update(chunk)
                        total_bytes += len(chunk)
                        progress.update(task, completed=total_bytes)
        else:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hash_md5.update(chunk)
        
        return base64.b64encode(hash_md5.digest()).decode('utf-8')
    
    def _generate_signature(self, method, object_key, credentials, headers, bucket_name="zhishi"):
        """生成OSS签名"""
        canonicalized_resource = f'/{bucket_name}/{object_key}'
        
        canonicalized_headers = ''
        oss_headers = {k: v for k, v in headers.items() if k.lower().startswith('x-oss-')}
        sorted_oss_headers = sorted(oss_headers.items())
        canonicalized_headers = ''.join([f'{k.lower()}:{v}\n' for k, v in sorted_oss_headers])
        
        string_to_sign = f"{method.upper()}\n"
        string_to_sign += f"{headers.get('Content-MD5', '')}\n"
        string_to_sign += f"{headers.get('Content-Type', '')}\n"
        string_to_sign += f"{headers.get('Date', '')}\n"
        string_to_sign += canonicalized_headers
        string_to_sign += canonicalized_resource
        
        import hmac
        key = credentials['accessKeySecret'].encode('utf-8')
        signature = base64.b64encode(
            hmac.new(key, string_to_sign.encode('utf-8'), hashlib.sha1).digest()
        ).decode('utf-8')
        
        return signature
    
    def _format_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes == 0:
            return "0B"
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"
    
    def batch_upload(self, folder_path, upload_mode="fast", extensions=None, max_workers=3):
        """批量上传文件夹中的文件"""
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"文件夹不存在: {folder_path}")
        
        if not os.path.isdir(folder_path):
            raise ValueError(f"路径不是文件夹: {folder_path}")
        
        # 获取文件夹中的所有文件
        all_files = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                all_files.append(file_path)
        
        if not all_files:
            self.console.print("文件夹中没有文件", style="yellow")
            return []
        
        # 过滤文件扩展名
        if extensions:
            extensions = [ext.lower().strip() for ext in extensions]
            filtered_files = []
            for file_path in all_files:
                _, ext = os.path.splitext(file_path)
                if ext.lower() in extensions:
                    filtered_files.append(file_path)
            all_files = filtered_files
        
        if not all_files:
            self.console.print(f"没有匹配 {extensions} 扩展名的文件", style="yellow")
            return []
        
        self.console.print(f"找到 {len(all_files)} 个文件", style="green")
        
        # 显示文件列表
        table = Table(title="待上传文件列表", box=box.ROUNDED)
        table.add_column("序号", style="cyan", width=6)
        table.add_column("文件名", style="green", width=40)
        table.add_column("大小", style="yellow", width=12)
        table.add_column("路径", style="white")
        
        for i, file_path in enumerate(all_files[:20]):  # 只显示前20个
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            table.add_row(str(i+1), file_name, self._format_size(file_size), file_path)
        
        if len(all_files) > 20:
            table.add_row("...", f"...等 {len(all_files)-20} 个文件", "...", "...")
        
        self.console.print(table)
        
        # 确认是否继续
        confirm = input(f"\n是否开始上传这 {len(all_files)} 个文件? (y/n): ").strip().lower()
        if confirm != 'y':
            return []
        
        results = []
        success_count = 0
        fail_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TimeRemainingColumn(),
        ) as progress:
            main_task = progress.add_task(f"批量上传", total=len(all_files))
            
            for i, file_path in enumerate(all_files, 1):
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)
                
                progress.update(main_task, description=f"正在上传: {file_name}")
                
                try:
                    if upload_mode == "fast":
                        result = self.upload_file_fast(file_path, show_progress=False)
                    else:
                        result = self.upload_file_stream(file_path, show_progress=False)
                    
                    if result["success"]:
                        result["file_path"] = file_path
                        results.append(result)
                        success_count += 1
                        progress.console.print(f"[green]✓ 上传成功: {file_name} ({self._format_size(file_size)})")
                        # 显示CDN地址
                        cdn_url = result.get("cdn_url", "")
                        oss_url = result.get("oss_url", "")
                        if cdn_url:
                            progress.console.print(f"[cyan]   OSS地址: {oss_url}[/cyan]")
                            progress.console.print(f"[cyan]   CDN地址: {cdn_url}[/cyan]")
                    else:
                        result["file_path"] = file_path
                        result["success"] = False
                        results.append(result)
                        fail_count += 1
                        progress.console.print(f"[red]✗ 上传失败: {file_name} - {result.get('error', '未知错误')}")
                        
                except Exception as e:
                    results.append({
                        "file_path": file_path,
                        "success": False,
                        "error": str(e)
                    })
                    fail_count += 1
                    progress.console.print(f"[red]✗ 上传异常: {file_name} - {str(e)[:100]}")
                
                progress.update(main_task, advance=1)
        
        return results
    
    def display_batch_results(self, results):
        """显示批量上传结果"""
        if not results:
            self.console.print("\n没有上传结果", style="yellow")
            return
        
        success_results = [r for r in results if r.get("success")]
        fail_results = [r for r in results if not r.get("success")]
        
        # 显示统计信息
        self.console.print("\n" + "="*60)
        self.console.print("批量上传结果统计", style="bold cyan")
        self.console.print("="*60)
        
        stat_table = Table(box=box.SIMPLE)
        stat_table.add_column("项目", style="cyan", width=15)
        stat_table.add_column("数量", style="green", width=10)
        stat_table.add_column("百分比", style="yellow", width=10)
        
        total = len(results)
        success = len(success_results)
        fail = len(fail_results)
        
        stat_table.add_row("总文件数", str(total), "100%")
        stat_table.add_row("成功数", str(success), f"{success/total*100:.1f}%" if total > 0 else "0%")
        stat_table.add_row("失败数", str(fail), f"{fail/total*100:.1f}%" if total > 0 else "0%")
        
        self.console.print(stat_table)
        
        # 显示成功文件详情
        if success_results:
            self.console.print(f"\n[bold green]✓ 上传成功的文件 ({len(success_results)} 个):[/bold green]")
            success_table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta")
            success_table.add_column("序号", style="cyan", width=6)
            success_table.add_column("文件名", style="green", width=30)
            success_table.add_column("大小", style="yellow", width=12)
            success_table.add_column("CDN地址", style="blue")
            
            for i, result in enumerate(success_results, 1):
                file_name = os.path.basename(result["file_path"])
                cdn_url = result.get("cdn_url", "")
                file_size = result.get("file_size", 0)
                
                # 缩短文件名显示
                if len(file_name) > 25:
                    display_name = file_name[:22] + "..."
                else:
                    display_name = file_name
                
                success_table.add_row(
                    str(i),
                    display_name,
                    self._format_size(file_size) if file_size else "N/A",
                    cdn_url
                )
            
            self.console.print(success_table)
            
            # 询问是否复制所有链接到文件
            if success_results:
                confirm = input(f"\n是否将成功的CDN链接保存到文件? (y/n): ").strip().lower()
                if confirm == 'y':
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"upload_results_{timestamp}.txt"
                    
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(f"批量上传结果 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write(f"成功: {len(success_results)} 个, 失败: {len(fail_results)} 个\n")
                        f.write("="*60 + "\n\n")
                        
                        for i, result in enumerate(success_results, 1):
                            file_name = os.path.basename(result["file_path"])
                            cdn_url = result.get("cdn_url", "")
                            f.write(f"{i}. {file_name}\n")
                            f.write(f"   链接: {cdn_url}\n")
                            f.write(f"   大小: {self._format_size(result.get('file_size', 0))}\n")
                            f.write(f"   时间: {result.get('upload_time', 'N/A')}\n\n")
                    
                    self.console.print(f"[green]✓ 结果已保存到: {filename}")
        
        # 显示失败文件详情
        if fail_results:
            self.console.print(f"\n[bold red]✗ 上传失败的文件 ({len(fail_results)} 个):[/bold red]")
            fail_table = Table(box=box.ROUNDED, show_header=True, header_style="bold red")
            fail_table.add_column("序号", style="cyan", width=6)
            fail_table.add_column("文件名", style="green", width=30)
            fail_table.add_column("错误信息", style="red")
            
            for i, result in enumerate(fail_results, 1):
                file_name = os.path.basename(result["file_path"])
                error_msg = result.get("error", "未知错误")
                
                if len(file_name) > 25:
                    display_name = file_name[:22] + "..."
                else:
                    display_name = file_name
                
                if len(error_msg) > 100:
                    display_error = error_msg[:97] + "..."
                else:
                    display_error = error_msg
                
                fail_table.add_row(str(i), display_name, display_error)
            
            self.console.print(fail_table)
        
        # 显示总结
        self.console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
        if success > 0 and fail == 0:
            self.console.print("[bold green]🎉 所有文件上传成功![/bold green]")
        elif success > 0 and fail > 0:
            self.console.print(f"[bold yellow]⚠  {success} 个成功, {fail} 个失败[/bold yellow]")
        else:
            self.console.print("[bold red]❌ 所有文件上传失败[/bold red]")

def main():
    uploader = CCWOSSUploader()
    console = Console()
    
    # 显示欢迎界面
    console.print(Panel.fit(
        """🎬 CCW OSS 高速文件上传工具 🎬
支持大文件、多线程、断点续传、批量上传、文件删除""",
        border_style="cyan",
        padding=(1, 2)
    ))
    
    # 登录
    while True:
        console.print("\n[bold cyan]请选择登录方式:[/bold cyan]")
        console.print("1. 密码登录")
        console.print("2. 使用CCW Token登录")
        console.print("3. 退出")
        
        choice = console.input("请选择 (1/2/3): ").strip()
        
        if choice == '1':
            login_id = console.input("请输入登录ID: ").strip()
            # 使用getpass安全输入密码
            try:
                password = getpass.getpass("请输入密码: ")
            except Exception as e:
                console.print(f"[yellow]警告: 无法隐藏密码输入，请确保在终端中运行[/yellow]")
                password = console.input("请输入密码: ")
            
            with console.status("正在登录..."):
                if uploader.password_login(login_id, password):
                    console.print("[bold green]登录成功![/bold green]")
                    break
                else:
                    console.print("[bold red]登录失败，请重试[/bold red]")
                    
        elif choice == '2':
            ccw_token = console.input("请输入CCW Token: ").strip()
            user_id = console.input("请输入用户ID: ").strip()
            
            if uploader.token_login(ccw_token, user_id):
                break
            else:
                console.print("[bold red]Token设置失败，请重试[/bold red]")
        elif choice == '3':
            console.print("感谢使用！")
            return
        else:
            console.print("[yellow]无效选择，请重新输入[/yellow]")
    
    # 主菜单
    while True:
        console.print("\n" + "="*60)
        console.print("[bold cyan]主菜单[/bold cyan]")
        console.print("="*60)
        console.print("1. 上传单个文件")
        console.print("2. 批量上传文件夹")
        console.print("3. 删除单个文件")
        console.print("4. 批量删除文件")
        console.print("5. 从文件批量删除")
        console.print("6. 退出")
        
        main_choice = console.input("请选择 (1/2/3/4/5/6): ").strip()
        
        if main_choice == '1':
            # 单个文件上传
            console.print("\n[bold cyan]单个文件上传[/bold cyan]")
            console.print("-"*30)
            
            file_path = console.input("请输入要上传的文件路径 (输入q返回主菜单): ").strip().strip('"')
            
            if file_path.lower() == 'q':
                continue
                
            if not file_path or not os.path.exists(file_path):
                console.print("[bold red]✗ 文件路径无效或文件不存在[/bold red]")
                continue
            
            if os.path.isdir(file_path):
                console.print("[yellow]⚠ 这是一个文件夹，请使用批量上传功能[/yellow]")
                continue
            
            try:
                file_size = os.path.getsize(file_path)
                file_name = os.path.basename(file_path)
                
                # 显示文件信息
                table = Table(show_header=False, box=box.SIMPLE)
                table.add_column("属性", style="cyan", width=15)
                table.add_column("值", style="green")
                
                table.add_row("文件名称", file_name)
                table.add_row("文件大小", uploader._format_size(file_size))
                table.add_row("创建时间", time.ctime(os.path.getctime(file_path)))
                table.add_row("修改时间", time.ctime(os.path.getmtime(file_path)))
                
                console.print(table)
                
                console.print("\n[bold cyan]请选择上传模式:[/bold cyan]")
                console.print("1. 标准上传 (带进度条)")
                console.print("2. 高速上传 (多线程，适合大文件)")
                
                mode_choice = console.input("请选择 (1/2，默认2): ").strip() or "2"
                
                confirm = console.input(f"\n是否开始上传 '{file_name}'? (y/n, 默认y): ").strip().lower() or "y"
                
                if confirm != 'y':
                    continue
                
                start_time = time.time()
                
                if mode_choice == '1':
                    console.print(f"\n[bold cyan]开始标准上传: {file_name}[/bold cyan]")
                    result = uploader.upload_file_stream(file_path)
                else:
                    console.print(f"\n[bold cyan]开始高速上传: {file_name}[/bold cyan]")
                    result = uploader.upload_file_fast(file_path)
                
                end_time = time.time()
                upload_time = end_time - start_time
                
                if result["success"]:
                    console.print("\n" + "="*50)
                    console.print("[bold green]🎉 上传完成![/bold green]")
                    console.print("="*50)
                    
                    result_table = Table(show_header=False, box=None)
                    result_table.add_column("项目", style="cyan", width=15)
                    result_table.add_column("详情", style="green")
                    
                    result_table.add_row("原始文件名", result.get('original_filename', file_name))
                    result_table.add_row("文件大小", uploader._format_size(result["file_size"]))
                    result_table.add_row("上传时间", f"{upload_time:.2f}秒")
                    result_table.add_row("平均速度", f"{result['file_size'] / upload_time / 1024 / 1024:.2f} MB/s")
                    result_table.add_row("存储路径", result['object_key'])
                    result_table.add_row("OSS地址", result['oss_url'])
                    result_table.add_row("CDN地址", result['cdn_url'])
                    
                    if result.get("multipart"):
                        result_table.add_row("上传模式", f"分块上传 ({result.get('parts', 1)} 个分块)")
                    else:
                        result_table.add_row("上传模式", "简单上传")
                    
                    console.print(result_table)
                    
                    console.print(f"\n[bold yellow]📋 下载时将显示文件名: {result.get('original_filename', file_name)}[/bold yellow]")
                    
                    # 尝试复制到剪贴板
                    try:
                        import pyperclip
                        pyperclip.copy(result['cdn_url'])
                        console.print("[green]✓ CDN地址已复制到剪贴板[/green]")
                    except:
                        console.print("[yellow]⚠ 无法复制到剪贴板，请手动复制CDN地址[/yellow]")
                        console.print(f"[cyan]CDN地址: {result['cdn_url']}[/cyan]")
                        
                else:
                    console.print(f"\n[bold red]❌ 上传失败: {result.get('error', '未知错误')}[/bold red]")
                    
            except Exception as e:
                console.print(f"\n[bold red]❌ 上传过程中发生错误: {str(e)}[/bold red]")
                if console.input("是否查看详细错误信息? (y/n): ").lower() == 'y':
                    import traceback
                    console.print(traceback.format_exc())
        
        elif main_choice == '2':
            # 批量上传
            console.print("\n[bold cyan]批量上传文件夹[/bold cyan]")
            console.print("-"*30)
            
            folder_path = console.input("请输入文件夹路径 (输入q返回主菜单): ").strip().strip('"')
            
            if folder_path.lower() == 'q':
                continue
            
            if not folder_path or not os.path.exists(folder_path):
                console.print("[bold red]✗ 文件夹路径无效或不存在[/bold red]")
                continue
            
            if not os.path.isdir(folder_path):
                console.print("[yellow]⚠ 这不是一个文件夹[/yellow]")
                continue
            
            console.print("\n[bold cyan]上传设置[/bold cyan]")
            console.print("1. 上传所有文件")
            console.print("2. 按扩展名过滤")
            
            filter_choice = console.input("请选择 (1/2，默认1): ").strip() or "1"
            
            extensions = None
            if filter_choice == '2':
                exts_input = console.input("请输入文件扩展名(用逗号分隔，如 .mp4,.avi,.mov): ").strip()
                if exts_input:
                    extensions = [ext.strip() for ext in exts_input.split(',') if ext.strip()]
            
            console.print("\n[bold cyan]上传模式[/bold cyan]")
            console.print("1. 标准模式")
            console.print("2. 高速模式 (推荐)")
            
            upload_mode_choice = console.input("请选择 (1/2，默认2): ").strip() or "2"
            upload_mode = "stream" if upload_mode_choice == "1" else "fast"
            
            try:
                console.print(f"\n[bold cyan]开始批量上传文件夹: {folder_path}[/bold cyan]")
                results = uploader.batch_upload(folder_path, upload_mode, extensions)
                
                if results:
                    uploader.display_batch_results(results)
                else:
                    console.print("[yellow]没有文件被上传[/yellow]")
                    
            except Exception as e:
                console.print(f"\n[bold red]❌ 批量上传过程中发生错误: {str(e)}[/bold red]")
                if console.input("是否查看详细错误信息? (y/n): ").lower() == 'y':
                    import traceback
                    console.print(traceback.format_exc())
        
        elif main_choice == '3':
            # 删除单个文件
            console.print("\n[bold cyan]删除单个文件[/bold cyan]")
            console.print("-"*30)
            console.print("[yellow]支持以下格式:[/yellow]")
            console.print("1. OSS URL: https://zhishi.oss-cn-beijing.aliyuncs.com/path/to/file")
            console.print("2. CDN URL: https://m.ccw.site/path/to/file")
            console.print("3. Object Key: path/to/file")
            
            url_or_key = console.input("\n请输入文件URL或Object Key (输入q返回主菜单): ").strip()
            
            if url_or_key.lower() == 'q':
                continue
            
            if not url_or_key:
                console.print("[bold red]✗ 输入不能为空[/bold red]")
                continue
            
            try:
                result = uploader.delete_file(url_or_key, confirm_before_delete=True)
                
                if result.get("success"):
                    console.print(f"\n[bold green]✓ 文件删除成功![/bold green]")
                elif result.get("cancelled"):
                    console.print(f"\n[yellow]⚠ 删除操作已取消[/yellow]")
                else:
                    console.print(f"\n[bold red]✗ 文件删除失败: {result.get('error', '未知错误')}[/bold red]")
                    
            except Exception as e:
                console.print(f"\n[bold red]❌ 删除过程中发生错误: {str(e)}[/bold red]")
                if console.input("是否查看详细错误信息? (y/n): ").lower() == 'y':
                    import traceback
                    console.print(traceback.format_exc())
        
        elif main_choice == '4':
            # 批量删除文件
            console.print("\n[bold cyan]批量删除文件[/bold cyan]")
            console.print("-"*30)
            console.print("[yellow]请输入文件URL或Object Key列表[/yellow]")
            console.print("每行输入一个，输入空行结束")
            console.print("支持格式:")
            console.print("  - OSS URL: https://zhishi.oss-cn-beijing.aliyuncs.com/path/to/file")
            console.print("  - CDN URL: https://m.ccw.site/path/to/file")
            console.print("  - Object Key: path/to/file")
            
            urls_or_keys = []
            while True:
                line = console.input(f"第 {len(urls_or_keys)+1} 个 (直接回车结束输入): ").strip()
                if not line:
                    break
                urls_or_keys.append(line)
            
            if not urls_or_keys:
                console.print("[yellow]没有输入任何文件[/yellow]")
                continue
            
            try:
                results = uploader.batch_delete(urls_or_keys, confirm_before_delete=True)
                
                if results:
                    success_count = sum(1 for r in results if r.get("success"))
                    fail_count = len(results) - success_count
                    
                    console.print(f"\n[bold cyan]批量删除完成[/bold cyan]")
                    console.print(f"总计: {len(results)} 个文件")
                    console.print(f"成功: {success_count} 个")
                    console.print(f"失败: {fail_count} 个")
                    
                    # 询问是否保存结果
                    save_choice = console.input("\n是否保存删除结果到文件? (y/n): ").strip().lower()
                    if save_choice == 'y':
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"delete_results_{timestamp}.txt"
                        
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(f"批量删除结果 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"总计: {len(results)} 个, 成功: {success_count} 个, 失败: {fail_count} 个\n")
                            f.write("="*60 + "\n\n")
                            
                            for i, result in enumerate(results, 1):
                                if result.get("success"):
                                    f.write(f"{i}. [成功] {result.get('object_key', 'N/A')}\n")
                                    f.write(f"   删除时间: {result.get('deleted_at', 'N/A')}\n\n")
                                else:
                                    f.write(f"{i}. [失败] {result.get('object_key', result.get('original_input', 'N/A'))}\n")
                                    f.write(f"   错误: {result.get('error', '未知错误')}\n\n")
                        
                        console.print(f"[green]✓ 结果已保存到: {filename}")
                else:
                    console.print("[yellow]没有文件被删除[/yellow]")
                    
            except Exception as e:
                console.print(f"\n[bold red]❌ 批量删除过程中发生错误: {str(e)}[/bold red]")
                if console.input("是否查看详细错误信息? (y/n): ").lower() == 'y':
                    import traceback
                    console.print(traceback.format_exc())
        
        elif main_choice == '5':
            # 从文件批量删除
            console.print("\n[bold cyan]从文件批量删除[/bold cyan]")
            console.print("-"*30)
            console.print("[yellow]从文件中读取URL或Object Key列表进行批量删除[/yellow]")
            console.print("文件格式: 每行一个URL或Object Key，支持#开头的注释行")
            
            file_path = console.input("\n请输入文件路径 (输入q返回主菜单): ").strip().strip('"')
            
            if file_path.lower() == 'q':
                continue
            
            if not file_path or not os.path.exists(file_path):
                console.print("[bold red]✗ 文件路径无效或文件不存在[/bold red]")
                continue
            
            try:
                results = uploader.delete_from_file(file_path, confirm_before_delete=True)
                
                if results:
                    success_count = sum(1 for r in results if r.get("success"))
                    fail_count = len(results) - success_count
                    
                    console.print(f"\n[bold cyan]批量删除完成[/bold cyan]")
                    console.print(f"总计: {len(results)} 个文件")
                    console.print(f"成功: {success_count} 个")
                    console.print(f"失败: {fail_count} 个")
                else:
                    console.print("[yellow]没有文件被删除[/yellow]")
                    
            except Exception as e:
                console.print(f"\n[bold red]❌ 批量删除过程中发生错误: {str(e)}[/bold red]")
                if console.input("是否查看详细错误信息? (y/n): ").lower() == 'y':
                    import traceback
                    console.print(traceback.format_exc())
        
        elif main_choice == '6':
            console.print("再见！")
            break
        
        else:
            console.print("[yellow]无效选择，请重新输入[/yellow]")
        
        # 询问是否继续
        if main_choice in ['1', '2', '3', '4', '5']:
            continue_choice = console.input("\n是否返回主菜单? (y/n, 默认y): ").strip().lower() or "y"
            if continue_choice != 'y':
                console.print("再见！")
                break

if __name__ == "__main__":
    # 检查依赖
    required_packages = {
        'requests': 'requests',
        'Crypto': 'pycryptodome',
        'rich': 'rich',
    }
    
    missing_packages = []
    for package, install_name in required_packages.items():
        try:
            if package == 'Crypto':
                __import__('Crypto.Cipher')
            else:
                __import__(package)
        except ImportError:
            missing_packages.append(install_name)
    
    if missing_packages:
        print("缺少必要的依赖包，请安装:")
        print(f"pip install {' '.join(missing_packages)}")
        
        # 询问是否自动安装
        try:
            import sys
            if sys.stdin.isatty():  # 只有在交互式终端中才询问
                install_choice = input("是否自动安装? (y/n): ").lower()
                if install_choice == 'y':
                    import subprocess
                    subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_packages)
                    print("依赖安装完成，请重新运行程序")
                else:
                    print("请手动安装依赖后重新运行")
            else:
                print("请手动安装依赖后重新运行")
        except:
            print("请手动安装依赖后重新运行")
        exit(1)
    
    try:
        import aiohttp
    except ImportError:
        print("未安装aiohttp，部分异步功能将不可用")
        print("可运行: pip install aiohttp")
    
    try:
        import pyperclip
    except ImportError:
        print("未安装pyperclip，无法自动复制链接到剪贴板")
        print("可运行: pip install pyperclip")
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        print(f"\n程序运行出错: {e}")
        import traceback
        traceback.print_exc()