#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebDAV note sync - pure urllib, English UI only.
"""

import os
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
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.utils import platform

# ===== Config =====
WEBDAV_USER = 'zhw63@189.cn'
REMOTE_URL = 'https://dav.jianguoyun.com/dav/note/zhw63.note'
LOCAL_FILE_NAME = 'zhw63.note'
DEBUG_LOG = 'debug.log'

# Disable SSL verification (self-use, only connects to JianguoYun)
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


# ===== Local directory (lazy init) =====
_TXT_DIR = None

def get_txt_dir():
    global _TXT_DIR
    if _TXT_DIR is not None:
        return _TXT_DIR
    if platform == 'android':
        from android import mActivity
        base = mActivity.getExternalFilesDir(None).getAbsolutePath()
        path = os.path.join(base, 'fileshare', 'note')
    else:
        path = os.path.join(os.path.expanduser('~'), 'Download', 'fileshare', 'note')
    os.makedirs(path, exist_ok=True)
    _TXT_DIR = path
    return path


def log(msg):
    try:
        d = get_txt_dir()
        p = os.path.join(d, DEBUG_LOG)
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(p, 'a', encoding='utf-8') as f:
            f.write(f'[{ts}] {msg}\n')
    except Exception:
        pass
    print(f'LOG: {msg}')


def password_file_path():
    return os.path.join(get_txt_dir(), 'webdav-password.txt')


def load_password():
    try:
        p = password_file_path()
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except Exception:
        pass
    return ''


def save_password(pwd):
    try:
        with open(password_file_path(), 'w', encoding='utf-8') as f:
            f.write(pwd)
        return True
    except Exception as e:
        log(f'save_password error: {e}')
        return False


def make_auth_header():
    pwd = load_password()
    if not pwd:
        raise Exception('Password not set')
    token = base64.b64encode(f'{WEBDAV_USER}:{pwd}'.encode('utf-8')).decode('ascii')
    return f'Basic {token}'


def http_request(method, url, data=None, timeout=20):
    """Send an HTTP request with Basic Auth. Returns (status, body_bytes)."""
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
    log(f'PROPFIND status={status}')
    return status in (200, 207)


def download_remote(local_path):
    status, body = http_request('GET', REMOTE_URL)
    log(f'GET status={status} size={len(body)}')
    if status != 200:
        raise Exception(f'HTTP {status}')
    with open(local_path, 'wb') as f:
        f.write(body)


def upload_remote(local_path):
    with open(local_path, 'rb') as f:
        data = f.read()
    status, body = http_request('PUT', REMOTE_URL, data=data)
    log(f'PUT status={status} size={len(data)}')
    if status not in (200, 201, 204):
        raise Exception(f'HTTP {status}')


class MiniApp(App):

    def build(self):
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_EXTERNAL_STORAGE
                ])
                log('permission requested')
            except Exception as e:
                log(f'permission request error: {e}')

        Window.clearcolor = (0.12, 0.12, 0.14, 1)

        main = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))

        # Password row
        pwd_box = BoxLayout(orientation='horizontal', size_hint_y=None,
                            height=dp(50), spacing=dp(8))
        pwd_box.add_widget(Label(text='Password:', size_hint_x=0.3, color=(1, 1, 1, 1)))
        self.pwd_input = TextInput(multiline=False, password=True, size_hint_x=0.7)
        pwd_box.add_widget(self.pwd_input)
        main.add_widget(pwd_box)

        # Save password
        save_btn = Button(text='SAVE PASSWORD', size_hint_y=None, height=dp(45))
        save_btn.bind(on_press=self.on_save_pwd)
        main.add_widget(save_btn)

        # Download
        dl_btn = Button(text='DOWNLOAD', size_hint_y=None, height=dp(60), font_size=dp(20))
        dl_btn.bind(on_press=self.on_download)
        main.add_widget(dl_btn)

        # Upload
        ul_btn = Button(text='UPLOAD', size_hint_y=None, height=dp(60), font_size=dp(20))
        ul_btn.bind(on_press=self.on_upload)
        main.add_widget(ul_btn)

        # Log area
        scroll = ScrollView()
        self.log_label = Label(
            text='Ready',
            font_size=dp(12),
            color=(0.9, 0.9, 0.9, 1),
            halign='left',
            valign='top',
            size_hint_y=None,
            text_size=(Window.width - dp(30), None),
        )
        self.log_label.bind(texture_size=self.log_label.setter('size'))
        scroll.add_widget(self.log_label)
        main.add_widget(scroll)

        Clock.schedule_once(lambda dt: self.preload_pwd(), 0.2)
        return main

    def preload_pwd(self):
        pwd = load_password()
        if pwd:
            self.pwd_input.text = pwd
            self.set_log('Password loaded from local file')

    def set_log(self, msg):
        log(msg)
        self.log_label.text = msg

    def on_save_pwd(self, instance):
        pwd = self.pwd_input.text.strip()
        if not pwd:
            self.set_log('Password is empty')
            return
        if save_password(pwd):
            self.set_log('Password saved')
        else:
            self.set_log('Password save failed')

    def on_download(self, instance):
        self.set_log('Downloading...')
        Clock.schedule_once(lambda dt: self._download(), 0.1)

    def _download(self):
        try:
            self.set_log('Checking remote...')
            if not remote_exists():
                self.set_log('Remote file not found')
                return
            local_path = os.path.join(get_txt_dir(), LOCAL_FILE_NAME)
            download_remote(local_path)
            size = os.path.getsize(local_path)
            self.set_log(f'Download OK: {size} bytes')
        except Exception as e:
            self.set_log(f'Download failed: {e}')

    def on_upload(self, instance):
        self.set_log('Uploading...')
        Clock.schedule_once(lambda dt: self._upload(), 0.1)

    def _upload(self):
        try:
            local_path = os.path.join(get_txt_dir(), LOCAL_FILE_NAME)
            if not os.path.exists(local_path):
                self.set_log('Local file not found, download first')
                return
            upload_remote(local_path)
            size = os.path.getsize(local_path)
            self.set_log(f'Upload OK: {size} bytes')
        except Exception as e:
            self.set_log(f'Upload failed: {e}')


if __name__ == '__main__':
    MiniApp().run()
