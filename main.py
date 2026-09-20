#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebDAV Tool - Download / Upload zhw63.note (坚果云)
"""

import os
import json
import io
from datetime import datetime

from webdav3.client import Client

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.utils import platform

# ===== Config =====
WEBDAV_HOST = 'https://dav.jianguoyun.com/dav/'
WEBDAV_USER = 'zhw63@189.cn'
REMOTE_FILE = 'note/zhw63.note'
DEBUG_LOG = 'debug.log'


def get_txt_dir():
    """获取可写的本地目录（Android 使用外部应用专属目录）"""
    if platform == 'android':
        from android import mActivity
        base = mActivity.getExternalFilesDir(None).getAbsolutePath()
        path = os.path.join(base, 'fileshare', 'note')
    else:
        path = os.path.join(os.path.expanduser('~'), 'Download', 'fileshare', 'note')

    os.makedirs(path, exist_ok=True)
    return path


TXT_DIR = get_txt_dir()
PASSWORD_FILE = os.path.join(TXT_DIR, 'webdav-password.txt')


def load_password():
    """从本地读取密码"""
    try:
        if os.path.exists(PASSWORD_FILE):
            with open(PASSWORD_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except Exception as e:
        print(f'Load password error: {e}')
    return ''


def save_password(password):
    """保存密码到本地"""
    try:
        with open(PASSWORD_FILE, 'w', encoding='utf-8') as f:
            f.write(password)
        return True
    except Exception as e:
        print(f'Save password error: {e}')
        return False


def log_to_server(msg):
    """写调试日志到本地文件（保留函数名，稳定后可删除）"""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f'[{timestamp}] {msg}\n'
        log_path = os.path.join(TXT_DIR, DEBUG_LOG)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        print(f'LOG: {msg}')
    except Exception as e:
        print(f'LOG ERROR: {e}')


def get_webdav_client():
    """创建并返回 WebDAV 客户端"""
    password = load_password()
    if not password:
        raise Exception('Password not set')

    options = {
        'webdav_hostname': WEBDAV_HOST,
        'webdav_login': WEBDAV_USER,
        'webdav_password': password
    }
    return Client(options)


class FTPApp(App):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.status_text = 'Ready'

    def build(self):
        log_to_server('=' * 50)
        log_to_server('APP STARTED: build() called')
        log_to_server(f'platform = {platform}')
        log_to_server(f'platform == android? {platform == "android"}')
        log_to_server(f'TXT_DIR = {TXT_DIR}')

        # ===== Permission request =====
        if platform == 'android':
            log_to_server('Entering android permission block')
            try:
                from android.permissions import request_permissions, Permission
                log_to_server('Successfully imported android.permissions')
                log_to_server('Calling request_permissions...')
                request_permissions([
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_EXTERNAL_STORAGE
                ])
                log_to_server('request_permissions() completed')
            except ImportError as e:
                log_to_server(f'ERROR: Failed to import android.permissions: {e}')
            except Exception as e:
                log_to_server(f'ERROR: Permission request failed: {e}')
        else:
            log_to_server('Not Android platform, skipping permission request')

        log_to_server('=' * 50)

        Window.clearcolor = (0.12, 0.12, 0.14, 1)

        main = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))

        title = Label(
            text='WebDAV Tool',
            font_size=dp(24),
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(50)
        )
        main.add_widget(title)

        status_scroll = ScrollView(
            size_hint_y=0.3,
            bar_width=dp(4),
            bar_color=(0.3, 0.5, 0.8, 0.8),
            bar_inactive_color=(0.3, 0.5, 0.8, 0.2)
        )
        self.status_label = Label(
            text=self.status_text,
            font_size=dp(14),
            color=(0.8, 0.8, 0.8, 1),
            halign='left',
            valign='top',
            text_size=(Window.width - dp(40), None),
            size_hint_y=None
        )
        self.status_label.bind(texture_size=self.status_label.setter('size'))
        status_scroll.add_widget(self.status_label)
        main.add_widget(status_scroll)

        btn_layout = BoxLayout(orientation='vertical', spacing=dp(20), size_hint_y=0.5)

        self.download_btn = Button(
            text='DOWNLOAD',
            font_size=dp(28),
            background_color=(0.2, 0.5, 0.8, 1),
            color=(1, 1, 1, 1),
            size_hint_y=0.45
        )
        self.download_btn.bind(on_press=self.on_download)
        btn_layout.add_widget(self.download_btn)

        self.upload_btn = Button(
            text='UPLOAD',
            font_size=dp(28),
            background_color=(0.2, 0.7, 0.3, 1),
            color=(1, 1, 1, 1),
            size_hint_y=0.45
        )
        self.upload_btn.bind(on_press=self.on_upload)
        btn_layout.add_widget(self.upload_btn)

        main.add_widget(btn_layout)

        self.update_status('Ready')

        # ===== 首次运行：如果本地没密码，弹窗让用户输入 =====
        Clock.schedule_once(lambda dt: self.check_password(), 0.3)

        return main

    def check_password(self):
        """检查本地是否已有密码，没有则弹窗输入"""
        if not load_password():
            self.show_password_dialog()

    def show_password_dialog(self):
        """输入密码的弹窗"""
        content = BoxLayout(orientation='vertical', spacing=dp(15), padding=dp(15))

        tip = Label(
            text='First run: please enter WebDAV password',
            font_size=dp(14),
            color=(0.9, 0.9, 0.9, 1),
            size_hint_y=None,
            height=dp(40)
        )
        content.add_widget(tip)

        pwd_input = TextInput(
            multiline=False,
            password=True,
            font_size=dp(18),
            size_hint_y=None,
            height=dp(50)
        )
        content.add_widget(pwd_input)

        save_btn = Button(
            text='SAVE',
            font_size=dp(18),
            background_color=(0.2, 0.7, 0.3, 1),
            size_hint_y=None,
            height=dp(50)
        )
        content.add_widget(save_btn)

        popup = Popup(
            title='WebDAV Password',
            content=content,
            size_hint=(0.9, 0.45),
            auto_dismiss=False
        )

        def on_save(instance):
            pwd = pwd_input.text.strip()
