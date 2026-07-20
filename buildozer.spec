[app]
title = KU9 Player
package.name = ku9player
package.domain = org.ku9
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 2.0.0

requirements = python3,kivy==2.3.0,ffpyplayer,requests,pyjnius,android,plyer

android.permissions = INTERNET,ACCESS_NETWORK_STATE,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 31
android.minapi = 21
android.gradle_dependencies =

android.add_src = 
android.add_activity = 
android.add_service = 

fullscreen = 1
orientation = landscape

# 支持多架构
android.arch = arm64-v8a, armeabi-v7a
