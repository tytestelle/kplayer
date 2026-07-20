[app]

title = KU9 Player
package.name = ku9player
package.domain = org.ku9

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 2.0.0

requirements = python3,kivy==2.2.1,ffpyplayer,requests,plyer

android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

android.api = 31
android.minapi = 21
android.target_api = 31

android.accept_sdk_license = True

# 可选择只打64位以加快速度
android.arch = arm64-v8a

fullscreen = 1
orientation = landscape

icon.filename = icon.png

[buildozer]
log_level = 2
warn_on_root = 1
