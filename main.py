#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FTP Tool - Download / Upload
"""

import os
import json
from ftplib import FTP, error_perm

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.utils import platform

# ===== 路径配置 =====
CONFIG_DIR = '/storage/emulated/0/Download/fileshare'
CONFIG_FILE = os.path.join(CONFIG_DIR, 'ftp-config.json')


def get_txt_dir():
    """获取 .txt 保存目录"""
    if platform == 'android':
        path = os.path.join(CONFIG_DIR, 'note')
    else:
        path = os.path.join(os.path.expanduser('~'), 'Download', 'fileshare', 'note')
    os.makedirs(path, exist_ok=True)
    return path


TXT_DIR = get_txt_dir()


def load_config():
    """读取本地配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'Config load error: {e}')
    return None


class FTPApp(App):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = load_config()

    def build(self):
        Window.clearcolor = (0.12, 0.12, 0.14, 1)

        main = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(20))

        title = Label(
            text='FTP Tool',
            font_size=dp(28),
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(60)
        )
        main.add_widget(title)

        # 下载按钮
        self.download_btn = Button(
            text='DOWNLOAD',
            font_size=dp(32),
            background_color=(0.2, 0.5, 0.8, 1),
            color=(1, 1, 1, 1),
            size_hint_y=0.4
        )
        self.download_btn.bind(on_press=self.on_download)
        main.add_widget(self.download_btn)

        # 上传按钮
        self.upload_btn = Button(
            text='UPLOAD',
            font_size=dp(32),
            background_color=(0.2, 0.7, 0.3, 1),
            color=(1, 1, 1, 1),
            size_hint_y=0.4
        )
        self.upload_btn.bind(on_press=self.on_upload)
        main.add_widget(self.upload_btn)

        # 状态栏
        self.status_label = Label(
            text='Ready',
            font_size=dp(16),
            color=(0.8, 0.8, 0.8, 1),
            size_hint_y=None,
            height=dp(40),
            halign='center'
        )
        main.add_widget(self.status_label)

        # 检查配置
        if not self.config:
            self.update_status(f'Config not found: ftp-config.json')
        else:
            self.update_status('Ready')

        return main

    def update_status(self, msg):
        self.status_label.text = msg
        print(f'STATUS: {msg}')

    def connect_ftp(self):
        """连接 FTP"""
        if not self.config:
            raise Exception('No config')
        ftp = FTP()
        ftp.connect(self.config['host'], self.config['port'], timeout=15)
        ftp.login(self.config['user'], self.config['pass'])
        ftp.cwd('/')
        return ftp

    def on_download(self, instance):
        if not self.config:
            self.update_status('Config missing')
            return
        self.download_btn.disabled = True
        self.update_status('Connecting...')
        Clock.schedule_once(lambda dt: self._do_download(), 0.05)

    def _do_download(self):
        ftp = None
        try:
            remote_file = self.config['file']
            ftp = self.connect_ftp()
            self.update_status('Downloading...')

            try:
                ftp.size(remote_file)
            except:
                self.update_status('File not found')
                return

            os.makedirs(TXT_DIR, exist_ok=True)
            note_path = os.path.join(TXT_DIR, remote_file)

            with open(note_path, 'wb') as f:
                ftp.retrbinary(f'RETR {remote_file}', f.write)

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
            if ftp:
                try:
                    ftp.quit()
                except:
                    pass
            self.download_btn.disabled = False

    def on_upload(self, instance):
        if not self.config:
            self.update_status('Config missing')
            return
        self.upload_btn.disabled = True
        self.update_status('Connecting...')
        Clock.schedule_once(lambda dt: self._do_upload(), 0.05)

    def _do_upload(self):
        ftp = None
        try:
            remote_file = self.config['file']
            note_path = os.path.join(TXT_DIR, remote_file)

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

            ftp = self.connect_ftp()
            with open(note_path, 'rb') as f:
                ftp.storbinary(f'STOR {remote_file}', f)

            self.update_status(f'Done: {count} files')

        except Exception as e:
            self.update_status(f'Error: {str(e)[:40]}')
        finally:
            if ftp:
                try:
                    ftp.quit()
                except:
                    pass
            self.upload_btn.disabled = False


if __name__ == '__main__':
    FTPApp().run()
