#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebDAV Note - Download / Upload all files in note/ (English UI only)
"""

import os
import json
import ssl
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


def http_request(method, url, data=None, timeout=20, depth=None):
    auth = make_auth_header()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', auth)
    req.add_header('User-Agent', 'KivyWebDAV/1.0')
    if depth is not None:
        req.add_header('Depth', str(depth))
    if method == 'PROPFIND':
        req.add_header('Content-Type', 'application/xml')
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


# ===== WebDAV operations =====

def list_remote_files():
    """List all files under note/ (skip subdirectories). Returns list of filenames."""
    status, body = http_request('PROPFIND', REMOTE_DIR_URL, depth=1)
    print(f'PROPFIND status={status} size={len(body)}')
    if status not in (200, 207):
        raise Exception(f'PROPFIND HTTP {status}')

    try:
        text = body.decode('utf-8', errors='replace')
        root = ET.fromstring(text)
    except Exception as e:
        raise Exception(f'XML parse error: {e}')

    # Try with DAV: namespace first
    names = []
    ns_candidates = [
        {'d': 'DAV:'},
        {},  # no namespace
    ]
    for ns in ns_candidates:
        responses = root.findall('d:response', ns) if ns else root.findall('response')
        if not responses:
            continue
        for resp in responses:
            href_el = resp.find('d:href', ns) if ns else resp.find('href')
            if href_el is None or not href_el.text:
                continue
            href = urllib.parse.unquote(href_el.text)
            # Skip the directory entry itself
            if href.rstrip('/').endswith('note'):
                # Actually check it's the directory, not a file named "note"
                if href.endswith('/'):
                    continue
            # Skip subdirectories (end with /)
            if href.endswith('/'):
                continue
            name = href.rstrip('/').split('/')[-1]
            if name:
                names.append(name)
        if names:
            break

    return names


def download_one(name):
    """Download one file from remote note/ to local TXT_DIR."""
    url = REMOTE_DIR_URL + urllib.parse.quote(name)
    status, body = http_request('GET', url)
    print(f'GET {name} status={status} size={len(body)}')
    if status != 200:
        raise Exception(f'GET {name} HTTP {status}')
    local_path = os.path.join(TXT_DIR, name)
    with open(local_path, 'wb') as f:
        f.write(body)
    return local_path


def upload_one(name, local_path):
    """Upload one local file to remote note/<name>."""
    url = REMOTE_DIR_URL + urllib.parse.quote(name)
    with open(local_path, 'rb') as f:
        data = f.read()
    status, body = http_request('PUT', url, data=data)
    print(f'PUT {name} status={status} size={len(data)}')
    if status not in (200, 201, 204):
        raise Exception(f'PUT {name} HTTP {status}')


def remote_exists(name):
    url = REMOTE_DIR_URL + urllib.parse.quote(name)
    status, _ = http_request('PROPFIND', url, depth=0)
    print(f'PROPFIND {name} status={status}')
    return status in (200, 207)


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

        # Password row (hidden if password already exists)
        self.pwd_box = BoxLayout(orientation='horizontal', size_hint_y=None,
                                 height=dp(45), spacing=dp(8))
        self.pwd_box.add_widget(Label(text='Password:', size_hint_x=0.3, color=(1, 1, 1, 1)))
        self.pwd_input = TextInput(multiline=False, password=True, size_hint_x=0.7)
        self.pwd_box.add_widget(self.pwd_input)
        main.add_widget(self.pwd_box)

        # Save password (hidden if password already exists)
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

        # Download
        self.download_btn = Button(
            text='DOWNLOAD',
            font_size=dp(32),
            background_color=(0.2, 0.5, 0.8, 1),
            color=(1, 1, 1, 1),
            size_hint_y=0.4
        )
        self.download_btn.bind(on_press=self.on_download)
        main.add_widget(self.download_btn)

        # Upload
        self.upload_btn = Button(
            text='UPLOAD',
            font_size=dp(32),
            background_color=(0.2, 0.7, 0.3, 1),
            color=(1, 1, 1, 1),
            size_hint_y=0.4
        )
        self.upload_btn.bind(on_press=self.on_upload)
        main.add_widget(self.upload_btn)

        # Status
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
            names = list_remote_files()
            print(f'Remote files: {names}')

            if not names:
                self.update_status('No files on remote')
                return

            total = 0
            for name in names:
                try:
                    download_one(name)
                    total += 1
                except Exception as e:
                    print(f'Download {name} failed: {e}')

            # If zhw63.note was downloaded, export tabs to txt
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

            self.update_status(f'Done: {total} files')

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
            merged_names = set()  # filenames that were merged into zhw63.note

            # Step 1: merge txt into zhw63.note
            if os.path.exists(note_local):
                self.update_status('Reading...')
                with open(note_local, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                changed = 0
                for tab in data.get('tabs', []):
                    if tab.get('type') == 'text':
                        title = tab.get('title', 'untitled')
                        safe = title.replace('/', '_').replace('\\', '_').replace(':', '_')
                        txt_path = os.path.join(TXT_DIR, f'{safe}.txt')
                        if os.path.exists(txt_path):
                            with open(txt_path, 'r', encoding='utf-8') as f:
                                new_content = f.read()
                            if tab.get('content') != new_content:
                                tab['content'] = new_content
                            merged_names.add(f'{safe}.txt')
                            changed += 1

                if changed > 0:
                    with open(note_local, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

            # Step 2: upload zhw63.note + other files
            self.update_status('Uploading...')
            uploaded = 0

            if os.path.exists(note_local):
                upload_one(REMOTE_FILE_NAME, note_local)
                uploaded += 1

            for name in os.listdir(TXT_DIR):
                full = os.path.join(TXT_DIR, name)
                if not os.path.isfile(full):
                    continue
                if name == REMOTE_FILE_NAME:
                    continue
                if name in merged_names:
                    continue
                try:
                    upload_one(name, full)
                    uploaded += 1
                except Exception as e:
                    print(f'Upload {name} failed: {e}')

            self.update_status(f'Merge: {len(merged_names)}, Upload: {uploaded}')

        except Exception as e:
            self.update_status(f'Error: {str(e)[:50]}')
        finally:
            self.upload_btn.disabled = False


if __name__ == '__main__':
    FTPApp().run()
