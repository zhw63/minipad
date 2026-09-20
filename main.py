#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FTP Tool - Download / Upload zhw63.note
"""

import os
import json
import io
from datetime import datetime
from ftplib import FTP, error_perm

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
FTP_HOST = '014.3vftp.cn'
FTP_PORT = 3535
FTP_USER = 'zhw63'
REMOTE_FILE = 'zhw63.note'
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
PASSWORD_FILE = os.path.join(TXT_DIR, 'ftp-password.txt')


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
    """Write debug log to FTP server"""
    password = load_password()
    if not password:
        print(f'LOG (no password): {msg}')
        return

    ftp = None
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f'[{timestamp}] {msg}\n'

        ftp = FTP()
        ftp.connect(FTP_HOST, FTP_PORT, timeout=15)
        ftp.login(FTP_USER, password)
        ftp.cwd('/')

        existing = ''
        try:
            bio = io.BytesIO()
            ftp.retrbinary(f'RETR {DEBUG_LOG}', bio.write)
            existing = bio.getvalue().decode('utf-8')
        except:
            pass

        new_log = existing + log_entry
        bio = io.BytesIO(new_log.encode('utf-8'))
        ftp.storbinary(f'STOR {DEBUG_LOG}', bio)

        ftp.quit()
        print(f'LOG: {msg}')

    except Exception as e:
        print(f'LOG ERROR: {e}')


def connect_ftp():
    """Connect to FTP server, stay in root directory"""
    password = load_password()
    if not password:
        raise Exception('Password not set')

    ftp = FTP()
    ftp.connect(FTP_HOST, FTP_PORT, timeout=15)
    ftp.login(FTP_USER, password)
    ftp.cwd('/')
    return ftp


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
            text='FTP Tool',
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
            text='First run: please enter FTP password',
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
            title='FTP Password',
            content=content,
            size_hint=(0.9, 0.45),
            auto_dismiss=False
        )

        def on_save(instance):
            pwd = pwd_input.text.strip()
            if not pwd:
                tip.text = 'Password cannot be empty'
                return
            if save_password(pwd):
                self.update_status('Password saved')
                popup.dismiss()
                log_to_server('Password saved to local file')
            else:
                tip.text = 'Save failed'

        save_btn.bind(on_press=on_save)
        popup.open()

    def update_status(self, msg):
        self.status_text = msg
        self.status_label.text = msg
        log_to_server(f'STATUS: {msg}')

    def on_download(self, instance):
        log_to_server('on_download() called')
        self.download_btn.disabled = True
        self.update_status('Downloading...')
        Clock.schedule_once(lambda dt: self._do_download(), 0.1)

    def _do_download(self):
        log_to_server('_do_download() started')
        ftp = None
        try:
            log_to_server('Connecting to FTP...')
            ftp = connect_ftp()
            log_to_server('FTP connected')

            log_to_server('Checking server file...')
            try:
                server_size = ftp.size(REMOTE_FILE)
                log_to_server(f'Server file size: {server_size} bytes')
                self.update_status(f'Server: {server_size/1024:.2f} KB')
            except Exception as e:
                log_to_server(f'File not found on server: {e}')
                self.update_status('File not found on server')
                self.download_btn.disabled = False
                return

            log_to_server(f'Creating directory: {TXT_DIR}')
            os.makedirs(TXT_DIR, exist_ok=True)
            log_to_server('Directory ready')

            note_path = os.path.join(TXT_DIR, REMOTE_FILE)
            log_to_server(f'note_path = {note_path}')

            log_to_server('Downloading...')
            self.update_status('Downloading...')
            with open(note_path, 'wb') as f:
                ftp.retrbinary(f'RETR {REMOTE_FILE}', f.write)
            log_to_server('Download complete')

            log_to_server('Exporting txt...')
            self.update_status('Exporting txt...')
            with open(note_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            count = 0
            for tab in data.get('tabs', []):
                if tab.get('type') == 'text':
                    title = tab.get('title', 'untitled')
                    content = tab.get('content', '')
                    safe_title = title.replace('/', '_').replace('\\', '_').replace(':', '_')
                    txt_path = os.path.join(TXT_DIR, f'{safe_title}.txt')
                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    count += 1

            log_to_server(f'Exported {count} txt files')
            self.update_status(f'Done: {count} txt files exported')

        except Exception as e:
            log_to_server(f'ERROR: {e}')
            import traceback
            log_to_server(traceback.format_exc())
            self.update_status(f'Error: {str(e)[:50]}')
        finally:
            if ftp:
                try:
                    ftp.quit()
                except:
                    pass
            self.download_btn.disabled = False

    def on_upload(self, instance):
        log_to_server('on_upload() called')
        self.upload_btn.disabled = True
        self.update_status('Uploading...')
        Clock.schedule_once(lambda dt: self._do_upload(), 0.1)

    def _do_upload(self):
        log_to_server('_do_upload() started')
        ftp = None
        try:
            note_path = os.path.join(TXT_DIR, REMOTE_FILE)
            log_to_server(f'note_path = {note_path}')

            if not os.path.exists(note_path):
                log_to_server('Local .note not found')
                self.update_status('Please download first')
                self.upload_btn.disabled = False
                return

            log_to_server('Reading .note...')
            with open(note_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            log_to_server('Importing txt...')
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
                log_to_server('Nothing to update')
                self.update_status('Nothing to update')
                self.upload_btn.disabled = False
                return

            log_to_server(f'Updated {count} txt files')
            with open(note_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            log_to_server('Connecting to FTP for upload...')
            ftp = connect_ftp()
            log_to_server('FTP connected')

            log_to_server('Uploading...')
            self.update_status('Uploading...')
            with open(note_path, 'rb') as f:
                ftp.storbinary(f'STOR {REMOTE_FILE}', f)

            log_to_server('Upload complete')
            self.update_status('Upload complete')

        except Exception as e:
            log_to_server(f'ERROR: {e}')
            import traceback
            log_to_server(traceback.format_exc())
            self.update_status(f'Error: {str(e)[:50]}')
        finally:
            if ftp:
                try:
                    ftp.quit()
                except:
                    pass
            self.upload_btn.disabled = False


if __name__ == '__main__':
    FTPApp().run()
