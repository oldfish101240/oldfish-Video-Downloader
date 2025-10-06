#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
常數定義模組
"""

# 應用程式資訊
APP_NAME = "oldfish影片下載器"
APP_VERSION = "2.0.0-beta2"

# 音訊品質選項
AUDIO_QUALITIES = [
    {"label": "320kbps", "value": "320"},
    {"label": "256kbps", "value": "256"},
    {"label": "192kbps", "value": "192"},
    {"label": "128kbps", "value": "128"},
    {"label": "96kbps", "value": "96"},
]

# 預設設定
DEFAULT_SETTINGS = {
    'enableNotifications': True,
    # 下載目錄，預設為應用根目錄下的 downloads
    'downloadDir': 'downloads'
}

# 視窗設定
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 640
SETTINGS_WINDOW_WIDTH = 500
SETTINGS_WINDOW_HEIGHT = 350
