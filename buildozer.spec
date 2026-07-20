[app]

# 应用基本信息
title = KU9 Player
package.name = ku9player
package.domain = org.ku9

# 源码包含的扩展名
source.include_exts = py,png,jpg,kv,atlas,json

# 版本号
version = 2.0.0

# 依赖（建议固定版本，避免不兼容）
requirements = python3,kivy==2.2.1,ffpyplayer,requests,plyer

# Android 权限
android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE

# API 级别（建议使用广泛支持的版本）
android.api = 31
android.minapi = 21
android.target_api = 31

# 自动接受 SDK 许可
android.accept_sdk_license = True

# 架构（减少打包时间，可只保留 arm64-v8a）
android.arch = arm64-v8a, armeabi-v7a

# 全屏与横屏
fullscreen = 1
orientation = landscape

# 允许使用 gradle 依赖（如果有）
android.gradle_dependencies =

# 图标（请确认存在 icon.png）
icon.filename = icon.png

# 调试模式（发布时改为 0）
android.debug = 1

[buildozer]
log_level = 2
warn_on_root = 1
