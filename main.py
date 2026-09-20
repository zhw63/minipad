#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebDAV 最小调试版 - 使用 webdav4
"""

import os
from datetime import datetime

from webdav4.client import Client

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

WEBDAV_HOST = 'https://dav.jianguoyun.com/dav/'
WEBDAV_USER = 'zhw63@189.cn'
REMOTE_FILE = 'note/zhw63.note'
LOCAL_FILE_NAME = 'zhw63.note'
DEBUG_LOG = 'debug.log'


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
        path = os.path.join(d, DEBUG_LOG)
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(path, 'a', encoding='utf-8') as f:
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


def make_client():
    pwd = load_password()
    if not pwd:
        raise Exception('Password not set')
    return Client(
        base_url=WEBDAV_HOST,
        auth=(WEBDAV_USER, pwd)
    )


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

        pwd_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=dp(8))
        pwd_box.add_widget(Label(text='密码:', size_hint_x=0.25, color=(1, 1, 1, 1)))
        self.pwd_input = TextInput(multiline=False, password=True, size_hint_x=0.75)
        pwd_box.add_widget(self.pwd_input)
        main.add_widget(pwd_box)

        save_btn = Button(text='保存密码', size_hint_y=None, height=dp(45))
        save_btn.bind(on_press=self.on_save_pwd)
        main.add_widget(save_btn)

        dl_btn = Button(text='DOWNLOAD', size_hint_y=None, height=dp(60), font_size=dp(20))
        dl_btn.bind(on_press=self.on_download)
        main.add_widget(dl_btn)

        ul_btn = Button(text='UPLOAD', size_hint_y=None, height=dp(60), font_size=dp(20))
        ul_btn.bind(on_press=self.on_upload)
        main.add_widget(ul_btn)

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
            self.set_log('本地已有密码，已自动填入')

    def set_log(self, msg):
        log(msg)
        self.log_label.text = msg

    def on_save_pwd(self, instance):
        pwd = self.pwd_input.text.strip()
        if not pwd:
            self.set_log('密码不能为空')
            return
        if save_password(pwd):
            self.set_log('密码已保存')
        else:
            self.set_log('密码保存失败')

    def on_download(self, instance):
        self.set_log('开始下载...')
        Clock.schedule_once(lambda dt: self._download(), 0.1)

    def _download(self):
        try:
            client = make_client()
            self.set_log('已创建 WebDAV 客户端')

            exists = False
            try:
                exists = client.exists(REMOTE_FILE)
            except Exception as e:
                log(f'exists error: {e}')

            if not exists:
                self.set_log('云端没有 note/zhw63.note')
                return

            local_path = os.path.join(get_txt_dir(), LOCAL_FILE_NAME)
            client.download_file(from_path=REMOTE_FILE, to_path=local_path)
            size = os.path.getsize(local_path)
            self.set_log(f'下载成功: {size} 字节 -> {local_path}')
        except Exception as e:
            self.set_log(f'下载失败: {e}')

    def on_upload(self, instance):
        self.set_log('开始上传...')
        Clock.schedule_once(lambda dt: self._upload(), 0.1)

    def _upload(self):
        try:
            local_path = os.path.join(get_txt_dir(), LOCAL_FILE_NAME)
            if not os.path.exists(local_path):
                self.set_log('本地没有 zhw63.note，请先下载')
                return

            client = make_client()
            self.set_log('已创建 WebDAV 客户端')

            client.upload_file(from_path=local_path, to_path=REMOTE_FILE)
            size = os.path.getsize(local_path)
            self.set_log(f'上传成功: {size} 字节')
        except Exception as e:
            self.set_log(f'上传失败: {e}')


if __name__ == '__main__':
    MiniApp().run()
