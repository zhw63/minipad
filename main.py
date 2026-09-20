#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""启动测试版 - 不依赖任何 WebDAV 库"""

import os
from datetime import datetime

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.utils import platform

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
        path = os.path.join(d, 'debug.log')
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(path, 'a', encoding='utf-8') as f:
            f.write(f'[{ts}] {msg}\n')
    except Exception:
        pass
    print(f'LOG: {msg}')


class TestApp(App):

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

        main = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        main.add_widget(Label(text='启动成功!', font_size=dp(30), color=(1, 1, 1, 1)))

        def on_click(instance):
            try:
                d = get_txt_dir()
                p = os.path.join(d, 'test.txt')
                with open(p, 'w', encoding='utf-8') as f:
                    f.write('hello')
                log(f'write ok: {p}')
            except Exception as e:
                log(f'write error: {e}')

        btn = Button(text='测试写文件', size_hint_y=None, height=dp(60))
        btn.bind(on_press=on_click)
        main.add_widget(btn)

        log('build() completed')
        return main


if __name__ == '__main__':
    TestApp().run()
