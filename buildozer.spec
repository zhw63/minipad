[app]
title = FTP Tool
package.name = ftptool
package.domain = com.zhw63.ftptool

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 1.0.0

requirements = python3,kivy

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,ACCESS_NETWORK_STATE

android.api = 33
android.minapi = 21
android.archs = arm64-v8a,armeabi-v7a
android.allow_backup = False
android.accept_sdk_license = True

p4a.branch = v2024.01.21
requirements = python3,kivy,webdavclient3,requests,urllib3,certifi,chardet,idna
[buildozer]
log_level = 2
warn_on_root = 1
