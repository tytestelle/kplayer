[app]

# 应用基本信息
title = KU9 Player
package.name = ku9player
package.domain = org.ku9

# 源码
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 1.0.0

# 要求
requirements = python3,kivy,ffpyplayer,requests

# Android相关
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE
android.api = 31
android.minapi = 21
android.gradle_dependencies =

# 图标
icon.filename = icon.png

# 全屏
fullscreen = 1

# 支持的架构
android.arch = arm64-v8a, armeabi-v7a

# 签名（发布时需要）
# android.keystore = ku9.keystore
# android.keystore_alias = ku9
# android.keystore_password = your_password

[buildozer]
log_level = 2
warn_on_root = 1
