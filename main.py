#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FTP Tool - Download / Upload
带详细调试信息
"""

import os
import json
from datetime import datetime
from ftplib import FTP, error_perm

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.utils import platform

# ===== 路径配置 =====
CONFIG_DIR = '/storage/emulated/0/Download/fileshare'
CONFIG_FILE = os.path.join(CONFIG_DIR, 'ftp-config.json')
NOTE_DIR = os.path.join(CONFIG_DIR, 'note')


def load_config():
    """读取配置文件"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return {'_error': str(e)}
    return None


class FTPApp(App):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = load_config()
        self.debug_log = []

    def log(self, msg):
        """记录调试信息"""
        ts = datetime.now().strftime('%H:%M:%S')
        line = f'[{ts}] {msg}'
        self.debug_log.append(line)
        print(line)

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
            size_hint_y=0.35
        )
        self.download_btn.bind(on_press=self.on_download)
        main.add_widget(self.download_btn)

        # 上传按钮
        self.upload_btn = Button(
            text='UPLOAD',
            font_size=dp(32),
            background_color=(0.2, 0.7, 0.3, 1),
            color=(1, 1, 1, 1),
            size_hint_y=0.35
        )
        self.upload_btn.bind(on_press=self.on_upload)
        main.add_widget(self.upload_btn)

        # 显示日志按钮
        log_btn = Button(
            text='SHOW LOG',
            font_size=dp(16),
            background_color=(0.3, 0.3, 0.4, 1),
            color=(0.9, 0.9, 0.9, 1),
            size_hint_y=None,
            height=dp(40)
        )
        log_btn.bind(on_press=self.show_log)
        main.add_widget(log_btn)

        # 状态栏
        self.status_label = Label(
            text='Ready',
            font_size=dp(14),
            color=(0.8, 0.8, 0.8, 1),
            size_hint_y=None,
            height=dp(40),
            halign='center'
        )
        main.add_widget(self.status_label)

        # 启动时输出初始信息
        self.log('=' * 40)
        self.log('APP STARTED')
        self.log(f'Config file: {CONFIG_FILE}')
        self.log(f'Config exists: {os.path.exists(CONFIG_FILE)}')
        self.log(f'Note dir: {NOTE_DIR}')
        self.log(f'Note dir exists: {os.path.exists(NOTE_DIR)}')
        if self.config:
            if '_error' in self.config:
                self.log(f'Config ERROR: {self.config["_error"]}')
            else:
                self.log(f'Config loaded: host={self.config.get("host")}, port={self.config.get("port")}')
                self.log(f'User={self.config.get("user")}, file={self.config.get("file")}')
        else:
            self.log('Config not found!')
        self.log('=' * 40)

        return main

    def update_status(self, msg):
        self.status_label.text = msg
        self.log(f'STATUS: {msg}')

    def show_log(self, instance):
        """显示调试日志"""
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))

        scroll = ScrollView()
        log_text = '\n'.join(self.debug_log)
        log_label = Label(
            text=log_text,
            font_size=dp(11),
            color=(0.9, 0.9, 0.9, 1),
            halign='left',
            valign='top',
            size_hint_y=None,
            text_size=(Window.width - dp(60), None)
        )
        log_label.bind(texture_size=log_label.setter('size'))
        scroll.add_widget(log_label)
        content.add_widget(scroll)

        close_btn = Button(
            text='CLOSE',
            size_hint_y=None,
            height=dp(45),
            background_color=(0.3, 0.3, 0.4, 1)
        )
        content.add_widget(close_btn)

        popup = Popup(
            title='Debug Log',
            content=content,
            size_hint=(0.95, 0.85)
        )
        close_btn.bind(on_press=popup.dismiss)
        popup.open()

    def connect_ftp(self):
        """连接 FTP"""
        if not self.config or '_error' in self.config:
            raise Exception('No valid config')
        self.log(f'Connecting to {self.config["host"]}:{self.config["port"]}...')
        ftp = FTP()
        ftp.connect(self.config['host'], self.config['port'], timeout=15)
        self.log('Connected')
        ftp.login(self.config['user'], self.config['pass'])
        self.log('Logged in')
        ftp.cwd('/')
        self.log(f'CWD to /, now at {ftp.pwd()}')
        return ftp

    def on_download(self, instance):
        self.debug_log = []  # 清空日志
        if not self.config:
            self.update_status('Config missing')
            return
        if '_error' in self.config:
            self.update_status(f'Config error: {self.config["_error"]}')
            return
        self.download_btn.disabled = True
        self.update_status('Connecting...')
        Clock.schedule_once(lambda dt: self._do_download(), 0.05)

    def _do_download(self):
        ftp = None
        try:
            remote_file = self.config.get('file', 'zhw63.note')
            self.log(f'Remote file: {remote_file}')
            self.log(f'Local dir: {NOTE_DIR}')

            ftp = self.connect_ftp()

            self.log('Checking remote file...')
            try:
                size = ftp.size(remote_file)
                self.log(f'Remote size: {size} bytes')
            except Exception as e:
                self.log(f'Size check failed: {e}')
                self.update_status('File not found')
                return

            self.log('Listing directory:')
            try:
                ftp.retrlines('LIST', lambda x: self.log(f'  {x}'))
            except Exception as e:
                self.log(f'LIST failed: {e}')

            os.makedirs(NOTE_DIR, exist_ok=True)
            note_path = os.path.join(NOTE_DIR, remote_file)
            self.log(f'Local path: {note_path}')

            self.update_status('Downloading...')
            with open(note_path, 'wb') as f:
                ftp.retrbinary(f'RETR {remote_file}', f.write)
            self.log(f'Downloaded: {os.path.getsize(note_path)} bytes')

            self.update_status('Exporting txt...')
            with open(note_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            count = 0
            for tab in data.get('tabs', []):
                if tab.get('type') == 'text':
                    title = tab.get('title', 'untitled')
                    content = tab.get('content', '')
                    safe = title.replace('/', '_').replace('\\', '_').replace(':', '_')
                    txt_path = os.path.join(NOTE_DIR, f'{safe}.txt')
                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    self.log(f'Exported: {safe}.txt ({len(content)} chars)')
                    count += 1

            self.update_status(f'Done: {count} files')

        except Exception as e:
            self.log(f'ERROR: {e}')
            import traceback
            self.log(traceback.format_exc())
            self.update_status(f'Error: {str(e)[:40]}')
        finally:
            if ftp:
                try:
                    ftp.quit()
                except:
                    pass
            self.download_btn.disabled = False

    def on_upload(self, instance):
        self.debug_log = []  # 清空日志
        if not self.config:
            self.update_status('Config missing')
            return
        if '_error' in self.config:
            self.update_status(f'Config error: {self.config["_error"]}')
            return
        self.upload_btn.disabled = True
        self.update_status('Connecting...')
        Clock.schedule_once(lambda dt: self._do_upload(), 0.05)

    def _do_upload(self):
        ftp = None
        try:
            remote_file = self.config.get('file', 'zhw63.note')
            self.log(f'Remote file: {remote_file}')
            self.log(f'Local dir: {NOTE_DIR}')

            note_path = os.path.join(NOTE_DIR, remote_file)
            self.log(f'Local path: {note_path}')
            self.log(f'Local exists: {os.path.exists(note_path)}')

            if not os.path.exists(note_path):
                self.update_status('Download first')
                return

            self.log(f'Local size: {os.path.getsize(note_path)} bytes')

            self.update_status('Reading .note...')
            with open(note_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.log('Importing txt files...')
            count = 0
            for tab in data.get('tabs', []):
                if tab.get('type') == 'text':
                    title = tab.get('title', 'untitled')
                    txt_path = os.path.join(NOTE_DIR, f'{title}.txt')
                    self.log(f'Checking: {title}.txt')
                    if os.path.exists(txt_path):
                        with open(txt_path, 'r', encoding='utf-8') as f:
                            new_content = f.read()
                        old_len = len(tab.get('content', ''))
                        new_len = len(new_content)
                        if tab.get('content') != new_content:
                            tab['content'] = new_content
                            count += 1
                            self.log(f'  Updated: {old_len} -> {new_len} chars')
                        else:
                            self.log(f'  No change ({new_len} chars)')
                    else:
                        self.log(f'  Not found: {title}.txt')

            self.log(f'Total updated: {count} tabs')

            if count == 0:
                self.update_status('Nothing to update')
                return

            with open(note_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log(f'Saved .note: {os.path.getsize(note_path)} bytes')

            self.update_status('Uploading...')

            ftp = self.connect_ftp()
            with open(note_path, 'rb') as f:
                ftp.storbinary(f'STOR {remote_file}', f)
            self.log(f'Uploaded: {os.path.getsize(note_path)} bytes')

            self.update_status(f'Done: {count} files')

        except Exception as e:
            self.log(f'ERROR: {e}')
            import traceback
            self.log(traceback.format_exc())
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