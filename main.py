#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebDAV Note - Download / Upload zhw63.note (English UI only)
"""

import os
import json
import ssl
import base64
import urllib.request
import urllib.error
from datetime import datetime

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
REMOTE_URL = 'https://dav.jianguoyun.com/dav/note/zhw63.note'
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


def http_request(method, url, data=None, timeout=20):
    auth = make_auth_header()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', auth)
    req.add_header('User-Agent', 'KivyWebDAV/1.0')
    if method == 'PROPFIND':
        req.add_header('Depth', '0')
        req.add_header('Content-Type', 'application/xml')
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def remote_exists():
    status, _ = http_request('PROPFIND', REMOTE_URL)
    print(f'PROPFIND status={status}')
    return status in (200, 207)


def download_remote(local_path):
    status, body = http_request('GET', REMOTE_URL)
    print(f'GET status={status} size={len(body)}')
    if status != 200:
        raise Exception(f'HTTP {status}')
    with open(local_path, 'wb') as f:
        f.write(body)


def upload_remote(local_path):
    with open(local_path, 'rb') as f:
        data = f.read()
    status, body = http_request('PUT', REMOTE_URL, data=data)
    print(f'PUT status={status} size={len(data)}')
    if status not in (200, 201, 204):
        raise Exception(f'HTTP {status}')


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

        # Password row
        pwd_box = BoxLayout(orientation='horizontal', size_hint_y=None,
                            height=dp(45), spacing=dp(8))
        pwd_box.add_widget(Label(text='Password:', size_hint_x=0.3, color=(1, 1, 1, 1)))
        self.pwd_input = TextInput(multiline=False, password=True, size_hint_x=0.7)
        pwd_box.add_widget(self.pwd_input)
        main.add_widget(pwd_box)

        # Save password
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

    def preload_pwd(self):
        pwd = load_password()
        if pwd:
            self.pwd_input.text = pwd
            self.update_status('Password loaded')

    def update_status(self, msg):
        self.status_label.text = msg
        print(f'STATUS: {msg}')

    def on_save_pwd(self, instance):
        pwd = self.pwd_input.text.strip()
        if not pwd:
            self.update_status('Password is empty')
            return
        if save_password(pwd):
            self.update_status('Password saved')
        else:
            self.update_status('Password save failed')

    def on_download(self, instance):
        self.download_btn.disabled = True
        self.update_status('Connecting...')
        Clock.schedule_once(lambda dt: self._do_download(), 0.05)

    def _do_download(self):
        try:
            self.update_status('Checking remote...')
            if not remote_exists():
                self.update_status('File not found on remote')
                return

            ensure_dirs()
            note_path = os.path.join(TXT_DIR, REMOTE_FILE_NAME)

            self.update_status('Downloading...')
            download_remote(note_path)

            self.update_status('Exporting...')
            with open(note_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            count = 0
            for tab in data.get('tabs', []):
                if tab.get('type') == 'text':
                    title = tab.get('title', 'untitled')
                    content = tab.get('content', '')
                    safe = title.replace('/', '_').replace('\\', '_').replace(':', '_')
                    with open(os.path.join(TXT_DIR, f'{safe}.txt'), 'w', encoding='utf-8') as f:
                        f.write(content)
                    count += 1

            self.update_status(f'Done: {count} files')

        except Exception as e:
            self.update_status(f'Error: {str(e)[:40]}')
        finally:
            self.download_btn.disabled = False

    def on_upload(self, instance):
        self.upload_btn.disabled = True
        self.update_status('Connecting...')
        Clock.schedule_once(lambda dt: self._do_upload(), 0.05)

    def _do_upload(self):
        try:
            note_path = os.path.join(TXT_DIR, REMOTE_FILE_NAME)

            if not os.path.exists(note_path):
                self.update_status('Download first')
                return

            self.update_status('Reading...')
            with open(note_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            count = 0
            for tab in data.get('tabs', []):
                if tab.get('type') == 'text':
                    title = tab.get('title', 'untitled')
                    txt_path = os.path.join(TXT_DIR, f'{title}.txt')
                    if os.path.exists(txt_path):
                        with open(txt_path, 'r', encoding='utf-8') as f:
                            new_content = f.read()
                        if tab.get('content') != new_content:
                            tab['content'] = new_content
                            count += 1

            if count == 0:
                self.update_status('Nothing to update')
                return

            with open(note_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.update_status('Uploading...')
            upload_remote(note_path)

            self.update_status(f'Done: {count} files')

        except Exception as e:
            self.update_status(f'Error: {str(e)[:40]}')
        finally:
            self.upload_btn.disabled = False


if __name__ == '__main__':
    FTPApp().run()
