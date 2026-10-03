#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebDAV Note - Recursive sync of note/ folder (English UI only)
"""

import os
import json
import ssl
import time
import base64
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.utils import platform

# ===== WebDAV config =====
WEBDAV_USER = 'zhw63@189.cn'
WEBDAV_BASE = 'https://dav.jianguoyun.com/dav/'
REMOTE_DIR = 'note/'
REMOTE_DIR_URL = WEBDAV_BASE + REMOTE_DIR
REMOTE_FILE_NAME = 'zhw63.note'

# SSL: disable verification (self-use, only JianguoYun)
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ===== Path config =====
if platform == 'android':
    from android import mActivity
    BASE_DIR = mActivity.getExternalFilesDir(None).getAbsolutePath()
else:
    BASE_DIR = os.path.join(os.path.expanduser('~'), 'ftptool')

TXT_DIR = os.path.join(BASE_DIR, 'note')
PASSWORD_FILE = os.path.join(BASE_DIR, 'file', 'webdav-password.txt')


def ensure_dirs():
    os.makedirs(TXT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(PASSWORD_FILE), exist_ok=True)


def load_password():
    try:
        if os.path.exists(PASSWORD_FILE):
            with open(PASSWORD_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except Exception as e:
        print(f'load_password error: {e}')
    return ''


def save_password(pwd):
    try:
        ensure_dirs()
        with open(PASSWORD_FILE, 'w', encoding='utf-8') as f:
            f.write(pwd)
        return True
    except Exception as e:
        print(f'save_password error: {e}')
        return False


def make_auth_header():
    pwd = load_password()
    if not pwd:
        raise Exception('Password not set')
    token = base64.b64encode(f'{WEBDAV_USER}:{pwd}'.encode('utf-8')).decode('ascii')
    return f'Basic {token}'


def http_request(method, url, data=None, timeout=30, depth=None, retries=3):
    auth = make_auth_header()
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header('Authorization', auth)
        req.add_header('User-Agent', 'Mozilla/5.0 (Linux; Android 13)')
        if depth is not None:
            req.add_header('Depth', str(depth))
        if method == 'PROPFIND':
            req.add_header('Content-Type', 'application/xml')
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except Exception as e:
            last_err = e
            print(f'HTTP {method} {url} attempt {attempt + 1} failed: {e}')
            if attempt < retries - 1:
                time.sleep(1)
    raise last_err


# ===== WebDAV helpers =====

NS = {'d': 'DAV:'}


def walk_remote(rel_dir='', visited=None, depth=0):
    if visited is None:
        visited = set()
    if depth > 8:
        return []
    if rel_dir in visited:
        return []
    visited.add(rel_dir)

    base = WEBDAV_BASE + REMOTE_DIR
    if rel_dir:
        parts = rel_dir.rstrip('/').split('/')
        encoded = '/'.join(urllib.parse.quote(p, safe='') for p in parts)
        url = base + encoded + '/'
    else:
        url = base

    status, body = http_request('PROPFIND', url, depth=1)
    if status not in (200, 207):
        raise Exception(f'PROPFIND {rel_dir} HTTP {status}')

    items = []
    text = body.decode('utf-8', errors='replace')
    root = ET.fromstring(text)

    for resp in root.findall('d:response', NS):
        href_el = resp.find('d:href', NS)
        if href_el is None or not href_el.text:
            continue
        href = href_el.text
        href_name = href.rstrip('/').split('/')[-1]
        href_name = urllib.parse.unquote(href_name)

        if rel_dir:
            if href_name == os.path.basename(rel_dir.rstrip('/')):
                continue
        else:
            if href.rstrip('/') == '/dav/note':
                continue

        if not href_name:
            continue

        propstat = resp.find('d:propstat', NS)
        prop = propstat.find('d:prop', NS) if propstat is not None else None

        is_dir = False
        if prop is not None:
            rt = prop.find('d:resourcetype', NS)
            is_dir = (rt is not None and rt.find('d:collection', NS) is not None)

        size = 0
        if prop is not None:
            size_el = prop.find('d:getcontentlength', NS)
            if size_el is not None and size_el.text:
                try:
                    size = int(size_el.text)
                except ValueError:
                    size = 0

        if rel_dir:
            rel_path = f'{rel_dir.rstrip("/")}/{href_name}'
        else:
            rel_path = href_name

        if is_dir:
            sub_items = walk_remote(rel_path, visited, depth + 1)
            items.extend(sub_items)
        else:
            items.append((rel_path, size))

    return items


def download_one(rel_path, remote_size, stats):
    """Download one file if needed. rel_path uses forward slashes."""
    local_path = os.path.join(TXT_DIR, *rel_path.split('/'))
    force = (rel_path == REMOTE_FILE_NAME)
    if not force and os.path.exists(local_path) and os.path.getsize(local_path) == remote_size:
        stats['skip'] += 1
        return
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    url = REMOTE_DIR_URL + urllib.parse.quote(rel_path)
    status, body = http_request('GET', url)
    print(f'GET {rel_path} status={status} size={len(body)}')
    if status != 200:
        raise Exception(f'GET {rel_path} HTTP {status}')
    with open(local_path, 'wb') as f:
        f.write(body)
    stats['new'] += 1


def ensure_remote_dir(rel_dir):
    """Create remote directory (and all parents) via MKCOL. rel_dir uses forward slashes."""
    if not rel_dir:
        return True
    parts = rel_dir.strip('/').split('/')
    current = ''
    for part in parts:
        if not part:
            continue
        current = f'{current}/{part}' if current else part
        url = REMOTE_DIR_URL + urllib.parse.quote(current) + '/'
        try:
            status, body = http_request('MKCOL', url, retries=1)
            # 201 = created, 405 = already exists
            if status not in (201, 405):
                print(f'MKCOL {current} HTTP {status}')
        except Exception as e:
            print(f'MKCOL {current} error: {e}')
    return True


def upload_one(rel_path):
    """Upload one file if needed. rel_path uses forward slashes."""
    local_path = os.path.join(TXT_DIR, *rel_path.split('/'))
    if not os.path.isfile(local_path):
        return False
    local_size = os.path.getsize(local_path)
    url = REMOTE_DIR_URL + urllib.parse.quote(rel_path)

    # Ensure parent directory exists on remote
    parent_dir = '/'.join(rel_path.split('/')[:-1])
    if parent_dir:
        ensure_remote_dir(parent_dir)

    cloud_size = None
    try:
        status, body = http_request('PROPFIND', url, depth=0)
        if status in (200, 207):
            text = body.decode('utf-8', errors='replace')
            root = ET.fromstring(text)
            for resp in root.findall('d:response', NS):
                href_el = resp.find('d:href', NS)
                if href_el is None or not href_el.text:
                    continue
                propstat = resp.find('d:propstat', NS)
                prop = propstat.find('d:prop', NS) if propstat is not None else None
                if prop is None:
                    continue
                size_el = prop.find('d:getcontentlength', NS)
                if size_el is not None and size_el.text:
                    try:
                        cloud_size = int(size_el.text)
                    except ValueError:
                        cloud_size = None
                break
    except Exception as e:
        print(f'PROPFIND {rel_path} error: {e}')
    if cloud_size is not None and cloud_size == local_size:
        return False
    with open(local_path, 'rb') as f:
        data = f.read()
    status, body = http_request('PUT', url, data=data)
    print(f'PUT {rel_path} status={status} size={len(data)}')
    if status not in (200, 201, 204):
        raise Exception(f'PUT {rel_path} HTTP {status}')
    return True


def walk_local(base):
    """Walk local dir, return list of relative paths with forward slashes."""
    results = []
    for root, dirs, files in os.walk(base):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, base).replace(os.sep, '/')
            results.append(rel)
    return results


# ===== App =====

class FTPApp(App):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.status_text = 'Ready'

    def build(self):
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_EXTERNAL_STORAGE
                ])
            except Exception as e:
                print(f'permission error: {e}')

        Window.clearcolor = (0.12, 0.12, 0.14, 1)

        main = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))

        title = Label(
            text='WebDAV Note',
            font_size=dp(26),
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(50)
        )
        main.add_widget(title)

        self.pwd_box = BoxLayout(orientation='horizontal', size_hint_y=None,
                                 height=dp(45), spacing=dp(8))
        self.pwd_box.add_widget(Label(text='Password:', size_hint_x=0.3, color=(1, 1, 1, 1)))
        self.pwd_input = TextInput(multiline=False, password=True, size_hint_x=0.7)
        self.pwd_box.add_widget(self.pwd_input)
        main.add_widget(self.pwd_box)

        self.save_btn = Button(
            text='SAVE PASSWORD',
            font_size=dp(18),
            background_color=(0.5, 0.5, 0.5, 1),
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(45)
        )
        self.save_btn.bind(on_press=self.on_save_pwd)
        main.add_widget(self.save_btn)

        self.download_btn = Button(
            text='DOWNLOAD',
            font_size=dp(32),
            background_color=(0.2, 0.5, 0.8, 1),
            color=(1, 1, 1, 1),
            size_hint_y=0.4
        )
        self.download_btn.bind(on_press=self.on_download)
        main.add_widget(self.download_btn)

        self.upload_btn = Button(
            text='UPLOAD',
            font_size=dp(32),
            background_color=(0.2, 0.7, 0.3, 1),
            color=(1, 1, 1, 1),
            size_hint_y=0.4
        )
        self.upload_btn.bind(on_press=self.on_upload)
        main.add_widget(self.upload_btn)

        self.status_label = Label(
            text='Ready',
            font_size=dp(16),
            color=(0.8, 0.8, 0.8, 1),
            size_hint_y=None,
            height=dp(40),
            halign='center'
        )
        main.add_widget(self.status_label)

        Clock.schedule_once(lambda dt: self.preload_pwd(), 0.2)
        return main

    def hide_pwd_ui(self):
        self.pwd_box.opacity = 0
        self.pwd_box.disabled = True
        self.pwd_box.height = 0
        self.save_btn.opacity = 0
        self.save_btn.disabled = True
        self.save_btn.height = 0

    def preload_pwd(self):
        pwd = load_password()
        if pwd:
            self.hide_pwd_ui()
            self.update_status('Password loaded')
        else:
            self.update_status('Please enter password and save')

    def update_status(self, msg):
        self.status_label.text = msg
        print(f'STATUS: {msg}')

    def on_save_pwd(self, instance):
        pwd = self.pwd_input.text.strip()
        if not pwd:
            self.update_status('Password is empty')
            return
        if save_password(pwd):
            self.hide_pwd_ui()
            self.update_status('Password saved')
        else:
            self.update_status('Password save failed')

    # ===== DOWNLOAD =====

    def on_download(self, instance):
        self.download_btn.disabled = True
        self.update_status('Connecting...')
        Clock.schedule_once(lambda dt: self._do_download(), 0.05)

    def _do_download(self):
        try:
            ensure_dirs()
            self.update_status('Listing...')
            items = walk_remote()

            if not items:
                self.update_status('No files on remote')
                return

            stats = {'new': 0, 'skip': 0}
            for rel_path, size in items:
                try:
                    download_one(rel_path, size, stats)
                except Exception as e:
                    print(f'Download {rel_path} failed: {e}')

            note_local = os.path.join(TXT_DIR, REMOTE_FILE_NAME)
            if os.path.exists(note_local):
                try:
                    self.update_status('Exporting...')
                    with open(note_local, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    for tab in data.get('tabs', []):
                        if tab.get('type') == 'text':
                            title = tab.get('title', 'untitled')
                            content = tab.get('content', '')
                            safe = title.replace('/', '_').replace('\\', '_').replace(':', '_')
                            with open(os.path.join(TXT_DIR, f'{safe}.txt'), 'w', encoding='utf-8') as f:
                                f.write(content)
                except Exception as e:
                    print(f'Export error: {e}')

            self.update_status(f'Done: {stats["new"]} new, {stats["skip"]} skip')

        except Exception as e:
            self.update_status(f'Error: {str(e)[:50]}')
        finally:
            self.download_btn.disabled = False

    # ===== UPLOAD =====

    def on_upload(self, instance):
        self.upload_btn.disabled = True
        self.update_status('Connecting...')
        Clock.schedule_once(lambda dt: self._do_upload(), 0.05)

    def _do_upload(self):
        try:
            note_local = os.path.join(TXT_DIR, REMOTE_FILE_NAME)
            merged_names = set()

            # Step 1: merge txt into zhw63.note (only for existing titles)
            if os.path.exists(note_local):
                self.update_status('Reading...')
                with open(note_local, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                changed = 0
                for tab in data.get('tabs', []):
                    if tab.get('type') == 'text':
                        title = tab.get('title', 'untitled')
                        safe = title.replace('/', '_').replace('\\', '_').replace(':', '_')
                        txt_name = f'{safe}.txt'
                        txt_path = os.path.join(TXT_DIR, txt_name)
                        if os.path.exists(txt_path):
                            with open(txt_path, 'r', encoding='utf-8') as f:
                                new_content = f.read()
                            if tab.get('content') != new_content:
                                tab['content'] = new_content
                            merged_names.add(txt_name)
                            changed += 1

                if changed > 0:
                    with open(note_local, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

            # Step 2: create all local directories on remote (including empty ones)
            self.update_status('Creating dirs...')
            for root, dirs, files in os.walk(TXT_DIR):
                for d in dirs:
                    full_dir = os.path.join(root, d)
                    rel_dir = os.path.relpath(full_dir, TXT_DIR).replace(os.sep, '/')
                    try:
                        ensure_remote_dir(rel_dir)
                    except Exception as e:
                        print(f'MKCOL {rel_dir} failed: {e}')

            # Step 3: upload zhw63.note + all other files (only skip .bak and merged txt)
            self.update_status('Uploading...')
            uploaded = 0
            skipped = 0

            # zhw63.note first
            if os.path.exists(note_local):
                try:
                    if upload_one(REMOTE_FILE_NAME):
                        uploaded += 1
                    else:
                        skipped += 1
                except Exception as e:
                    print(f'Upload {REMOTE_FILE_NAME} failed: {e}')

            # Walk local dir, upload all files
            for rel in walk_local(TXT_DIR):
                if rel == REMOTE_FILE_NAME:
                    continue
                if rel in merged_names:
                    continue
                if rel.lower().endswith('.bak'):
                    continue
                try:
                    if upload_one(rel):
                        uploaded += 1
                    else:
                        skipped += 1
                except Exception as e:
                    print(f'Upload {rel} failed: {e}')

            self.update_status(f'Merge: {len(merged_names)}, Upload: {uploaded}, Skip: {skipped}')

        except Exception as e:
            self.update_status(f'Error: {str(e)[:50]}')
        finally:
            self.upload_btn.disabled = False


if __name__ == '__main__':
    FTPApp().run()
