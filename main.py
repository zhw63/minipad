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
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.utils import platform


def get_txt_dir():
    """获取可写的本地目录"""
    if platform == 'android':
        from android import mActivity
        base = mActivity.getExternalFilesDir(None).getAbsolutePath()
        path = os.path.join(base, 'note')
    else:
        path = os.path.join(os.path.expanduser('~'), 'Download', 'fileshare', 'note')
    os.makedirs(path, exist_ok=True)
    return path


TXT_DIR = get_txt_dir()
CONFIG_FILE = os.path.join(TXT_DIR, 'ftp_config.json')


def load_config():
    """读取本地配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return None


def save_config(config):
    """保存配置到本地"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


class FTPApp(App):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.status_text = 'Ready'
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

        # 配置按钮
        config_btn = Button(
            text='⚙ CONFIG',
            font_size=dp(16),
            background_color=(0.3, 0.3, 0.35, 1),
            color=(0.8, 0.8, 0.8, 1),
            size_hint_y=None,
            height=dp(40)
        )
        config_btn.bind(on_press=self.show_config)
        main.add_widget(config_btn)

        # 按钮区
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

        # 首次启动，如果没配置，弹出配置界面
        if not self.config:
            Clock.schedule_once(lambda dt: self.show_config(None), 0.5)

        return main

    def update_status(self, msg):
        self.status_label.text = msg
        print(f'STATUS: {msg}')

    def show_config(self, instance):
        """配置界面"""
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(15))

        cfg = self.config or {}

        # Host
        content.add_widget(Label(text='Host:', size_hint_y=None, height=dp(25), halign='left'))
        host_input = TextInput(text=cfg.get('host', ''), multiline=False, size_hint_y=None, height=dp(40))
        content.add_widget(host_input)

        # Port
        content.add_widget(Label(text='Port:', size_hint_y=None, height=dp(25), halign='left'))
        port_input = TextInput(text=str(cfg.get('port', 21)), multiline=False, size_hint_y=None, height=dp(40), input_filter='int')
        content.add_widget(port_input)

        # User
        content.add_widget(Label(text='User:', size_hint_y=None, height=dp(25), halign='left'))
        user_input = TextInput(text=cfg.get('user', ''), multiline=False, size_hint_y=None, height=dp(40))
        content.add_widget(user_input)

        # Password
        content.add_widget(Label(text='Password:', size_hint_y=None, height=dp(25), halign='left'))
        pass_input = TextInput(text=cfg.get('pass', ''), multiline=False, password=True, size_hint_y=None, height=dp(40))
        content.add_widget(pass_input)

        # File
        content.add_widget(Label(text='Remote File:', size_hint_y=None, height=dp(25), halign='left'))
        file_input = TextInput(text=cfg.get('file', 'myfile.note'), multiline=False, size_hint_y=None, height=dp(40))
        content.add_widget(file_input)

        # 按钮
        btn_row = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(10))
        cancel_btn = Button(text='Cancel', background_color=(0.4, 0.4, 0.4, 1))
        save_btn = Button(text='Save', background_color=(0.2, 0.6, 0.3, 1))
        btn_row.add_widget(cancel_btn)
        btn_row.add_widget(save_btn)
        content.add_widget(btn_row)

        popup = Popup(
            title='FTP Configuration',
            content=content,
            size_hint=(0.9, 0.85),
            auto_dismiss=False
        )

        def on_save(*a):
            self.config = {
                'host': host_input.text.strip(),
                'port': int(port_input.text.strip() or 21),
                'user': user_input.text.strip(),
                'pass': pass_input.text,
                'file': file_input.text.strip() or 'myfile.note'
            }
            save_config(self.config)
            popup.dismiss()
            self.update_status('Config saved')

        cancel_btn.bind(on_press=popup.dismiss)
        save_btn.bind(on_press=on_save)

        popup.open()

    def connect_ftp(self):
        """使用配置连接 FTP"""
        if not self.config:
            raise Exception('No config')
        ftp = FTP()
        ftp.connect(self.config['host'], self.config['port'], timeout=15)
        ftp.login(self.config['user'], self.config['pass'])
        ftp.cwd('/')
        return ftp

    def on_download(self, instance):
        if not self.config:
            self.update_status('Please configure first')
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
                size = ftp.size(remote_file)
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
            self.update_status('Please configure first')
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