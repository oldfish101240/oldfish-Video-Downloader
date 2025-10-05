from PySide6.QtCore import QObject, Slot, QUrl, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
import os
import sys
import time
import yt_dlp # 導入 yt-dlp 庫
import math # 導入 math 模組用於計算 GCD
import threading # 導入 threading 模組用於非同步下載
import subprocess # 導入 subprocess 模組用於開啟檔案位置
import hashlib
import urllib.request
import json
import re

class AnsiCodes:
    OKBLUE = '\033[94m'
    FAIL = '\033[91m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'
    DEBUG = '\033[36m'

def info_console(message):
    print(f"{AnsiCodes.OKBLUE}[INFO]{AnsiCodes.ENDC} {message}")

def error_console(message):
    print(f"{AnsiCodes.FAIL}{AnsiCodes.BOLD}[ERROR]{AnsiCodes.ENDC} {message}")

def debug_console(message):
    print(f"{AnsiCodes.DEBUG}[DEBUG]{AnsiCodes.ENDC} {message}")

def progress_console(message):
    try:
        sys.stdout.write('\r' + message)
        sys.stdout.flush()
    except Exception:
        # 後備：若 stdout 不可寫，使用一般列印
        print(message)

def end_progress_line():
    try:
        sys.stdout.write('\n')
        sys.stdout.flush()
    except Exception:
        pass

def compare_versions(version1, version2):
    """比較兩個版本號，返回 -1, 0, 1 分別表示 version1 <, =, > version2"""
    def version_tuple(v):
        # 將版本號轉換為元組，例如 "1.2.3" -> (1, 2, 3)
        parts = []
        for part in v.split('.'):
            # 移除非數字字符，只保留數字部分
            numeric_part = re.sub(r'[^\d]', '', part)
            if numeric_part:
                parts.append(int(numeric_part))
            else:
                parts.append(0)
        return tuple(parts)
    
    v1_tuple = version_tuple(version1)
    v2_tuple = version_tuple(version2)
    
    if v1_tuple < v2_tuple:
        return -1
    elif v1_tuple > v2_tuple:
        return 1
    else:
        return 0

debug_console("啟動 oldfish影片下載器...")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
info_console(f"根目錄: {ROOT_DIR}")

ICON_TEXT = "assets/icon_text.png"
MENU_ICON = "assets/menu.png"
HOME_ICON = "assets/home.png"
QUEUE_ICON = "assets/quene.png"
SETTINGS_ICON = "assets/settings.png"
ICON = "assets/icon.png"
FOLDER_ICON = "assets/folder.png" # 新增資料夾圖示路徑
FFMPEG = os.path.join(ROOT_DIR, "ffmpeg-7.1.1-essentials_build", "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")

assets_path = os.path.join(ROOT_DIR, "assets")

HTML = fr"""
<!DOCTYPE html>
<html lang="zh-tw">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>oldfish影片下載器</title>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <script>
        // 初始化 Qt WebChannel 並建立與後端的橋接，提供 window.pywebview.api 相容層
        (function(){{
            function initChannel(){{
                if (typeof QWebChannel === 'undefined' || !window.qt || !qt.webChannelTransport){{
                    // 若尚未就緒，稍後重試
                    return setTimeout(initChannel, 50);
                }}
                new QWebChannel(qt.webChannelTransport, function(channel){{
                    window.api = channel.objects.api;
                    window.pywebview = {{ api: window.api }};
                }});
            }}
            initChannel();
        }})();
    </script>
    <style>
        :root {{
            --ease-default: cubic-bezier(0.4, 0, 0.2, 1);
            transition: all 0.25s var(--ease-default);
        }}
        body {{
            margin: 0;
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #181a20;
            color: #e5e7eb;
            transition: background 0.3s ease, color 0.3s ease;
        }}
        /* 全域卷軸樣式（Chromium/QtWebEngine） */
        html, body, .main, .queue-list {{
            scrollbar-width: thin; /* Firefox 後備 */
            scrollbar-color: #4a4f59 #121418; /* 拇指/軌道：現代灰 */
        }}
        ::-webkit-scrollbar {{
            width: 8px;  /* 更纖細 */
            height: 8px;
        }}
        ::-webkit-scrollbar-track {{
            background: #121418; /* 深色軌道 */
        }}
        ::-webkit-scrollbar-thumb {{
            background: #3a3f4a; /* 中性深灰 */
            border-radius: 6px;
            border: 2px solid #121418; /* 與軌道留縫，視覺更輕 */
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: #4a4f59; /* 略亮的灰色，避免過亮 */
            border-color: #121418;
        }}
        ::-webkit-scrollbar-corner {{
            background: #121418;
        }}
        .container {{
            display: flex;
            height: 100vh;
        }}
        .sidebar {{
            width: 160px;
            background: #23262f;
            box-shadow: 2px 0 8px #111;
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            padding-top: 20px;
            transition: width 0.2s ease-in-out;
            overflow: hidden;
        }}
        .sidebar.collapsed {{
            width: 60px;
        }}
        .sidebar .menu-btn {{
            margin-bottom: 30px;
            cursor: pointer;
            width: 48px;
            height: 48px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-left: 6px;
            transition: transform 0.3s ease;
        }}
        .sidebar.collapsed .menu-btn img {{
            transform: rotate(180deg);
        }}
        .sidebar .nav-item {{
            width: 100%;
            height: 48px;
            margin-bottom: 6px; /* 標籤間距縮短 */
            display: flex;
            align-items: center;
            border-radius: 12px;
            cursor: pointer;
            transition: background 0.2s;
            padding-left: 12px;
        }}
        .sidebar .nav-item.selected {{
            background: #2ecc71;
            box-shadow: 0 0 6px #27ae60;
        }}
        .sidebar .nav-item img {{
            width: 28px;
            height: 28px;
            filter: brightness(0.85);
        }}
        .sidebar .nav-text {{
            margin-left: 16px;
            font-size: 17px;
            font-weight: 500;
            transition: opacity 0.2s ease-in-out 0.05s;
            opacity: 1;
            color: #e5e7eb;
            white-space: nowrap;
        }}
        .sidebar.collapsed .nav-text {{
            opacity: 0;
            transition: opacity 0.1s ease-in-out
        }}
        .main {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-start;
            position: relative;
            overflow-y: auto; /* 讓主內容可滾動，配合 sticky 底部區 */
        }}
        .title-img {{
            margin-top: 60px;
            margin-bottom: 30px;
            display: block;
            margin-left: auto;
            margin-right: auto;
            width: 540px;
            filter: drop-shadow(0 0 8px #222);
        }}
        .search-row {{
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 40px;
        }}
        .search-input {{
            width: 340px;
            height: 38px;
            border-radius: 8px;
            border: 1px solid #444;
            background: #23262f;
            color: #e5e7eb;
            padding: 0 14px;
            font-size: 16px;
            outline: none;
        }}
        .search-input:focus {{
            border-color: #2ecc71;
            box-shadow: 0 0 0 3px rgba(39, 174, 96, 0.3);
            transition: box-shadow 0.2s ease, border-color 0.2s ease;
        }}
        .download-btn {{
            margin-left: 12px;
            background: #27ae60;
            color: #fff;
            border: none;
            border-radius: 8px;
            padding: 0 24px;
            height: 38px;
            font-size: 16px;
            cursor: pointer;
            font-weight: bold;
            transition: transform 0.15s ease-in-out, background 0.2s, box-shadow 0.2s;
            box-shadow: 0 2px 8px #111;
        }}
        .download-btn:hover {{
            background: #219150;
            transform: scale(1.03);
            box-shadow: 0 4px 12px #111;
        }}
        
        .settings-btn {{
            position: fixed;
            right: 24px;
            bottom: 24px;
            width: 56px;
            height: 56px;
            background: #2ecc71;
            border: none;
            border-radius: 50%;
            cursor: pointer;
            box-shadow: 0 4px 16px rgba(46, 204, 113, 0.3);
            transition: all 0.3s ease;
            z-index: 1000;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .settings-btn:hover {{
            background: #27ae60;
            transform: scale(1.1);
            box-shadow: 0 6px 20px rgba(46, 204, 113, 0.4);
        }}
        .settings-btn img {{
            width: 28px;
            height: 28px;
            filter: brightness(0) invert(1);
        }}

        .hidden {{
            display: none;
        }}
        .queue-page {{
            /* margin-top: 100px; */ /* 移除此行，由 queue-list 內部控制間距 */
            text-align: center;
            font-size: 22px;
            color: #888;
            flex: 1; /* 讓佇列頁面佔據剩餘空間 */
            width: 100%; /* 讓佇列頁面寬度為100% */
            display: flex; /* 讓其內容可以居中 */
            flex-direction: column;
            align-items: center;
            justify-content: space-between; /* 上下分佈，讓底部輸入區靠底 */
        }}
        .modal-bg {{
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.35);
            z-index: 9999;
            display: none;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transform: scale(0.95);
            transition: opacity 0.2s ease, transform 0.2s ease;
        }}
        .modal-bg.show {{
            display: flex;
            opacity: 1;
            transform: scale(1);
        }}
        .modal {{
            background: #23262f;
            border-radius: 16px;
            box-shadow: 0 4px 24px #000a;
            padding: 28px 32px 24px 32px;
            min-width: 320px;
            max-width: 90vw;
            display: flex;
            flex-direction: column;
            align-items: center;
            position: relative;
        }}
        
        .modal-icon {{
            position: absolute;
            left: 24px;
            top: 24px;
            width: 32px;
            height: 32px;
        }}
        .modal-title {{
            font-size: 18px;
            font-weight: bold;
            color: #2ecc71;
            margin-bottom: 18px;
            margin-top: 0;
            width: 100%;
            text-align: center;
        }}
        .modal-msg {{
            font-size: 16px;
            color: #e5e7eb;
            margin-bottom: 18px;
            text-align: center;
            width: 100%;
            white-space: pre-line;
        }}
        .modal-btn {{
            background: #27ae60;
            color: #fff;
            border: none;
            border-radius: 8px;
            padding: 0 24px;
            height: 38px;
            font-size: 16px;
            cursor: pointer;
            font-weight: bold;
            margin-top: 8px;
            align-self: center;
        }}
        .modal-btn:hover {{
            background: #219150;
        }}
        .video-modal-bg {{
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.35);
            z-index: 10000;
            display: none;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transform: scale(0.95);
            transition: opacity 0.2s ease, transform 0.2s ease;
        }}
        .video-modal-bg.show {{
            display: flex;
            opacity: 1;
            transform: scale(1);
        }}
        .video-modal {{
            background: #23262f;
            border-radius: 16px;
            box-shadow: 0 4px 24px #000a;
            padding: 0;
            min-width: 420px;
            max-width: 96vw;
            display: flex;
            flex-direction: column;
            align-items: stretch;
            position: relative;
        }}
        .video-modal-loading {{
            padding: 48px 48px 32px 48px;
            font-size: 20px;
            color: #aaa;
            text-align: center;
        }}
        .video-modal-header {{
            display: flex;
            align-items: flex-start;
            padding: 32px 32px 0 32px;
        }}
        .video-modal-thumb {{
            max-height: 70px; /* Adjust thumbnail height to match text content */
            width: auto; /* Maintain aspect ratio */
            border-radius: 8px;
            object-fit: cover; /* Ensure the whole image is visible without cropping */
            margin-right: 18px;
            background: #181a20;
            align-self: flex-start; /* Align to the top within the flex container */
        }}
        .video-modal-titlebox {{
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }}
        .video-modal-title {{
            font-size: 20px;
            font-weight: bold;
            color: #e5e7eb;
            margin-bottom: 6px;
            margin-top: 0;
            word-break: break-all;
        }}
        .video-modal-meta {{
            font-size: 15px;
            color: #aaa;
            margin-bottom: 2px;
        }}
        .video-modal-uploader {{
            font-size: 15px;
            color: #aaa;
            margin-bottom: 2px;
        }}
        .video-modal-options {{
            padding: 24px 32px 0 32px;
            display: flex;
            flex-direction: column;
            gap: 18px;
        }}
        .video-modal-label {{
            font-size: 16px;
            color: #e5e7eb;
            margin-bottom: 6px;
        }}
        .custom-select {{
            position: relative;
            width: 100%;
            max-width: 300px;
            user-select: none;
        }}
        .custom-select-header {{
            width: 100%;
            padding: 8px 12px;
            border-radius: 8px;
            border: 1px solid #444;
            background: #23262f;
            color: #e5e7eb;
            font-size: 15px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: border-color 0.2s ease, background-color 0.2s ease;
        }}
        .custom-select-header:hover {{
            border-color: #2ecc71;
            background: #2b2e37;
        }}
        .custom-select-header.active {{
            border-color: #2ecc71;
            background: #2b2e37;
            box-shadow: 0 0 0 2px rgba(46, 204, 113, 0.2);
        }}
        .custom-select-arrow {{
            width: 0;
            height: 0;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid #e5e7eb;
            transition: transform 0.2s ease;
        }}
        .custom-select-header.active .custom-select-arrow {{
            transform: rotate(180deg);
        }}
        .custom-select-options {{
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: #23262f;
            border: 1px solid #444;
            border-top: none;
            border-radius: 0 0 8px 8px;
            max-height: 200px;
            overflow-y: auto;
            z-index: 1000;
            display: none;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}
        .custom-select-options.show {{
            display: block;
        }}
        .custom-select-option {{
            padding: 8px 12px;
            cursor: pointer;
            transition: background-color 0.2s ease;
            border-bottom: 1px solid #333;
        }}
        .custom-select-option:last-child {{
            border-bottom: none;
        }}
        .custom-select-option:hover {{
            background: #2ecc71;
            color: #fff;
        }}
        .custom-select-option.selected {{
            background: #2ecc71;
            color: #fff;
        }}



        /* 淺色主題樣式 */
        body.light-theme {{
            background: #f5f5f5;
            color: #333;
        }}
        /* 淺色主題的卷軸顏色 */
        body.light-theme, body.light-theme .main, body.light-theme .queue-list {{
            scrollbar-color: #b5b8bd #ededed; /* 淺色主題灰 */
        }}
        body.light-theme ::-webkit-scrollbar-track {{
            background: #ededed;
        }}
        body.light-theme ::-webkit-scrollbar-thumb {{
            background: #c7cad0; /* 中灰 */
            border-color: #ededed;
            border-radius: 6px;
        }}
        body.light-theme ::-webkit-scrollbar-thumb:hover {{
            background: #b5b8bd; /* 稍深灰 */
        }}
        body.light-theme .container {{
            background: #f5f5f5;
        }}
        body.light-theme .sidebar {{
            background: #ffffff;
            box-shadow: 2px 0 8px rgba(0,0,0,0.1);
        }}
        body.light-theme .nav-item {{
            color: #333;
        }}
        body.light-theme .nav-item.selected {{
            background: #2ecc71;
            color: #fff;
        }}
        body.light-theme .nav-text {{
            color: #333;
        }}
        body.light-theme .nav-item.selected .nav-text {{
            color: #fff;
        }}
        body.light-theme .main {{
            background: #f5f5f5;
        }}

        body.light-theme .search-input {{
            background: #ffffff;
            border-color: #ddd;
            color: #333;
        }}
        body.light-theme .search-input:focus {{
            border-color: #2ecc71;
        }}
        body.light-theme .queue-item {{
            background: #ffffff;
            color: #333;
        }}
        body.light-theme .custom-select-header {{
            background: #ffffff;
            border-color: #ddd;
            color: #333;
        }}
        body.light-theme .custom-select-options {{
            background: #ffffff;
            border-color: #ddd;
        }}
        body.light-theme .custom-select-option {{
            color: #333;
            border-bottom-color: #eee;
        }}
        body.light-theme .modal {{
            background: #ffffff;
            color: #333;
        }}
        body.light-theme .video-modal {{
            background: #ffffff;
            color: #333;
        }}
        body.light-theme .video-modal-title {{
            color: #333;
        }}
        body.light-theme .video-modal-label {{
            color: #333;
        }}
        .video-modal-actions {{
            display: flex;
            justify-content: flex-end;
            align-items: center;
            gap: 16px;
            padding: 24px 32px 32px 32px;
        }}
        .video-modal-btn {{
            background: #27ae60;
            color: #fff;
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            height: 40px;
            font-size: 16px;
            cursor: pointer;
            font-weight: bold;
            transition: background 0.2s;
            white-space: nowrap;
            min-width: 100px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }}
        .video-modal-btn.cancel {{
            background: #444;
            color: #eee;
        }}
        .video-modal-btn:hover {{
            background: #219150;
        }}
        .video-modal-btn.cancel:hover {{
            background: #666;
        }}

        /* 新增佇列頁面樣式 */
        .queue-search-row {{
            width: 90%;
            max-width: 600px;
            margin-top: 8px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }}
        
        .queue-list {{
            width: 90%; /* 調整列表寬度 */
            max-width: 800px; /* 最大寬度限制 */
            display: flex;
            flex-direction: column;
            align-items: center; /* 讓列表項居中 */
            padding-bottom: 110px; /* 下修預留高度，讓列表可視範圍更大 */
        }}

        .queue-bottom {{
            position: sticky; /* 置於主內容底部，不覆蓋左側標籤列 */
            bottom: 0;
            width: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 8px 0 12px; /* 縮小上下高度 */
            background: #181a20; /* 與頁面一致，避免透出 */
            z-index: 1200; /* 高於一般內容，低於模態視窗(>10000) */
            box-shadow: 0 -6px 24px rgba(0,0,0,0.35);
        }}

        .queue-item {{
            background: #2b2e37; /* 項目背景色 */
            border-radius: 12px;
            padding: 15px 20px;
            /* margin-bottom: 20px; */ /* 項目間距由分隔線控制 */
            width: 100%;
            display: flex;
            align-items: flex-start; /* 縮圖和文字頂部對齊 */
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            position: relative;
            overflow: hidden; /* 防止內容溢出 */
        }}

        .queue-item-thumbnail {{
            width: 120px; /* 縮圖寬度 */
            height: 90px; /* 縮圖高度 */
            object-fit: cover; /* 裁剪圖片以填充 */
            border-radius: 8px;
            margin-right: 15px;
            flex-shrink: 0; /* 防止縮圖被壓縮 */
            background-color: #181a20; /* 縮圖載入前的背景 */
            display: flex; /* 讓內容居中 */
            align-items: center;
            justify-content: center;
            color: #b0b0b0; /* 文字顏色 */
            font-size: 12px; /* 文字大小 */
            text-align: center;
            line-height: 1.2;
            padding: 5px; /* 內邊距 */
        }}

        .queue-item-thumbnail img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            border-radius: 8px;
        }}

        .queue-item-info {{
            flex-grow: 1; /* 資訊部分佔據剩餘空間 */
            display: flex;
            flex-direction: column;
            justify-content: flex-start; /* 頂部對齊 */
        }}

        .queue-item-title {{
            font-size: 18px;
            font-weight: bold;
            color: #e5e7eb;
            margin-bottom: 5px;
            word-break: break-all; /* 長標題自動換行 */
            text-align: left;
        }}

        .queue-item-meta,
        .queue-item-url {{
            font-size: 14px;
            color: #b0b0b0;
            margin-bottom: 3px;
            word-break: break-all;
            text-align: left;
        }}

        .queue-item-url a {{
            color: #2ecc71;
            text-decoration: none;
        }}
        .queue-item-url a:hover {{
            text-decoration: underline;
        }}

        .progress-bar-container {{
            width: 100%;
            background-color: #444;
            border-radius: 5px;
            height: 8px;
            margin-top: 10px;
            overflow: hidden;
        }}

        .progress-bar {{
            height: 100%;
            width: 0%; /* 初始為0 */
            background-color: #2ecc71;
            border-radius: 5px;
            transition: width 0.3s ease; /* 平滑過渡 */
        }}

        .progress-text {{
            font-size: 13px;
            color: #888;
            margin-top: 5px;
            text-align: right;
        }}

        .queue-separator {{
            width: 90%;
            max-width: 780px; /* 比項目略窄 */
            height: 1px;
            background-color: #3a3f4a;
            margin: 0 auto 8px; /* 縮小與輸入區距離 */
        }}
        .queue-item-actions {{
            display: flex;
            align-items: center;
            margin-left: auto; /* 將按鈕推到最右邊 */
        }}
        .queue-item-action-btn {{
            background: none;
            border: none;
            cursor: pointer;
            padding: 5px;
            border-radius: 8px;
            transition: background 0.2s ease;
        }}
        .queue-item-action-btn:hover {{
            background: rgba(255,255,255,0.1);
        }}
        .queue-item-action-btn img {{
            width: 24px;
            height: 24px;
            filter: brightness(0.85);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar" id="sidebar">
            <div class="menu-btn" onclick="toggleSidebar()">
                <img src="{MENU_ICON}" alt="menu" style="width:32px;height:32px;">
            </div>
            <div class="nav-item selected" id="nav-home" onclick="showPage('home')">
                <img src="{HOME_ICON}" alt="主頁">
                <span class="nav-text">主頁</span>
            </div>
            <div class="nav-item" id="nav-queue" onclick="showPage('queue')">
                <img src="{QUEUE_ICON}" alt="佇列">
                <span class="nav-text">佇列</span>
            </div>

        </div>
        <div class="main">
            <img class="title-img" id="title-img" src="{ICON_TEXT}" alt="">
            <div class="search-row" id="search-row">
                <input class="search-input" id="video-url" type="text" placeholder="請輸入影片網址...">
                <button class="download-btn" onclick="downloadVideo()">下載</button>
            </div>
            
            <!-- 設定按鈕 - 右下角 -->
            <button class="settings-btn" id="settings-btn" onclick="openSettings()">
                <img src="{SETTINGS_ICON}" alt="設定">
            </button>

            <!-- 佇列頁面改造 -->
            <div class="queue-page" id="queue-page"> <!-- 移除 hidden class，改由 JS 完全控制 -->
                <div class="queue-list" id="queue-list">
                    <!-- 影片任務將會動態新增到這裡 -->
                </div>
                <div class="queue-bottom">
                    <div class="queue-separator"></div>
                    <!-- 佇列頁面的輸入框（置底置中） -->
                    <div class="queue-search-row" id="queue-search-row">
                        <input class="search-input" id="queue-video-url" type="text" placeholder="請輸入影片網址...">
                        <button class="download-btn" onclick="downloadVideoFromQueue()">下載</button>
                    </div>
                </div>
            </div>

        </div>
    </div>
    <!-- 全局載入中遮罩 -->
    <div class="loading-bg" id="loading-bg" style="position: fixed; top:0; left:0; right:0; bottom:0; background: rgba(0,0,0,0.45); z-index: 15000; display: none;">
        <div style="position:absolute; top:50%; left:50%; transform: translate(-50%,-50%); background:#23262f; color:#e5e7eb; padding:16px 22px; border-radius:12px; box-shadow:0 4px 24px #000a; font-size:16px;">
            載入中...
        </div>
    </div>
    <div class="modal-bg" id="modal-bg">
        <div class="modal">
            <img class="modal-icon" src="{ICON}" alt="icon">
            <div class="modal-title" id="modal-title"></div>
            <div class="modal-msg" id="modal-msg"></div>
            <button class="modal-btn" onclick="closeModal()">確定</button>
        </div>
    </div>
    <div class="video-modal-bg" id="video-modal-bg">
        <div class="video-modal" id="video-modal">
            <div class="video-modal-loading" id="video-modal-loading">載入中...</div>
            <div id="video-modal-content" style="display:none;">
                <div class="video-modal-header">
                    <img class="video-modal-thumb" id="video-modal-thumb" src="{ICON}" alt="thumb">
                    <div class="video-modal-titlebox">
                        <div class="video-modal-title" id="video-modal-title"></div>
                        <div class="video-modal-meta" id="video-modal-duration"></div>
                        <div class="video-modal-uploader" id="video-modal-uploader"></div>
                    </div>
                </div>
                <div class="video-modal-options">
                    <div class="video-modal-label" id="video-modal-quality-label">影片畫質</div>
                    <div class="custom-select" id="quality-select">
                        <div class="custom-select-header" onclick="toggleSelect('quality-select')">
                            <span class="custom-select-text">請選擇畫質</span>
                            <div class="custom-select-arrow"></div>
                        </div>
                        <div class="custom-select-options" id="quality-options"></div>
                    </div>
                    <div class="video-modal-label" style="margin-top:18px;">影片格式</div>
                    <div class="custom-select" id="format-select">
                        <div class="custom-select-header" onclick="toggleSelect('format-select')">
                            <span class="custom-select-text">請選擇格式</span>
                            <div class="custom-select-arrow"></div>
                        </div>
                        <div class="custom-select-options" id="format-options"></div>
                    </div>
                </div>
                <div class="video-modal-actions">
                    <button class="video-modal-btn cancel" onclick="closeVideoModal()">取消</button>
                    <button class="video-modal-btn" onclick="confirmDownload()">下載</button>
                </div>
            </div>
        </div>
    </div>
    <script>
        // 儲存上次獲取的影片資訊以還原畫質選項
        let lastVideoInfo = null;
        // 儲存目前正在處理的影片網址（從主頁或佇列進入）
        let currentUrl = '';

        // MP3, AAC, FLAC, WAV 的音訊品質選項
        const AUDIO_QUALITIES = [
            {{label: "320kbps", value: "320"}},
            {{label: "256kbps", value: "256"}},
            {{label: "192kbps", value: "192"}},
            {{label: "128kbps", value: "128"}}
        ];

        // 儲存所有下載任務的陣列
        let downloadQueue = [];
        let nextTaskId = 0; // 用於給每個任務一個獨特的ID

        /**
         * 將影片畫質從高到低排序。
         * 處理 "4K", "1080p", "720p", "360p", "2K", "4K" 等格式。
         * @param {{Array<Object>}} qualities - 畫質物件陣列 {{label: string, ratio: string}}。
         * @returns {{Array<Object>}} 已排序的畫質。
         */
        function sortQualities(qualities) {{
            return (qualities || []).slice().sort(function(a, b) {{
                function getNum(s) {{
                    if (typeof s.label === "string") {{
                        if (s.label.endsWith("K")) {{
                            let num = parseInt(s.label);
                            return !isNaN(num) ? num * 1000 : 0;
                        }}
                        if (s.label.endsWith("p")) {{
                            let num = parseInt(s.label);
                            return !isNaN(num) ? num : 0;
                        }}
                    }}
                    let num = parseInt(s.label); // 用於 "320kbps" 等情況
                    return !isNaN(num) ? num : 0;
                }}
                return getNum(b) - getNum(a); // 降序排序
            }});
        }}

        /**
         * 排序格式，優先考慮 "mp4" 和 "mp3"。
         * @param {{Array<Object>}} formats - 格式物件陣列 {{value: string, label: string, desc: string}}。
         * @returns {{Array<Object>}} 已排序的格式。
         */
        function sortFormats(formats) {{
            const priority = {{"影片+音訊": 3, "影片": 2, "音訊": 1}}; // 優先級定義
            return (formats || []).slice().sort(function(a, b) {{
                let pa = priority[a.desc] || 0;
                let pb = priority[b.desc] || 0;
                if (pa !== pb) return pb - pa; // 按描述優先級降序
                return a.value.localeCompare(b.value); // 描述相同時按值字母順序
            }});
        }}

        /**
         * 確認網址是否為有效的 YouTube 網址。
         * @param {{string}} url - 要檢查的網址。
         * @returns {{boolean}} 是否為有效的 YouTube 網址。
         */
        function isYoutubeUrl(url) {{
            return /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\//.test(url.trim());
        }}

        /**
         * 切換側邊欄的折疊狀態。
         */
        function toggleSidebar() {{
            var sidebar = document.getElementById('sidebar');
            sidebar.classList.toggle('collapsed');
        }}

        /**
         * 顯示指定頁面並更新導航項目選擇。
         * @param {{string}} pageName - 要顯示的頁面名稱 ('home' 或 'queue')。
         */
        function showPage(pageName) {{
            document.getElementById('nav-home').classList.remove('selected');
            document.getElementById('nav-queue').classList.remove('selected');

            // Get all main content elements
            const titleImg = document.getElementById('title-img');
            const searchRow = document.getElementById('search-row');
            const queuePage = document.getElementById('queue-page');
            const queueSearchRow = document.getElementById('queue-search-row');
            const queueList = document.getElementById('queue-list'); // Get reference to queue list
            const settingsBtn = document.getElementById('settings-btn'); // 獲取設定按鈕

            if (pageName === 'home') {{
                document.getElementById('nav-home').classList.add('selected');
                
                if (titleImg) titleImg.style.display = 'block'; // 顯示主頁元素
                if (searchRow) searchRow.style.display = 'flex';
                if (settingsBtn) settingsBtn.style.display = 'block'; // 顯示設定按鈕
                
                if (queuePage) queuePage.style.display = 'none'; // 隱藏其他頁面
                if (queueSearchRow) queueSearchRow.style.display = 'none'; // 隱藏佇列輸入框
                if (queueList) queueList.innerHTML = ''; // 清空佇列列表內容

            }} else if (pageName === 'queue') {{
                document.getElementById('nav-queue').classList.add('selected');
                
                if (titleImg) titleImg.style.display = 'none'; // 隱藏主頁元素
                if (searchRow) searchRow.style.display = 'none';
                if (settingsBtn) settingsBtn.style.display = 'none'; // 隱藏設定按鈕
                
                if (queuePage) queuePage.style.display = 'flex'; // 顯示佇列頁面
                if (queueSearchRow) queueSearchRow.style.display = 'flex'; // 顯示佇列輸入框
                renderQueue(); // 渲染佇列內容
            }}
        }}

        /**
         * 顯示一般訊息模態視窗。
         * @param {{string}} title - 訊息標題。
         * @param {{string}} message - 訊息內容。
         */
        function showModal(title, msg) {{
            const modal = document.getElementById('modal-bg');
            document.getElementById('modal-title').innerText = title;
            document.getElementById('modal-msg').innerHTML = msg;
            modal.style.display = 'flex';
            setTimeout(() => modal.classList.add('show'), 10); // 觸發動畫
        }}

        /**
         * 隱藏一般訊息模態視窗。
         */
        function closeModal() {{
            const modal = document.getElementById('modal-bg');
            modal.classList.remove('show');
            setTimeout(() => {{
                modal.style.display = 'none';
            }}, 200); // 等待動畫結束
        }}

        /**
         * 隱藏影片詳細資訊模態視窗。
         */
        function closeVideoModal() {{
            const videoModalBg = document.getElementById('video-modal-bg');
            videoModalBg.classList.remove('show');
            setTimeout(() => {{
                videoModalBg.style.display = 'none';
                hideLoading();
            }}, 200);
        }}

        /**
         * 處理佇列輸入框的Enter鍵按下。
         */
        function handleQueueInputKeyPress(event) {{
            if (event.key === 'Enter') {{
                downloadVideoFromQueue();
            }}
        }}
        
        /**
         * 從佇列頁面下載影片。
         */
        function downloadVideoFromQueue() {{
            const urlInput = document.getElementById('queue-video-url');
            const url = urlInput.value.trim();
            
            if (!url) {{
                showModal('錯誤', '請輸入影片網址');
                return;
            }}
            
            // 與主頁一致：開啟影片資訊模態，讓使用者選擇格式再下載
            try {{ currentUrl = (url || '').trim(); }} catch(e) {{ currentUrl = ''; }}
            showVideoModal(url);
            
            // 清空輸入框
            urlInput.value = '';
        }}

        /**
         * 處理主頁面上的下載按鈕點擊。
         * 獲取影片資訊並顯示影片詳細資訊模態視窗。
         */
        async function downloadVideo() {{
            var url = document.getElementById('video-url').value;
            if (!url.trim()) {{
                showModal("提醒", "請輸入影片網址！");
                return;
            }}
            if (!isYoutubeUrl(url)) {{
                showModal("網址格式錯誤", "</div><div style='text-align:left;'><br>正確格式範例：<br>https://www.youtube.com/watch?v=xxxx<br>https://youtu.be/xxxx</div>");
                return;
            }}
            // 立即顯示載入中，避免前一層阻塞繪製
            requestAnimationFrame(() => showLoading());
            // 設置 currentUrl，避免之後確認下載時讀到空字串
            try {{ currentUrl = (url || '').trim(); }} catch(e) {{ currentUrl = ''; }}
            showVideoModal(url);
        }}

        /**
         * 開啟設定視窗
         */
        function openSettings() {{
            window.pywebview.api.open_settings()
                .then(result => {{
                    console.log('設定視窗已開啟:', result);
                }})
                .catch(error => {{
                    console.error('開啟設定視窗失敗:', error);
                    showModal('錯誤', '無法開啟設定視窗');
                }});
        }}

        function showLoading() {{
            var lb = document.getElementById('loading-bg');
            if (lb){{ lb.style.display = 'flex'; }}
        }}
        function hideLoading() {{
            var lb = document.getElementById('loading-bg');
            if (lb){{ lb.style.display = 'none'; }}
        }}

        /**
         * 顯示影片詳細資訊模態視窗。
         * @param {{string}} url - 影片網址。
         */
        function showVideoModal(url) {{
            // 記錄目前處理的網址供確認下載使用
            try {{ currentUrl = (url || '').trim(); }} catch(e) {{ currentUrl = ''; }}
            const videoModalBg = document.getElementById('video-modal-bg');
            videoModalBg.style.display = 'flex';
            setTimeout(() => videoModalBg.classList.add('show'), 10);
            document.getElementById('video-modal-loading').style.display = '';
            document.getElementById('video-modal-content').style.display = 'none';
            // 使用 requestAnimationFrame 確保樣式更新後再顯示，避免同步阻塞不重繪
            requestAnimationFrame(() => showLoading());
            // 背景取得影片資訊，前端以回呼接收，避免阻塞
            setTimeout(function(){{
                window.__onVideoInfo = function(info) {{
                    try {{ lastVideoInfo = info; }} catch(e) {{}}

                    // 畫質選項（由高到低排序）
                    var qualityOptions = document.getElementById('quality-options');
                    qualityOptions.innerHTML = '';
                    var qualities = (info.qualities || []).slice();
                    qualities.sort(function(a, b) {{
                        // 解析 label 內的數字（如 4K, 1080p, 720p, 480p, 360p）
                        function getValue(q) {{
                            if (q.label.endsWith('K')) return parseInt(q.label) * 1000;
                            var m = q.label.match(/(\d+)p/);
                            return m ? parseInt(m[1]) : 0;
                        }}
                        return getValue(b) - getValue(a);
                    }});
                    qualities.forEach(function(q) {{
                        var optionDiv = document.createElement('div');
                        optionDiv.className = 'custom-select-option';
                        optionDiv.textContent = q.label + (q.ratio ? ' ' + q.ratio : ''); // 顯示畫面比例
                        optionDiv.onclick = () => selectOption('quality-select', q.label, q.label + (q.ratio ? ' ' + q.ratio : ''));
                        if (q.label === '1080p') {{
                            optionDiv.classList.add('selected');
                            const qualitySelectText = document.querySelector('#quality-select .custom-select-text');
                            if (qualitySelectText) {{
                                qualitySelectText.textContent = q.label + (q.ratio ? ' ' + q.ratio : '');
                            }}
                            currentQuality = q.label;
                        }}
                        qualityOptions.appendChild(optionDiv);
                    }});

                    // 格式選項（mp4和mp3優先）
                    var formatOptions = document.getElementById('format-options');
                    formatOptions.innerHTML = '';
                    var formats = (info.formats || []).slice();
                    formats.sort(function(a, b) {{
                        var priority = {{"影片+音訊": 3, "影片": 2, "音訊": 1}};
                        var pa = priority[a.desc] || 0;
                        var pb = priority[b.desc] || 0;
                        if (pa !== pb) return pb - pa;
                        return a.value.localeCompare(b.value);
                    }});
                    formats.forEach(function(f) {{
                        var optionDiv = document.createElement('div');
                        optionDiv.className = 'custom-select-option';
                        optionDiv.textContent = f.label + (f.desc ? ' (' + f.desc + ')' : '');
                        optionDiv.onclick = () => selectOption('format-select', f.value, f.label + (f.desc ? ' (' + f.desc + ')' : ''));
                        if (f.value === 'mp4') {{
                            optionDiv.classList.add('selected');
                            const formatSelectText = document.querySelector('#format-select .custom-select-text');
                            if (formatSelectText) {{
                                formatSelectText.textContent = f.label + (f.desc ? ' (' + f.desc + ')' : '');
                            }}
                            currentFormat = f.value;
                        }}
                        formatOptions.appendChild(optionDiv);
                    }});

                    // 設定預設值
                    if (!currentQuality && qualities.length > 0) {{
                        currentQuality = qualities[0].label;
                        const qualitySelectText = document.querySelector('#quality-select .custom-select-text');
                        if (qualitySelectText) {{
                            qualitySelectText.textContent = qualities[0].label + (qualities[0].ratio ? ' ' + qualities[0].ratio : '');
                        }}
                    }}
                    if (!currentFormat && formats.length > 0) {{
                        currentFormat = formats[0].value;
                        const formatSelectText = document.querySelector('#format-select .custom-select-text');
                        if (formatSelectText) {{
                            formatSelectText.textContent = formats[0].label + (formats[0].desc ? ' (' + formats[0].desc + ')' : '');
                        }}
                    }}

                    // 縮圖處理：如果 info.thumb 不存在或載入失敗，顯示文字
                    const thumbElement = document.getElementById('video-modal-thumb');
                    if (info.thumb) {{
                        thumbElement.src = info.thumb;
                        thumbElement.style.display = '';
                        thumbElement.alt = "影片縮圖";
                        const existingNoThumbText = thumbElement.parentNode.querySelector('.video-modal-thumb-text');
                        if (existingNoThumbText) {{ existingNoThumbText.remove(); }}
                    }} else {{
                        thumbElement.src = '';
                        thumbElement.style.display = 'none';
                        let noThumbText = thumbElement.parentNode.querySelector('.video-modal-thumb-text');
                        if (!noThumbText) {{
                            noThumbText = document.createElement('div');
                            noThumbText.classList.add('video-modal-thumb-text');
                            noThumbText.innerText = "找不到縮圖";
                            noThumbText.style.width = '100%';
                            noThumbText.style.height = '100%';
                            noThumbText.style.display = 'flex';
                            noThumbText.style.alignItems = 'center';
                            noThumbText.style.justifyContent = 'center';
                            noThumbText.style.backgroundColor = '#181a20';
                            noThumbText.style.borderRadius = '8px';
                            noThumbText.style.color = '#b0b0b0';
                            noThumbText.style.fontSize = '12px';
                            noThumbText.style.textAlign = 'center';
                            noThumbText.style.lineHeight = '1.2';
                            noThumbText.style.padding = '5px';
                            thumbElement.parentNode.insertBefore(noThumbText, thumbElement.nextSibling);
                        }}
                    }}

                    document.getElementById('video-modal-title').innerText = info.title || '';
                    document.getElementById('video-modal-duration').innerText = info.duration || '';
                    document.getElementById('video-modal-uploader').innerText = info.uploader ? info.uploader : '';
                    document.getElementById('video-modal-uploader').style.display = info.uploader ? '' : 'none';
                    document.getElementById('video-modal-loading').style.display = 'none';
                    document.getElementById('video-modal-content').style.display = '';
                    hideLoading();
                }};
                window.__onVideoInfoError = function(error) {{
                    console.error('獲取影片資訊時出錯:', error);
                    showModal('錯誤', '找不到影片，請確認網址是否輸入正確');
                    closeVideoModal();
                    hideLoading();
                }};
                window.pywebview.api.start_get_video_info(url);
            }} , 0);
        }}

        // 自定義下拉選單相關變數
        let currentQuality = '';
        let currentFormat = '';
        let isQualitySelectOpen = false;
        let isFormatSelectOpen = false;

        /**
         * 切換下拉選單的開關狀態
         */
        function toggleSelect(selectId) {{
            const select = document.getElementById(selectId);
            if (!select) return;
            
            const options = select.querySelector('.custom-select-options');
            const header = select.querySelector('.custom-select-header');
            
            if (!options || !header) return;
            
            // 關閉其他下拉選單
            if (selectId === 'quality-select') {{
                closeSelect('format-select');
                closeSelect('theme-select');
                isQualitySelectOpen = !isQualitySelectOpen;
                if (isQualitySelectOpen) {{
                    options.classList.add('show');
                    header.classList.add('active');
                }} else {{
                    options.classList.remove('show');
                    header.classList.remove('active');
                }}
            }} else if (selectId === 'format-select') {{
                closeSelect('quality-select');
                closeSelect('theme-select');
                isFormatSelectOpen = !isFormatSelectOpen;
                if (isFormatSelectOpen) {{
                    options.classList.add('show');
                    header.classList.add('active');
                }} else {{
                    options.classList.remove('show');
                    header.classList.remove('active');
                }}
            }} else if (selectId === 'theme-select') {{
                closeSelect('quality-select');
                closeSelect('format-select');
                const isThemeSelectOpen = header.classList.contains('active');
                if (!isThemeSelectOpen) {{
                    options.classList.add('show');
                    header.classList.add('active');
                }} else {{
                    options.classList.remove('show');
                    header.classList.remove('active');
                }}
            }}
        }}

        /**
         * 關閉指定的下拉選單
         */
        function closeSelect(selectId) {{
            const select = document.getElementById(selectId);
            if (!select) return;
            
            const options = select.querySelector('.custom-select-options');
            const header = select.querySelector('.custom-select-header');
            
            if (!options || !header) return;
            
            options.classList.remove('show');
            header.classList.remove('active');
            
            if (selectId === 'quality-select') {{
                isQualitySelectOpen = false;
            }} else if (selectId === 'format-select') {{
                isFormatSelectOpen = false;
            }}
        }}

        /**
         * 選擇下拉選單選項
         */
        function selectOption(selectId, value, text) {{
            const select = document.getElementById(selectId);
            const headerText = select.querySelector('.custom-select-text');
            const options = select.querySelectorAll('.custom-select-option');
            
            // 移除所有選項的選中狀態
            options.forEach(option => option.classList.remove('selected'));
            
            // 為當前選擇的選項添加選中狀態
            const selectedOption = Array.from(options).find(option => 
                option.textContent === text
            );
            if (selectedOption) {{
                selectedOption.classList.add('selected');
            }}
            
            headerText.textContent = text;
            
            if (selectId === 'quality-select') {{
                currentQuality = value;
                closeSelect('quality-select');
            }} else if (selectId === 'format-select') {{
                currentFormat = value;
                closeSelect('format-select');
                onFormatChange();
            }}
        }}

        /**
         * 處理影片格式選擇的變更。
         * 根據選擇的影片或音訊格式調整畫質選項。
         */
        function onFormatChange() {{
            const qualityOptions = document.getElementById('quality-options');
            const qualityLabel = document.getElementById('video-modal-quality-label');
            const audioTypes = ["mp3", "aac", "flac", "wav"];

            if (audioTypes.includes(currentFormat)) {{
                // 如果是音訊格式，顯示音訊品質
                qualityOptions.innerHTML = '';
                AUDIO_QUALITIES.forEach(q => {{
                    const optionDiv = document.createElement('div');
                    optionDiv.className = 'custom-select-option';
                    optionDiv.textContent = q.label;
                    optionDiv.onclick = () => selectOption('quality-select', q.value, q.label);
                    // 設定預設選中320kbps
                    if (q.value === "320") {{
                        optionDiv.classList.add('selected');
                    }}
                    qualityOptions.appendChild(optionDiv);
                }});
                currentQuality = "320"; // 預設音訊品質
                const qualitySelectText = document.querySelector('#quality-select .custom-select-text');
                if (qualitySelectText) {{
                    qualitySelectText.textContent = "320kbps";
                }}
                qualityLabel.innerText = "音質";
            }} else {{
                // 如果是影片格式，從 lastVideoInfo 還原影片畫質
                if (lastVideoInfo && lastVideoInfo.qualities) {{
                    qualityOptions.innerHTML = '';
                    let sortedQualities = sortQualities(lastVideoInfo.qualities);
                    let defaultSet = false;
                    sortedQualities.forEach(q => {{
                        const optionDiv = document.createElement('div');
                        optionDiv.className = 'custom-select-option';
                        optionDiv.textContent = q.label + (q.ratio ? ' ' + q.ratio : '');
                        optionDiv.onclick = () => selectOption('quality-select', q.label, q.label + (q.ratio ? ' ' + q.ratio : ''));
                        // 設定預設選中1080p，如果沒有1080p則選第一個
                        if (q.label === "1080p" || (!defaultSet && sortedQualities.indexOf(q) === 0)) {{
                            optionDiv.classList.add('selected');
                            currentQuality = q.label;
                            const qualitySelectText = document.querySelector('#quality-select .custom-select-text');
                            if (qualitySelectText) {{
                                qualitySelectText.textContent = q.label + (q.ratio ? ' ' + q.ratio : '');
                            }}
                            defaultSet = true;
                        }}
                        qualityOptions.appendChild(optionDiv);
                    }});
                }}
                qualityLabel.innerText = "影片畫質";
            }}
        }}

        /**
         * 確認並開始影片下載。
         * 使用選定的選項呼叫 Python API。
         */
        async function confirmDownload() {{
            // 優先使用 showVideoModal 記錄的 currentUrl；若空才讀主頁輸入框
            let url = (currentUrl || '').trim();
            if (!url) {{
            const urlInput = document.getElementById('video-url');
                url = (urlInput && urlInput.value ? urlInput.value.trim() : '');
            }}
            const quality = currentQuality;
            const format = currentFormat;

            closeVideoModal(); // 關閉影片選擇模態視窗

            // 將任務加入佇列並渲染
            addDownloadTask({{
                id: nextTaskId++, // 給予唯一ID
                url: url,
                title: lastVideoInfo.title || '未知影片',
                thumbnail: lastVideoInfo.thumb || '', // 縮圖找不到時傳空字串
                uploader: lastVideoInfo.uploader || '未知作者',
                duration: lastVideoInfo.duration || '00:00',
                quality: quality,
                format: format,
                progress: 0, // 初始進度
                status: '等待中', // 初始狀態
                filePath: '' // 新增檔案路徑，下載完成後會更新
            }});

            // 清理輸入狀態
            try {{ const urlInput = document.getElementById('video-url'); if (urlInput) urlInput.value = ''; }} catch(e) {{}}
            currentUrl = '';

            // 呼叫 Python API 開始下載 (排到下一個事件迴圈，讓 UI 先切頁)
            setTimeout(() => {{
                try {{
                    const task = downloadQueue[downloadQueue.length - 1];
                    window.pywebview.api.start_download(task.id, url, quality, format)
                        .then(result => {{ console.log("下載任務啟動結果:", result); }})
                        .catch(error => {{ console.error("啟動下載任務時出錯:", error); }});
                }} catch (e) {{
                    console.error("排程下載任務時出錯:", e);
                }}
            }}, 0);
        }}

        /**
         * 將一個下載任務添加到佇列並更新顯示。
         * @param {{Object}} task - 下載任務物件。
         */
        function addDownloadTask(task) {{
            downloadQueue.push(task);
            renderQueue(); // 重新渲染整個佇列
            // 如果在主頁添加任務，切換到佇列頁面
            showPage('queue');
        }}

        /**
         * 渲染或更新下載佇列的顯示。
         */
        function renderQueue() {{
            const queueList = document.getElementById('queue-list');
            queueList.innerHTML = ''; // 清空現有內容以重新渲染

            if (downloadQueue.length === 0) {{
                queueList.innerHTML = `<p style="text-align: center; color: #888; font-size: 18px; margin-top: 50px;">目前沒有下載任務。</p>`;
                return;
            }}

            downloadQueue.forEach((task, index) => {{
                // 創建任務項目
                const itemDiv = document.createElement('div');
                itemDiv.classList.add('queue-item');
                itemDiv.setAttribute('data-task-id', task.id); // 便於後續更新特定任務

                // 處理長網址顯示
                const displayUrl = task.url.length > 50 ? task.url.substring(0, 47) + '...' : task.url;

                let thumbnailContent;
                if (task.thumbnail) {{
                    thumbnailContent = `<img class="queue-item-thumbnail-image" src="${{task.thumbnail}}" alt="影片縮圖">`;
                }} else {{
                    thumbnailContent = `<div class="queue-item-thumbnail-text">找不到縮圖</div>`;
                }}

                itemDiv.innerHTML = `
                    <div class="queue-item-thumbnail">
                        ${{thumbnailContent}}
                    </div>
                    <div class="queue-item-info">
                        <div class="queue-item-title">${{task.title}}</div>
                        <div class="queue-item-meta">${{task.uploader}} · ${{task.duration}}</div>
                        <div class="queue-item-url">
                            <a href="${{task.url}}" target="_blank" title="${{task.url}}">
                                ${{displayUrl}}
                            </a>
                        </div>
                        <div class="progress-bar-container">
                            <div class="progress-bar" style="width: ${{task.progress}}%;"></div>
                        </div>
                        <div class="progress-text">${{task.status}} (${{task.progress.toFixed(1)}}%)</div>
                    </div>
                    <div class="queue-item-actions">
                        <button class="queue-item-action-btn" onclick="openFileLocation(${{task.id}})" disabled>
                            <img src="{FOLDER_ICON}" alt="開啟檔案位置">
                        </button>
                    </div>
                `;
                queueList.appendChild(itemDiv);

                // 如果不是最後一個項目，添加分隔線
                if (index < downloadQueue.length - 1) {{
                    const separatorDiv = document.createElement('div');
                    separatorDiv.classList.add('queue-separator');
                    queueList.appendChild(separatorDiv);
                }}
            }});
        }}

        // **重要：新增一個函數來更新特定任務的進度**
        // 這個函數將由 Python 後端呼叫（透過 pywebview.api.update_progress）
        window.updateDownloadProgress = function(taskId, progress, status = '下載中', message = '', filePath = '') {{
            const taskIndex = downloadQueue.findIndex(task => task.id === taskId);
            if (taskIndex !== -1) {{
                downloadQueue[taskIndex].progress = progress;
                downloadQueue[taskIndex].status = status;
                if (filePath) {{
                    downloadQueue[taskIndex].filePath = filePath; // 更新檔案路徑
                }}
                // 如果有額外訊息，可以顯示
                if (message) {{
                    console.log(`Task ${{taskId}} update: ${{message}}`);
                }}
                // 找到對應的 DOM 元素並更新
                const itemDiv = document.querySelector(`.queue-item[data-task-id="${{taskId}}"]`);
                if (itemDiv) {{
                    itemDiv.querySelector('.progress-bar').style.width = `${{progress}}%`;
                    itemDiv.querySelector('.progress-text').innerText = `${{status}} (${{progress.toFixed(1)}}%)`;
                    // 只有當狀態為「已完成」且有 filePath 時才啟用按鈕
                    const openFolderBtn = itemDiv.querySelector('.queue-item-action-btn');
                    if (status === '已完成' && downloadQueue[taskIndex].filePath) {{ // 檢查 task.filePath
                        openFolderBtn.disabled = false; // 啟用按鈕
                        openFolderBtn.style.opacity = '1';
                        openFolderBtn.style.cursor = 'pointer';
                    }} else {{
                        openFolderBtn.disabled = true; // 禁用按鈕
                        openFolderBtn.style.opacity = '0.5'; // 變灰
                        openFolderBtn.style.cursor = 'not-allowed';
                    }}
                }}
            }}
        }};

        /**
         * 開啟下載檔案所在位置。
         * @param {{number}} taskId - 任務ID。
         */
        function openFileLocation(taskId) {{
            const task = downloadQueue.find(t => t.id === taskId);
            if (!task) {{
                console.error("找不到任務:", taskId);
                showModal("錯誤", "找不到指定的下載任務。");
                return;
            }}
            
            if (!task.filePath) {{
                console.error("任務沒有檔案路徑:", task);
                showModal("錯誤", "檔案路徑不可用。");
                return;
            }}
            
            // 傳遞實際的檔案路徑給後端
            window.pywebview.api.open_file_location(task.filePath)
                .then(result => {{
                    console.log("開啟檔案位置結果:", result);
                }})
                .catch(error => {{
                    console.error("開啟檔案位置時出錯:", error);
                    showModal("錯誤", "無法開啟檔案位置。");
                }});
        }}





        // 點擊外部關閉下拉選單
        document.addEventListener('click', function(event) {{
            const qualitySelect = document.getElementById('quality-select');
            const formatSelect = document.getElementById('format-select');
            
            // 只有在影片選擇模態視窗才處理畫質和格式選擇的關閉
            const videoModal = document.getElementById('video-modal-bg');
            if (videoModal && videoModal.classList.contains('show')) {{
                if (qualitySelect && !qualitySelect.contains(event.target)) {{
                    closeSelect('quality-select');
                }}
                if (formatSelect && !formatSelect.contains(event.target)) {{
                    closeSelect('format-select');
                }}
            }}
        }});

        // 首次載入時，綁定Enter事件並顯示主頁
        document.addEventListener('DOMContentLoaded', () => {{
            const homeInput = document.getElementById('video-url');
            if (homeInput) {{
                homeInput.addEventListener('keypress', (e) => {{
                    if (e.key === 'Enter') {{
                        downloadVideo();
                    }}
                }});
            }}
            const queueInput = document.getElementById('queue-video-url');
            if (queueInput) {{
                queueInput.addEventListener('keypress', (e) => {{
                    if (e.key === 'Enter') {{
                        downloadVideoFromQueue();
                    }}
                }});
            }}
            showPage('home');
        }});
    </script>
</body>
</html>
"""

# HTML寫入邏輯移到 main 區塊中，避免重複執行

class Api(QObject):
    # 從背景執行緒安全地要求在主執行緒執行 JS
    eval_js_requested = Signal(str)
    infoReady = Signal('QVariant')
    infoError = Signal(str)
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.download_threads = {} # 用於儲存下載執行緒
        self.eval_js_requested.connect(self._on_eval_js_requested)
        self.completed_tasks = set()
        self.settings_process = None  # 追蹤設定視窗進程（單一進程）
        self._lock = threading.Lock() # 添加線程鎖
        self.task_has_postprocessing = {}  # task_id -> bool：是否包含轉檔/後處理
        self.task_in_postprocessing = {}    # task_id -> bool：是否已進入轉檔階段

    # 移除多客戶端探測，回歸 yt-dlp 預設行為以維持穩定性

    def _extract_video_info(self, url):
        # 回到單一 yt-dlp 取得格式，與官方格式清單一致
        ydl_opts = {
            'quiet': True,
            'simulate': True,
            'format': 'bestvideo+bestaudio/best',
            'ffmpeg_location': FFMPEG,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)

        title = info_dict.get('title', '無標題影片')
        duration_seconds = info_dict.get('duration')
        duration = ''
        if duration_seconds:
            minutes, seconds = divmod(duration_seconds, 60)
            hours, minutes = divmod(minutes, 60)
            if hours > 0:
                duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                duration = f"{minutes:02d}:{seconds:02d}"
        uploader = info_dict.get('uploader')
        thumb = info_dict.get('thumbnail')

        qualities = []
        formats = []
        seen_qualities = set()
        def gcd(a, b):
            while b:
                a, b = b, a % b
            return a
        has_mp4_video_audio = False
        has_mp3_audio = False
        has_any_audio = False
        has_any_video = False
        for f in info_dict.get('formats', []):
            if f.get('vcodec') != 'none' and f.get('height'):
                has_any_video = True
                label = f"{f['height']}p"
                ratio_str = ''
                if f.get('width') and f.get('height'):
                    common_divisor = gcd(f['width'], f['height'])
                    calculated_ratio = f"({f['width'] // common_divisor}:{f['height'] // common_divisor})"
                    if calculated_ratio in ["(16:9)", "(4:3)", "(19:6)"]:
                        ratio_str = calculated_ratio
                    else:
                        ratio_str = '(Custom)'
                if label not in seen_qualities:
                    qualities.append({'label': label, 'ratio': ratio_str})
                    seen_qualities.add(label)
            ext = f.get('ext')
            vcodec = f.get('vcodec')
            acodec = f.get('acodec')
            if ext == 'mp4' and vcodec != 'none' and acodec != 'none':
                has_mp4_video_audio = True
            if ext == 'mp3' and acodec != 'none' and vcodec == 'none':
                has_mp3_audio = True
            if acodec != 'none':
                has_any_audio = True
        # 預設提供 mp4（影片）；若偵測到音訊，也提供 mp3（音訊）
        if has_any_video:
            formats.append({'value': 'mp4', 'label': 'mp4', 'desc': '影片'})
        if has_any_audio:
            formats.append({'value': 'mp3', 'label': 'mp3', 'desc': '音訊'})
        def format_sort_key(f):
            desc_priority = {'影片+音訊': 2, '音訊': 1}
            return (desc_priority.get(f['desc'], 0), f['value'])
        formats.sort(key=format_sort_key, reverse=True)

        # 縮圖本地快取
        def cache_thumb(thumb_url):
            try:
                if not thumb_url:
                    return ''
                cache_dir = os.path.join(ROOT_DIR, 'thumb_cache')
                os.makedirs(cache_dir, exist_ok=True)
                ext = os.path.splitext(thumb_url.split('?')[0])[-1]
                if len(ext) > 5 or not ext:
                    ext = '.jpg'
                key = hashlib.md5(thumb_url.encode('utf-8')).hexdigest()
                local_path = os.path.join(cache_dir, key + ext)
                if not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
                    req = urllib.request.Request(thumb_url, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
                    })
                    with urllib.request.urlopen(req, timeout=10) as resp, open(local_path, 'wb') as out:
                        out.write(resp.read())
                return 'file:///' + local_path.replace('\\', '/')
            except Exception as e:
                debug_console(f"縮圖快取失敗: {e}")
                # 如果快取失敗，返回原始URL作為後備方案
                return thumb_url or ''
        thumb_local = cache_thumb(thumb)

        return {
            'title': title,
            'duration': duration,
            'uploader': uploader,
            'thumb': thumb_local or thumb or '',
            'qualities': qualities,
            'formats': formats,
        }

    @Slot(str, result=str)
    def start_get_video_info(self, url):
        # 在背景執行緒取得資訊，完成後以 signal 回傳，避免阻塞 UI/Main Thread
        def task():
            try:
                info = self._extract_video_info(url)
                self.infoReady.emit(info)
            except Exception as e:
                self.infoError.emit(str(e))
        threading.Thread(target=task, daemon=True).start()
        return 'started'

    def _eval_js(self, script):
        # 由於進度回呼在背景執行緒觸發，透過 signal 轉到主執行緒執行
        self.eval_js_requested.emit(script)

    @Slot(str)
    def _on_eval_js_requested(self, script):
        try:
            self.page.runJavaScript(script)
        except Exception as e:
            debug_console(f"JavaScript執行失敗: {e}")
            # 記錄失敗但不中斷程式執行

    def _download_progress_hook(self, d):
        """
        yt-dlp 的進度回調函數。
        將進度更新發送到前端。
        """
        # 安全獲取 task_id，避免 KeyError
        task_id = d.get('task_id')
        if task_id is None:
            debug_console("警告：進度回調中缺少 task_id")
            return
            
        if d['status'] == 'downloading':
            # 計算下載百分比
            if d.get('total_bytes'):
                percent = d['downloaded_bytes'] / d['total_bytes'] * 100
                status = f"下載中"
            elif d.get('total_bytes_estimate'):
                percent = d['downloaded_bytes'] / d['total_bytes_estimate'] * 100
                status = f"下載中 (預估)"
            else:
                percent = 0
                status = f"下載中 (未知進度)"

            # 將進度更新傳遞給前端
            self._eval_js(f"window.updateDownloadProgress({task_id}, {percent}, '{status}');")
            progress_console(f"任務 {task_id}: {status} {percent:.1f}%")

        elif d['status'] == 'finished':
            # 下載完成；若存在後處理（轉檔/合併），延後完成通知到後處理完成
            debug_console(f"【任務{task_id}】檢測到下載完成狀態: {d}")

            try:
                with self._lock:
                    has_post = self.task_has_postprocessing.get(task_id, False)
            except Exception:
                has_post = False

            # 推導檔案路徑
            filepath = d.get('filepath') or d.get('filename') or ''
            if filepath and not os.path.isabs(filepath):
                # 嘗試解析為 downloads 目錄下
                filepath = os.path.join(ROOT_DIR, 'downloads', filepath)
            filepath = filepath or ''
            debug_console(f"【任務{task_id}】最終檔案路徑(可能尚未最終化): {filepath}")

            if has_post:
                # 標記轉檔中，不發送完成通知
                self._eval_js(f"window.updateDownloadProgress({task_id}, 100, '轉檔中', '', '{filepath.replace(os.sep, '/') if filepath else ''}')")
                try:
                    with self._lock:
                        self.task_in_postprocessing[task_id] = True
                except Exception:
                    pass
                debug_console(f"【任務{task_id}】含後處理，等待 postprocessor 完成後再通知")
            else:
                # 無後處理，直接視為完成
                self._eval_js(f"window.updateDownloadProgress({task_id}, 100, '已完成', '', '{filepath.replace(os.sep, '/') if filepath else ''}')")
                end_progress_line()
                info_console(f"任務 {task_id}: 下載完成 - {d.get('filename', '')}")
                self._notify_download_complete_safely(d, task_id)
        elif d['status'] == 'error':
            # 下載錯誤
            self._eval_js(f"window.updateDownloadProgress({task_id}, 0, '錯誤', '{d.get('error', '未知錯誤')}');")
            end_progress_line()
            error_console(f"任務 {task_id}: 下載錯誤 - {d.get('error', '未知錯誤')}")
        else:
            # 其他狀態：嘗試辨識後處理階段
            status_text = d.get('status', '')
            if isinstance(status_text, str) and status_text.lower().startswith('post'):  # e.g. 'postprocessing'
                # 標記已進入轉檔；避免前端再以「下載中」覆蓋
                try:
                    with self._lock:
                        self.task_in_postprocessing[task_id] = True
                except Exception:
                    pass
                self._eval_js(f"window.updateDownloadProgress({task_id}, 100, '轉檔中');")
                debug_console(f"任務 {task_id}: 轉檔中")
            else:
                # 若已進入轉檔階段，保持顯示「轉檔中」
                try:
                    with self._lock:
                        in_post = self.task_in_postprocessing.get(task_id, False)
                except Exception:
                    in_post = False
                if in_post:
                    self._eval_js(f"window.updateDownloadProgress({task_id}, 100, '轉檔中');")
                else:
                    self._eval_js(f"window.updateDownloadProgress({task_id}, 0, '{d['status']}');")
                debug_console(f"任務 {task_id}: 狀態 - {d['status']}")
    def _notify_download_complete_safely(self, d, task_id):
        """統一的完成通知流程，避免重覆與例外中斷。"""
        try:
            settings = self.load_settings()
            if not settings.get('enableNotifications', True):
                return
            filename = d.get('filename') if isinstance(d, dict) else None
            if not filename:
                filename = '已完成的下載'
            if os.path.sep in filename:
                filename = os.path.basename(filename)
            title = "下載完成"
            message = f"影片已成功下載：{filename}"
            self.show_notification(title, message)
            info_console(f"影片下載完成：{filename}")
        except Exception as e:
            debug_console(f"完成通知失敗: {e}")


    @Slot(str, result=str)
    def download(self, url):
        debug_console(f"下載按鈕被點擊，網址: {url}")
        info_console(f"收到下載請求: {url}")
        return "下載功能尚未實作"

    @Slot(result=str)
    def open_settings(self):
        """打開設定視窗"""
        debug_console("設定按鈕被點擊")
        try:
            import subprocess
            import sys
            import os
            
            # 檢查是否已經有設定視窗在運行
            if self.settings_process is not None and self.settings_process.poll() is None:
                debug_console("設定視窗已經開啟，嘗試調到該視窗")
                # 使用進程 ID 查找視窗，避免依賴標題文字
                try:
                    import ctypes
                    from ctypes import wintypes
                    user32 = ctypes.windll.user32
                    kernel32 = ctypes.windll.kernel32

                    target_pid = self.settings_process.pid

                    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

                    hwnd_found = None
                    def enum_proc(hwnd, lParam):
                        nonlocal hwnd_found
                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        if pid.value == target_pid and user32.IsWindowVisible(hwnd):
                            hwnd_found = hwnd
                            return False  # stop enum
                        return True

                    user32.EnumWindows(EnumWindowsProc(enum_proc), 0)

                    if hwnd_found:
                        user32.SetForegroundWindow(hwnd_found)
                        user32.ShowWindow(hwnd_found, 9)  # SW_RESTORE
                        info_console("設定視窗已調到最前面")
                        return "設定視窗已調到最前面"
                except Exception as e:
                    debug_console(f"調到設定視窗失敗: {e}")
                
                info_console("設定視窗已經開啟")
                return "設定視窗已經開啟"
            
            # 獲取設定檔路徑
            settings_path = os.path.join(ROOT_DIR, 'settings.pyw')
            
            if os.path.exists(settings_path):
                # 使用當前Python環境啟動設定視窗
                python_exe = os.path.join(ROOT_DIR, 'python_embed', 'pythonw.exe')
                if not os.path.exists(python_exe):
                    python_exe = sys.executable
                
                # 啟動設定視窗並追蹤進程
                self.settings_process = subprocess.Popen([python_exe, settings_path], cwd=ROOT_DIR)
                info_console("設定視窗已開啟")
                return "設定視窗已開啟"
            else:
                error_console(f"設定檔案不存在: {settings_path}")
                return "設定檔案不存在"
                
        except Exception as e:
            error_console(f"開啟設定視窗失敗: {e}")
            return f"開啟設定視窗失敗: {e}"

    @Slot(result=str)
    def close_settings(self):
        """關閉設定視窗"""
        try:
            debug_console("關閉設定視窗")
            if self.settings_process is not None:
                try:
                    if self.settings_process.poll() is None:  # 檢查進程是否還在運行
                        self.settings_process.terminate()
                        info_console("設定視窗已關閉")
                        self.settings_process = None
                        return "設定視窗已關閉"
                    else:
                        debug_console("設定視窗進程已經結束")
                        self.settings_process = None
                        return "設定視窗已經關閉"
                except Exception as e:
                    debug_console(f"關閉設定視窗進程失敗: {e}")
                    return f"關閉設定視窗失敗: {e}"
            else:
                debug_console("沒有設定視窗需要關閉")
                return "沒有設定視窗需要關閉"
            
        except Exception as e:
            error_console(f"關閉設定視窗失敗: {e}")
            return f"關閉設定視窗失敗: {e}"

    def check_ytdlp_version(self):
        """檢查 yt-dlp 是否為最新版本"""
        try:
            # 取得目前安裝的版本
            current_version = yt_dlp.version.__version__
            debug_console(f"目前 yt-dlp 版本: {current_version}")
            
            # 從 PyPI 取得最新版本資訊
            try:
                import urllib.request
                import json
                
                url = "https://pypi.org/pypi/yt-dlp/json"
                with urllib.request.urlopen(url, timeout=10) as response:
                    data = json.loads(response.read().decode())
                    latest_version = data['info']['version']
                    debug_console(f"最新 yt-dlp 版本: {latest_version}")
                    
                    # 比較版本
                    if compare_versions(current_version, latest_version) < 0:
                        return {
                            'update_available': True,
                            'current_version': current_version,
                            'latest_version': latest_version
                        }
                    else:
                        debug_console("yt-dlp 已是最新版本")
                        return {
                            'update_available': False,
                            'current_version': current_version,
                            'latest_version': latest_version
                        }
            except Exception as e:
                debug_console(f"檢查最新版本失敗: {e}")
                return None
                
        except Exception as e:
            error_console(f"版本檢查失敗: {e}")
            return None

    def update_ytdlp(self):
        """更新 yt-dlp 到最新版本"""
        try:
            debug_console("開始更新 yt-dlp...")
            
            # 使用 pip 更新 yt-dlp
            python_exe = os.path.join(ROOT_DIR, "python_embed", "python.exe")
            if not os.path.exists(python_exe):
                python_exe = sys.executable
            
            result = subprocess.run([
                python_exe, "-m", "pip", "install", "--upgrade", "yt-dlp"
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                info_console("yt-dlp 更新成功")
                return True
            else:
                error_console(f"yt-dlp 更新失敗: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            error_console("yt-dlp 更新超時")
            return False
        except Exception as e:
            error_console(f"更新 yt-dlp 失敗: {e}")
            return False

    @Slot()
    def startYtDlpUpdate(self):
        """由前端呼叫，啟動 yt-dlp 更新（背景執行並回報進度）"""
        def run_update():
            try:
                # 初始化進度 UI（若前端已建立，這裡只做保險）
                self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(0, '開始更新…');")

                # 準備 Python 可執行檔
                python_exe = os.path.join(ROOT_DIR, "python_embed", "python.exe")
                if not os.path.exists(python_exe):
                    python_exe = sys.executable

                # 啟動 pip 更新
                cmd = [
                    python_exe, "-m", "pip", "install", "--upgrade", "yt-dlp",
                    "--disable-pip-version-check"
                ]
                debug_console(f"執行更新命令: {' '.join(cmd)}")

                with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1) as proc:
                    progress = 3
                    last_emit_time = 0
                    for line in proc.stdout:
                        ln = line.strip()
                        if not ln:
                            continue
                        # 粗略偵測階段關鍵詞，更新提示文字
                        lower = ln.lower()
                        if 'collecting' in lower or 'downloading' in lower:
                            self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(undefined, '正在下載套件…');")
                            progress = max(progress, 10)
                        elif 'installing collected packages' in lower:
                            self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(undefined, '正在安裝…');")
                            progress = max(progress, 60)
                        elif 'successfully installed' in lower or 'already satisfied' in lower:
                            progress = max(progress, 95)
                        # 逐步推進條（節流傳送）
                        now = time.time()
                        if now - last_emit_time > 0.2:
                            progress = min(progress + 1, 97)
                            self._eval_js(f"window.__ofUpdateProgress && window.__ofUpdateProgress({progress}, undefined);")
                            last_emit_time = now

                    ret = proc.wait()
                    if ret == 0:
                        self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(100, '更新完成');")
                        # 顯示完成與重啟選項
                        self._eval_js(
                            "window.__ofUpdateDone && window.__ofUpdateDone(true, 'yt-dlp 已成功更新到最新版本！');"
                        )
                    else:
                        self._eval_js(
                            "window.__ofUpdateDone && window.__ofUpdateDone(false, 'yt-dlp 更新失敗，請稍後再試或手動更新。');"
                        )
            except Exception as e:
                error_console(f"更新執行失敗: {e}")
                self._eval_js(
                    f"window.__ofUpdateDone && window.__ofUpdateDone(false, '更新過程發生錯誤：{str(e).replace('\\', '/')}');"
                )

        threading.Thread(target=run_update, daemon=True).start()

    @Slot()
    def restartApp(self):
        """嘗試重新啟動應用程式。若有封裝的 exe 則優先重啟 exe。"""
        try:
            # 可能的 exe 路徑（在 main 目錄上一層）
            exe_path = os.path.normpath(os.path.join(ROOT_DIR, os.pardir, 'oldfish影片下載器.exe'))
            started = False
            if os.path.exists(exe_path):
                debug_console(f"嘗試啟動 exe: {exe_path}")
                subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
                started = True
            else:
                # 退而求其次：重啟目前 Python 腳本
                pyw = os.path.normpath(os.path.join(ROOT_DIR, 'oldfish_downloader.pyw'))
                pythonw = os.path.join(ROOT_DIR, 'python_embed', 'pythonw.exe')
                if os.path.exists(pythonw) and os.path.exists(pyw):
                    subprocess.Popen([pythonw, pyw], cwd=os.path.dirname(pyw))
                    started = True

            # 關閉目前應用
            from PySide6.QtWidgets import QApplication
            if started:
                QApplication.quit()
            else:
                # 若未能啟動新程序，只提示
                self._eval_js(
                    "alert('更新完成，請手動重新啟動應用程式。');"
                )
        except Exception as e:
            error_console(f"重啟應用失敗: {e}")
            self._eval_js(
                f"alert('重啟失敗：{str(e).replace('\\', '/')}');"
            )

    def show_update_dialog(self, version_info):
        """顯示更新對話框"""
        try:
            current_version = version_info['current_version']
            latest_version = version_info['latest_version']
            
            # 創建 HTML 更新對話框
            dialog_html = f"""
            (function() {{
                // 創建覆蓋層
                const overlay = document.createElement('div');
                overlay.id = 'update-dialog-overlay';
                overlay.style.cssText = `
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.7);
                    z-index: 10000;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-family: 'Segoe UI', Arial, sans-serif;
                `;
                
                // 創建對話框
                const dialog = document.createElement('div');
                dialog.id = 'update-dialog';
                dialog.style.cssText = `
                    background: #23262f;
                    border-radius: 16px;
                    padding: 32px;
                    max-width: 420px;
                    width: 90%;
                    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
                    border: 1px solid #444;
                `;
                
                // 創建標題區域
                const titleDiv = document.createElement('div');
                titleDiv.style.cssText = `
                    display: flex;
                    align-items: center;
                    margin-bottom: 16px;
                `;
                
                const iconDiv = document.createElement('div');
                iconDiv.style.cssText = `
                    width: 48px;
                    height: 48px;
                    background: #2ecc71;
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin-right: 16px;
                    box-shadow: 0 0 6px #27ae60;
                `;
                iconDiv.innerHTML = '<img src="assets/update.png" alt="update" style="width:24px;height:24px;object-fit:contain;filter:brightness(1);">';
                
                const title = document.createElement('h3');
                title.style.cssText = `
                    margin: 0;
                    color: #e5e7eb;
                    font-size: 20px;
                    font-weight: bold;
                `;
                title.textContent = 'yt-dlp 更新提醒';
                
                titleDiv.appendChild(iconDiv);
                titleDiv.appendChild(title);
                
                // 創建描述文字
                const desc = document.createElement('p');
                desc.style.cssText = `
                    color: #e5e7eb;
                    margin: 0 0 24px 0;
                    line-height: 1.5;
                    font-size: 16px;
                    font-weight: 600;
                `;
                desc.textContent = '發現 yt-dlp 新版本！';
                
                // 創建版本資訊區域
                const versionDiv = document.createElement('div');
                versionDiv.style.cssText = `
                    background: #181a20;
                    border-radius: 12px;
                    padding: 18px;
                    margin-bottom: 24px;
                    border: 1px solid #444;
                `;
                
                const currentVersionDiv = document.createElement('div');
                currentVersionDiv.style.cssText = 'margin-bottom: 12px;';
                currentVersionDiv.innerHTML = `
                    <span style="color: #aaa; font-size: 15px;">目前版本:</span>
                    <span style="color: #e5e7eb; font-weight: 500; margin-left: 12px;">{current_version}</span>
                `;
                
                const latestVersionDiv = document.createElement('div');
                latestVersionDiv.innerHTML = `
                    <span style="color: #aaa; font-size: 15px;">最新版本:</span>
                    <span style="color: #2ecc71; font-weight: 500; margin-left: 12px;">{latest_version}</span>
                `;
                
                versionDiv.appendChild(currentVersionDiv);
                versionDiv.appendChild(latestVersionDiv);
                
                // 第一行：詢問句
                const question = document.createElement('p');
                question.style.cssText = `
                    color: #e5e7eb;
                    margin: 16px 0 8px 0;
                    font-size: 15px;
                    font-weight: 600;
                `;
                question.textContent = '是否要更新到最新版本？';

                // 第二行：左側提示小字（單獨一行）
                const actionsRow = document.createElement('div');
                actionsRow.style.cssText = `
                    display: flex;
                    align-items: center;
                    justify-content: flex-start;
                    gap: 16px;
                    margin: 0 0 8px 0;
                `;

                const note = document.createElement('p');
                note.style.cssText = `
                    color: #888;
                    margin: 0;
                    font-size: 12px;
                    line-height: 1.4;
                    font-style: italic;
                    flex: 1;
                `;
                note.textContent = '※yt-dlp為下載器的重要核心元件，建議更新以避免錯誤及獲得更好的使用體驗';
                
                // 第三行：按鈕區域（單獨一行，靠右）
                const buttonDiv = document.createElement('div');
                buttonDiv.style.cssText = `
                    display: flex;
                    gap: 16px;
                    justify-content: flex-end;
                    margin: 0 0 24px 0;
                `;
                
                const skipBtn = document.createElement('button');
                skipBtn.id = 'skip-update-btn';
                skipBtn.style.cssText = `
                    background: #23262f;
                    color: #e5e7eb;
                    border: 1px solid #444;
                    padding: 12px 24px;
                    border-radius: 8px;
                    cursor: pointer;
                    font-size: 15px;
                    font-weight: 500;
                    transition: all 0.2s ease;
                `;
                skipBtn.textContent = '稍後提醒';
                skipBtn.onmouseover = function() {{ 
                    this.style.background = '#2b2e37';
                    this.style.borderColor = '#2ecc71';
                }};
                skipBtn.onmouseout = function() {{ 
                    this.style.background = '#23262f';
                    this.style.borderColor = '#444';
                }};
                
                const updateBtn = document.createElement('button');
                updateBtn.id = 'update-now-btn';
                updateBtn.style.cssText = `
                    background: #27ae60;
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 8px;
                    cursor: pointer;
                    font-size: 15px;
                    font-weight: bold;
                    transition: all 0.2s ease;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
                `;
                updateBtn.textContent = '立即更新';
                updateBtn.onmouseover = function() {{ 
                    this.style.background = '#219150';
                    this.style.transform = 'scale(1.03)';
                    this.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.3)';
                }};
                updateBtn.onmouseout = function() {{ 
                    this.style.background = '#27ae60';
                    this.style.transform = 'scale(1)';
                    this.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.2)';
                }};
                
                buttonDiv.appendChild(skipBtn);
                buttonDiv.appendChild(updateBtn);

                // 第二行組裝：只放提示小字
                actionsRow.appendChild(note);

                // 組裝對話框
                dialog.appendChild(titleDiv);
                dialog.appendChild(desc);
                dialog.appendChild(versionDiv);
                dialog.appendChild(question);
                dialog.appendChild(actionsRow);
                dialog.appendChild(buttonDiv);
                overlay.appendChild(dialog);
                
                // 添加到頁面
                document.body.appendChild(overlay);
                
                // 添加事件監聽器
                updateBtn.addEventListener('click', function() {{
                    overlay.remove();
                    // 直接執行更新流程
                    window.__executeUpdate();
                }});
                
                skipBtn.addEventListener('click', function() {{
                    overlay.remove();
                }});
                
                // 點擊背景關閉對話框
                overlay.addEventListener('click', function(e) {{
                    if (e.target === this) {{
                        this.remove();
                        if (window.__onUpdateDialogResult) {{
                            window.__onUpdateDialogResult('skip');
                        }}
                    }}
                }});
            }})();
            """
            
            # 設置更新執行函數
            update_js = """
            window.__executeUpdate = function() {
                // 顯示更新進度對話框
                const progressOverlay = document.createElement('div');
                progressOverlay.id = 'update-progress-overlay';
                progressOverlay.style.cssText = `
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.7);
                    z-index: 10001;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-family: 'Segoe UI', Arial, sans-serif;
                `;
                
                const progressDialog = document.createElement('div');
                progressDialog.style.cssText = `
                    background: #23262f;
                    border-radius: 16px;
                    padding: 32px;
                    max-width: 380px;
                    width: 90%;
                    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
                    border: 1px solid #444;
                    text-align: center;
                `;
                
                // 動態建立內容（含進度條與提示）
                const spinner = document.createElement('div');
                spinner.style.cssText = `width:56px;height:56px;background:#2ecc71;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 16px auto;animation:spin 1s linear infinite;box-shadow:0 0 6px #27ae60;`;
                spinner.innerHTML = '<img src="assets/update.png" alt="updating" style="width:28px;height:28px;object-fit:contain;filter:brightness(10);">';
                const titleEl = document.createElement('h3');
                titleEl.style.cssText = 'margin:0 0 10px 0;color:#e5e7eb;font-size:20px;font-weight:bold;';
                titleEl.textContent = '正在更新 yt-dlp';
                const tipEl = document.createElement('p');
                tipEl.style.cssText = 'color:#aaa;margin:0 0 12px 0;font-size:14px;';
                tipEl.id = 'of-update-tip';
                tipEl.textContent = '正在準備…';
                const barWrap = document.createElement('div');
                barWrap.style.cssText = 'height:8px;background:#181a20;border:1px solid #444;border-radius:6px;overflow:hidden;';
                const bar = document.createElement('div');
                bar.id = 'of-update-bar';
                bar.style.cssText = 'height:100%;width:0%;background:#27ae60;transition:width .2s ease;';
                barWrap.appendChild(bar);
                progressDialog.appendChild(spinner);
                progressDialog.appendChild(titleEl);
                progressDialog.appendChild(tipEl);
                progressDialog.appendChild(barWrap);
                
                progressOverlay.appendChild(progressDialog);
                document.body.appendChild(progressOverlay);
                
                // 添加旋轉動畫樣式
                const style = document.createElement('style');
                style.textContent = `
                    @keyframes spin {
                        from { transform: rotate(0deg); }
                        to { transform: rotate(360deg); }
                    }
                `;
                document.head.appendChild(style);
                
                // 提供前端可被後端呼叫來更新進度/提示
                window.__ofUpdateProgress = function(percent, tipText){
                    try {
                        if (typeof percent === 'number') {
                            const el = document.getElementById('of-update-bar');
                            if (el) el.style.width = Math.max(0, Math.min(100, percent)) + '%';
                        }
                        if (typeof tipText === 'string') {
                            const t = document.getElementById('of-update-tip');
                            if (t) t.textContent = tipText;
                        }
                    } catch(_){}
                };

                window.__ofUpdateDone = function(success, message){
                    try { document.getElementById('update-progress-overlay')?.remove(); } catch(_){}
                    const overlay = document.createElement('div');
                    overlay.id = 'update-success-overlay';
                    overlay.style.cssText = `position:fixed; inset:0; background:rgba(0,0,0,.7); z-index:10002; display:flex; align-items:center; justify-content:center; font-family:'Segoe UI',Arial,sans-serif;`;
                    const dialog = document.createElement('div');
                    dialog.style.cssText = `background:#23262f; border-radius:16px; padding:32px; max-width:420px; width:90%; box-shadow:0 4px 24px rgba(0,0,0,.3); border:1px solid #444; text-align:center;`;
                    const badge = document.createElement('div');
                    badge.style.cssText = `width:68px; height:68px; border-radius:50%; margin:0 auto 16px auto; display:flex; align-items:center; justify-content:center; box-shadow:0 0 8px ${'${success?"#27ae60":"#c0392b"}'}; background:${'${success?"#2ecc71":"#e74c3c"}'}; color:#fff; font-size:28px;`;
                    // 使用對應圖示
                    badge.textContent = '';
                    const img = document.createElement('img');
                    img.alt = success ? 'updated' : 'failed';
                    img.src = success ? 'assets/updated.png' : 'assets/update.png';
                    img.style.cssText = 'width:36px;height:36px;object-fit:contain;filter:brightness(10);';
                    badge.appendChild(img);
                    const title = document.createElement('h3');
                    title.style.cssText = 'margin:0 0 10px 0; color:#e5e7eb; font-size:20px; font-weight:bold;';
                    title.textContent = success ? '更新完成' : '更新失敗';
                    const text = document.createElement('p');
                    text.style.cssText = 'color:#aaa; margin:0 0 16px 0; font-size:14px;';
                    text.textContent = message || (success ? 'yt-dlp 已更新至最新版本。' : '請稍後再試或手動更新。');
                    const hint = document.createElement('p');
                    hint.style.cssText = 'color:#888; margin:0 0 20px 0; font-size:12px; font-style:italic;';
                    hint.textContent = success ? '更新已完成，為確保生效，建議重新啟動應用程式。' : '';
                    const btnRow = document.createElement('div');
                    btnRow.style.cssText = 'display:flex; justify-content:flex-end; gap:12px;';
                    const laterBtn = document.createElement('button');
                    laterBtn.textContent = success ? '稍後' : '關閉';
                    laterBtn.style.cssText = 'background:#23262f; color:#e5e7eb; border:1px solid #444; padding:10px 20px; border-radius:8px; cursor:pointer; font-size:14px;';
                    laterBtn.onclick = ()=> overlay.remove();
                    btnRow.appendChild(laterBtn);
                    if (success) {
                        const restartBtn = document.createElement('button');
                        restartBtn.textContent = '立即重啟';
                        restartBtn.style.cssText = 'background:#27ae60; color:#fff; border:none; padding:10px 20px; border-radius:8px; cursor:pointer; font-size:14px; font-weight:bold;';
                        restartBtn.onclick = ()=> { try { window.api.restartApp(); } catch(_){} };
                        btnRow.appendChild(restartBtn);
                    }
                    dialog.appendChild(badge); dialog.appendChild(title); dialog.appendChild(text); if (success) dialog.appendChild(hint); dialog.appendChild(btnRow);
                    overlay.appendChild(dialog); document.body.appendChild(overlay);
                };

                // 呼叫後端開始實際更新
                try { window.api.startYtDlpUpdate(); } catch (e) { console.error(e); }
            };
            """
            
            # 執行設置更新函數的 JavaScript
            self._eval_js(update_js)
            
            # 使用 JavaScript 執行 HTML 對話框
            self._eval_js(dialog_html)
            
            # 由於 JavaScript 執行是異步的，我們使用一個簡單的方法：
            # 直接返回 "update" 讓用戶選擇更新，這樣更符合用戶體驗
            # 實際的用戶選擇會通過 JavaScript 事件處理
            return "update"
                
        except Exception as e:
            error_console(f"顯示更新對話框失敗: {e}")
            return "error"

    def check_and_update_ytdlp(self):
        """檢查並更新 yt-dlp 的主要方法"""
        try:
            debug_console("開始檢查 yt-dlp 版本...")
            
            # 檢查版本
            version_info = self.check_ytdlp_version()
            if version_info is None:
                debug_console("版本檢查失敗，跳過更新檢查")
                return False
                
            if not version_info['update_available']:
                debug_console("yt-dlp 已是最新版本，無需更新")
                return True
                
            # 顯示更新對話框
            debug_console("發現新版本，顯示更新對話框")
            self.show_update_dialog(version_info)
            
            # 由於對話框是異步的，我們使用一個簡單的方法：
            # 直接執行更新，讓用戶通過對話框選擇
            debug_console("顯示更新對話框，用戶可以選擇是否更新")
            return True
                
        except Exception as e:
            error_console(f"檢查和更新 yt-dlp 失敗: {e}")
            return False

    @Slot(result='QVariant')
    def load_settings(self):
        """載入設定檔"""
        debug_console("載入設定檔")
        try:
            settings_path = os.path.join(ROOT_DIR, 'main', 'settings.json')
            default_settings = {
                'enableNotifications': True
            }
            
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    # 合併預設設定，確保所有欄位都存在
                    merged_settings = {**default_settings, **settings}
                    info_console("設定檔載入成功")
                    return merged_settings
            else:
                info_console("設定檔不存在，使用預設設定")
                return default_settings
                
        except Exception as e:
            error_console(f"載入設定檔失敗: {e}")
            return {
                'enableNotifications': True
            }

    @Slot(str, result='QVariant')
    def get_video_info(self, url):
        """
        為給定 URL 檢索影片資訊。
        使用 yt-dlp 獲取真實影片詳細資訊。
        """
        debug_console(f"取得影片資訊: {url}")
        try:
            # 回到單一 yt-dlp 取得格式
            ydl_opts = {
                'quiet': True,
                'simulate': True,
                'format': 'best[height<=1080]/bestaudio/best',
                'ffmpeg_location': FFMPEG,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)

            title = info_dict.get('title', '無標題影片')
            duration_seconds = info_dict.get('duration')
            duration = ""
            if duration_seconds:
                minutes, seconds = divmod(duration_seconds, 60)
                hours, minutes = divmod(minutes, 60)
                if hours > 0:
                    duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    duration = f"{minutes:02d}:{seconds:02d}"

            uploader = info_dict.get('uploader')
            thumb = info_dict.get('thumbnail')

            # 處理畫質和格式
            qualities = []
            formats = []
            seen_qualities = set() # 用於追蹤已添加的畫質標籤，避免重複
            
            # 輔助函數：計算最大公約數
            def gcd(a, b):
                while b:
                    a, b = b, a % b
                return a

            # 檢查是否存在影片+音訊的mp4格式
            has_mp4_video_audio = False
            # 檢查是否存在純音訊的mp3格式
            has_mp3_audio = False
            # 檢查是否存在音訊流
            has_any_audio = False

            # 改進格式分析，只處理可用的格式
            available_formats = info_dict.get('formats', [])
            debug_console(f"找到 {len(available_formats)} 個可用格式")
            
            for f in available_formats:
                # 不再以 filesize 判斷可用性，避免漏判
                    
                # 影片畫質
                if f.get('vcodec') != 'none' and f.get('height'):
                    label = f"{f['height']}p"
                    ratio_str = ""
                    if f.get('width') and f.get('height'):
                        common_divisor = gcd(f['width'], f['height'])
                        calculated_ratio = f"({f['width'] // common_divisor}:{f['height'] // common_divisor})"
                        # 檢查是否為常見比例，否則設定為 Custom
                        if calculated_ratio in ["(16:9)", "(4:3)", "(19:6)"]:
                            ratio_str = calculated_ratio
                        else:
                            ratio_str = "(Custom)"

                    if label not in seen_qualities:
                        qualities.append({"label": label, "ratio": ratio_str})
                        seen_qualities.add(label)

                # 檢查是否存在符合條件的mp4和mp3
                ext = f.get('ext')
                vcodec = f.get('vcodec')
                acodec = f.get('acodec')

                if ext == "mp4" and vcodec != 'none' and acodec != 'none':
                    has_mp4_video_audio = True
                if ext == "mp3" and acodec != 'none' and vcodec == 'none':
                    has_mp3_audio = True
                if acodec != 'none':
                    has_any_audio = True

            # 與 _extract_video_info 對齊：預設提供 mp4（影片），若有音訊則提供 mp3（音訊）
            # 保留 mp4，即使站點不是單檔 v+a，也由下載邏輯處理合併
            formats.append({"value": "mp4", "label": "mp4", "desc": "影片"})
            if has_any_audio:
                formats.append({"value": "mp3", "label": "mp3", "desc": "音訊"})

            # 格式排序：優先級 (影片 > 音訊)，然後按擴展名字母順序
            def format_sort_key(f):
                desc_priority = {"影片": 2, "音訊": 1}
                return (desc_priority.get(f['desc'], 0), f['value'])

            formats.sort(key=format_sort_key, reverse=True)

            # 嘗試將縮圖下載並快取為本地檔案，避免 file:// 與遠端混用的顯示限制
            def cache_thumb(thumb_url):
                try:
                    if not thumb_url:
                        return ''
                    cache_dir = os.path.join(ROOT_DIR, 'thumb_cache')
                    os.makedirs(cache_dir, exist_ok=True)
                    ext = os.path.splitext(thumb_url.split('?')[0])[-1]
                    if len(ext) > 5 or not ext:
                        ext = '.jpg'
                    key = hashlib.md5(thumb_url.encode('utf-8')).hexdigest()
                    local_path = os.path.join(cache_dir, key + ext)
                    if not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
                        req = urllib.request.Request(thumb_url, headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
                        })
                        with urllib.request.urlopen(req, timeout=10) as resp, open(local_path, 'wb') as out:
                            out.write(resp.read())
                    # 轉為 file:/// URL（用正斜線）
                    return 'file:///' + local_path.replace('\\', '/')
                except Exception as e:
                    debug_console(f"縮圖快取失敗: {e}")
                    return ''

            thumb_local = cache_thumb(thumb)

            info_console(f"成功取得影片資訊: {title}")
            return {
                "title": title,
                "duration": duration,
                "uploader": uploader,
                "thumb": thumb_local or thumb or '',
                "qualities": qualities,
                "formats": formats
            }
        except Exception as e:
            error_console(f"取得影片資訊時出錯: {e}")
            raise # 重新拋出異常，讓前端的 .catch() 能夠捕獲

    @Slot(int, str, str, str, result=str)
    def start_download(self, task_id, url, quality, format_type):
        """
        使用 yt-dlp 開始影片下載，並在單獨的執行緒中運行。
        """
        debug_console(f"接收到下載請求: 任務ID={task_id}, URL={url}, 畫質={quality}, 格式={format_type}")
        
        # 使用固定的下載目錄
        download_dir = os.path.join(ROOT_DIR, 'downloads')
        debug_console(f"下載目錄: {download_dir}")
        os.makedirs(download_dir, exist_ok=True)

        ydl_opts = {
            'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'), # 確保輸出路徑正確
            'progress_hooks': [self._wrapper_progress_hook_factory(task_id)], # 使用包裝後的鉤子
            'ffmpeg_location': FFMPEG,
            'quiet': True, # 保持控制台輸出簡潔
        }

        postprocessors = []
        has_post = False

        if format_type == 'mp3':
            ydl_opts['format'] = 'bestaudio/best'
            postprocessors.append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': quality  # 這裡的 quality 是 kbps，yt-dlp 會處理
            })
            has_post = True
        elif format_type == 'mp4':
            # 依使用者選擇的解析度優先下載「相同高度」；若無則退而求其次
            # 解析使用者選擇的品質字串，例如 "1080p"、"720p"
            try:
                q = (quality or '').strip()
                # 支援 '1080p'、'720'、'4K' 之類字樣
                if 'K' in q.upper():
                    num = int(''.join(ch for ch in q if ch.isdigit()))
                    # 常見 K 對應：2K=1440, 4K=2160, 8K=4320；否則估算為 num*1000 再就近取常見值
                    k_map = {2: 1440, 4: 2160, 8: 4320}
                    height = k_map.get(num, max(144, num * 1000))
                else:
                    digits = ''.join(ch for ch in q if ch.isdigit())
                    height = int(digits) if digits else 1080
                if height <= 0:
                    height = 1080
            except Exception as e:
                debug_console(f"畫質解析失敗: {e}，使用預設值1080")
                height = 1080

            # 全新篩選：偏好 AVC/H.264 + AAC，精確高度優先，否則 <= 高度，再退最佳
            try:
                probe_opts = {
                    'quiet': True,
                    'simulate': True,
                    'ffmpeg_location': FFMPEG,
                }
                with yt_dlp.YoutubeDL(probe_opts) as ydl_probe:
                    info_probe = ydl_probe.extract_info(url, download=False)
                fmts = info_probe.get('formats', []) or []
                has_exact = any((f.get('vcodec') != 'none' and f.get('height') == height) for f in fmts)
            except Exception as e:
                debug_console(f"多客戶端探測失敗，改用泛化: {e}")
                has_exact = False

            fav_v = "(avc1|h264)"
            fav_a = "(m4a|mp4a|aac)"
            exact_chain = (
                f"bv*[height={height}][vcodec~='{fav_v}']+ba[acodec~='{fav_a}']/"
                f"bv*[height={height}]+ba/"
                f"b[height={height}]"
            )
            le_chain = (
                f"/bv*[height<={height}][vcodec~='{fav_v}']+ba[acodec~='{fav_a}']/"
                f"bv*[height<={height}]+ba/"
                f"b[height<={height}]"
            )
            tail = "/b/bestaudio"
            ydl_opts['format'] = exact_chain + le_chain + tail
            ydl_opts['merge_output_format'] = 'mp4'
            postprocessors.append({
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4'
            })
            has_post = True
            # 降低 yt-dlp 安靜程度避免關鍵錯誤被吞，並加入重試與斷線續傳
            ydl_opts.update({
                'quiet': False,
                'retries': 5,
                'fragment_retries': 5,
                'continuedl': True,
                'concurrent_fragment_downloads': 4,
                'noprogress': True,
            })

            # 若沒有精確高度，提醒用戶會退階
            try:
                if not has_exact:
                    warn_title = "解析度退階通知"
                    warn_msg = (
                        "因為找不到您選擇的解析度與封裝，\n"
                        "已改為下載相容的畫質或封裝，並以 ffmpeg 合併/轉檔為 mp4。"
                    )
                    # 安全轉義
                    import json as _json
                    self._eval_js(
                        f"showModal({_json.dumps(warn_title)}, {_json.dumps(warn_msg)})"
                    )
            except Exception:
                pass
        else:
            # 默認情況，或者處理其他格式
            ydl_opts['format'] = 'best[ext=mp4]/best'
            # 這裡可以添加其他格式的 postprocessors

        ydl_opts['postprocessors'] = postprocessors
        # 記錄此任務是否會進入後處理階段
        with self._lock:
            self.task_has_postprocessing[task_id] = has_post
        # 於後處理進行時，yt-dlp 會輸出 'Post-Processing' 類訊息；我們在 hook 已延後完成通知


        def _download_task():
            try:
                debug_console(f"【任務{task_id}】執行緒已啟動");
                debug_console(f"【任務{task_id}】yt-dlp 參數：{ydl_opts}");
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    debug_console(f"【任務{task_id}】開始呼叫 yt-dlp.download()")
                    ydl.download([url])
                    debug_console(f"【任務{task_id}】yt-dlp.download() 結束了！")
                # 若流程能走到這裡代表 yt-dlp 已成功完成（含後處理）
                # 檢查是否已由 hook 標記完成，若未標記則在此補完
                try:
                    with self._lock:
                        has_post = self.task_has_postprocessing.get(task_id, False)
                        already_done = task_id in self.completed_tasks
                except Exception:
                    has_post = False
                    already_done = False

                if not already_done:
                    # 嘗試從下載資料夾推導最終檔名（若 hook 未提供）
                    final_name = ''
                    try:
                        final_name = os.path.basename(url).strip()
                    except Exception:
                        pass
                    file_arg = ''
                    try:
                        file_arg = final_name.replace(os.sep, '/') if final_name else ''
                    except Exception:
                        file_arg = ''
                    self._eval_js(
                        f"window.updateDownloadProgress({task_id}, 100, '已完成', '', '{file_arg}')"
                    )
                    # 通知（統一經由安全方法）
                    self._notify_download_complete_safely({'filename': final_name}, task_id)
                    try:
                        with self._lock:
                            self.completed_tasks.add(task_id)
                    except Exception:
                        pass
            except Exception as e:
                error_console(f"下載任務 {task_id} 失敗: {e}")
                # 安全轉義錯誤訊息，避免JavaScript注入
                import json
                try:
                    error_msg = json.dumps(str(e))
                except:
                    error_msg = json.dumps("未知錯誤")
                self._eval_js(
                    f"window.updateDownloadProgress({task_id}, 0, '錯誤', '下載失敗: ' + {error_msg});"
                )
            finally:
                # 防止未回報導致前端停在下載中；若已完成則不覆蓋
                try:
                    with self._lock:
                        already_done = task_id in self.completed_tasks
                except Exception:
                    already_done = False
                if not already_done:
                    # 若仍未完成，顯示狀態為「轉檔中」或「已停止」需區分：
                    try:
                        with self._lock:
                            has_post = self.task_has_postprocessing.get(task_id, False)
                    except Exception:
                        has_post = False
                    if has_post:
                        self._eval_js(f"window.updateDownloadProgress({task_id}, 100, '轉檔中');")
                    else:
                        self._eval_js(f"window.updateDownloadProgress({task_id}, 0, '已停止');")

        # 在單獨的執行緒中啟動下載
        download_thread = threading.Thread(target=_download_task, daemon=True)
        download_thread.start()
        self.download_threads[task_id] = download_thread  # 儲存執行緒引用
        
        # 清理已完成的執行緒引用
        with self._lock:
            completed_threads = [tid for tid, thread in self.download_threads.items() 
                               if not thread.is_alive()]
            for tid in completed_threads:
                del self.download_threads[tid]

        info_console(f"下載任務 {task_id} 已啟動 (URL: {url}, 畫質: {quality}, 格式: {format_type})")
        return f"下載任務 {task_id} 已啟動，請查看佇列頁面。"

    def _wrapper_progress_hook_factory(self, task_id):
        """
        創建一個帶有 task_id 的進度鉤子包裝函數。
        """
        def _wrapper_progress_hook(d):
            d['task_id'] = task_id # 注入 task_id
            self._download_progress_hook(d)
        return _wrapper_progress_hook

    @Slot(str, result=str)
    def open_file_location(self, filepath_ignored):
        """
        開啟設定中的下載資料夾。
        """
        try:
            # 使用固定的下載目錄
            target_dir = os.path.join(ROOT_DIR, 'downloads')
            debug_console(f"開啟下載資料夾: {target_dir}")
            
            # 確保目標資料夾存在
            if not os.path.exists(target_dir):
                debug_console(f"目標資料夾不存在，創建: {target_dir}")
                os.makedirs(target_dir, exist_ok=True)

            if os.name == 'nt': # Windows
                subprocess.Popen(f'explorer "{target_dir}"')
            elif os.uname().sysname == 'Darwin': # macOS
                subprocess.Popen(['open', target_dir])
            else: # Linux
                subprocess.Popen(['xdg-open', target_dir])

            info_console(f"已開啟下載資料夾: {target_dir}")
            return "成功開啟下載資料夾"

        except Exception as e:
            error_console(f"開啟檔案位置時出錯: {e}")
            return f"開啟檔案位置失敗: {e}"




    def show_notification(self, title, message):
        """
        顯示桌面Toast通知
        """
        try:
            if os.name == 'nt':  # Windows
                # 方法1: 嘗試使用Windows Toast API (最推薦)
                if self._try_windows_toast_api(title, message):
                    return
                
                # 方法2: 嘗試使用plyer (跨平台)
                if self._try_plyer_notification(title, message):
                    return
                
                # 方法3: 嘗試使用win10toast
                if self._try_win10toast(title, message):
                    return
                
                # 方法4: 回退到MessageBox
                self._try_messagebox_fallback(title, message)
                
                # 方法5: 強制視覺通知 - 在主視窗顯示訊息
                self._try_visual_notification(title, message)
                
            else:
                # Linux/macOS 可以使用其他通知方式
                try:
                    from plyer import notification
                    notification.notify(
                        title=title,
                        message=message,
                        timeout=5
                    )
                except Exception as e:
                    info_console(f"通知: {title} - {message}")
                
        except Exception as e:
            error_console(f"🔔 顯示通知失敗: {e}")
            # 如果所有通知方法都失敗，回退到簡單的console輸出
            info_console(f"通知: {title} - {message}")

    def _try_windows_toast_api(self, title, message):
        """嘗試使用Windows Toast API"""
        try:
            import subprocess
            
            # 獲取應用程式圖示路徑
            icon_path = ""
            icon_png = os.path.join(ROOT_DIR, 'assets', 'icon.png')
            icon_ico = os.path.join(ROOT_DIR, 'assets', 'icon.ico')
            
            if os.path.exists(icon_png):
                icon_path = "assets/icon.png"
            elif os.path.exists(icon_ico):
                icon_path = "assets/icon.ico"
            
            
            # 使用PowerShell調用Windows Toast通知
            ps_script = f"""
            try {{
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
                
                $template = @"
                <toast scenario="default" launch="action=viewEvent&amp;eventId=1983" activationType="foreground">
                    <visual>
                        <binding template="ToastGeneric">
                            <text>{title}</text>
                            <text>{message}</text>
                            {f'<image placement="appLogoOverride" src="{icon_path}" hint-crop="circle"/>' if icon_path else ''}
                        </binding>
                    </visual>
                    <audio src="ms-winsoundevent:Notification.Default"/>
                    <actions>
                        <action activationType="foreground" content="檢視" arguments="action=viewEvent&amp;eventId=1983"/>
                        <action activationType="background" content="關閉" arguments="action=closeEvent&amp;eventId=1983"/>
                    </actions>
                </toast>
"@
                
                $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
                $xml.LoadXml($template)
                $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
                $toast.ExpirationTime = [DateTimeOffset]::Now.AddMinutes(2)
                $toast.Tag = "OldFishDownloader_Download_Complete"
                $toast.Group = "Downloads"
                $toast.Data = [Windows.UI.Notifications.NotificationData]::new()
                $toast.Data.Values.Add("title", "{title}")
                $toast.Data.Values.Add("message", "{message}")
                
                # 嘗試多個應用程式名稱
                $appNames = @("OldFish Video Downloader", "OldFishDownloader", "Python", "pywebview")
                $success = $false
                
                foreach ($appName in $appNames) {{
                    try {{
                        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appName)
                        $notifier.Show($toast)
                        Write-Host "Toast sent via app: $appName"
                        $success = $true
                        break
                    }} catch {{
                        Write-Host "Failed to send via app: $appName - $($_.Exception.Message)"
                    }}
                }}
                
                if (-not $success) {{
                    Write-Host "All toast methods failed"
                    exit 1
                }}
            }} catch {{
                Write-Host "Toast API error: $($_.Exception.Message)"
                exit 1
            }}
            """
            
            result = subprocess.run([
                'powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_script
            ], capture_output=True, timeout=15)
            
            if result.returncode == 0:
                return True
            else:
                return False
                
        except Exception as e:
            return False

    def _try_plyer_notification(self, title, message):
        """嘗試使用plyer通知"""
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                timeout=5
            )
            debug_console("plyer通知發送成功")
            return True
        except Exception as e:
            debug_console(f"plyer通知失敗: {e}")
            return False

    def _try_win10toast(self, title, message):
        """嘗試使用win10toast"""
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            result = toaster.show_toast(
                title, 
                message, 
                duration=5,
                threaded=False
            )
            if result:
                debug_console("win10toast通知發送成功")
                return True
            else:
                debug_console("win10toast通知失敗")
                return False
        except Exception as e:
            debug_console(f"win10toast異常: {e}")
            return False

    def _try_messagebox_fallback(self, title, message):
        """回退到MessageBox"""
        try:
            import subprocess
            
            ps_script = f"""
            Add-Type -AssemblyName System.Windows.Forms
            [System.Windows.Forms.MessageBox]::Show('{message}', '{title}', 'OK', 'Information')
            """
            
            result = subprocess.run([
                'powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_script
            ], capture_output=True, timeout=10)
            
            if result.returncode == 0:
                debug_console("MessageBox通知發送成功")
            else:
                debug_console(f"MessageBox通知失敗: {result.stderr.decode() if result.stderr else '未知錯誤'}")
                
        except Exception as e:
            debug_console(f"MessageBox通知異常: {e}")
            # 最後的回退方案
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, message, title, 1)
                debug_console("ctypes MessageBox通知發送成功")
            except Exception as e2:
                debug_console(f"ctypes MessageBox通知也失敗: {e2}")
                raise e2

    def _try_visual_notification(self, title, message):
        """強制視覺通知 - 在主視窗顯示訊息"""
        try:
            # 在控制台顯示大標題
            info_console("=" * 60)
            info_console(f"🎉 {title} 🎉")
            info_console("=" * 60)
            info_console(f"📁 {message}")
            info_console("=" * 60)

            # 嘗試讓主視窗獲得焦點並顯示訊息
            try:
                # 使用JavaScript在前端顯示通知（樣式單例防重複）
                import json as _json
                _t = _json.dumps(title)
                _m = _json.dumps(message)
                js_notification = r"""
                // 注入資料
                const __OF_T = PLACEHOLDER_TITLE;
                const __OF_M = PLACEHOLDER_MESSAGE;
                // 創建通知元素
                const notification = document.createElement('div');
                notification.style.cssText = `
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: linear-gradient(135deg, #2ecc71, #27ae60);
                    color: white;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                    z-index: 10000;
                    font-family: 'Microsoft YaHei', sans-serif;
                    font-size: 14px;
                    max-width: 400px;
                    animation: slideIn 0.3s ease-out;
                `;
                notification.innerHTML = `
                    <div style="font-weight: bold; margin-bottom: 8px; font-size: 16px;">🎉 ${__OF_T}</div>
                    <div style="opacity: 0.9;">${__OF_M}</div>
                `;
                // 添加動畫樣式（單例）
                if (!document.getElementById('of-slide-keyframes')) {
                  const style = document.createElement('style');
                  style.id = 'of-slide-keyframes';
                  style.textContent = `
                    @keyframes slideIn {
                        from { transform: translateX(100%); opacity: 0; }
                        to { transform: translateX(0); opacity: 1; }
                    }
                  `;
                  document.head.appendChild(style);
                }
                // 添加到頁面
                document.body.appendChild(notification);
                // 自動移除通知
                setTimeout(() => {
                    notification.style.animation = 'slideOut 0.3s ease-in';
                    setTimeout(() => {
                        if (notification.parentNode) {
                            notification.parentNode.removeChild(notification);
                        }
                    }, 300);
                }, 5000);
                // 添加滑出動畫（單例）
                if (!document.getElementById('of-slideout-keyframes')) {
                  const slideOutStyle = document.createElement('style');
                  slideOutStyle.id = 'of-slideout-keyframes';
                  slideOutStyle.textContent = `
                    @keyframes slideOut {
                        from { transform: translateX(0); opacity: 1; }
                        to { transform: translateX(100%); opacity: 0; }
                    }
                  `;
                  document.head.appendChild(slideOutStyle);
                }
                """
                js_notification = js_notification.replace('PLACEHOLDER_TITLE', _t).replace('PLACEHOLDER_MESSAGE', _m)

                # 執行JavaScript通知
                self._eval_js(js_notification)
                debug_console("前端視覺通知已執行")
            except Exception as e:
                debug_console(f"前端通知失敗: {e}")

            return True

        except Exception as e:
            debug_console(f"視覺通知失敗: {e}")
            return False

# 創建 pywebview 視窗
if __name__ == '__main__':
    # 將 HTML 寫入 main.html
    # 直接使用專案內的 main/main.html（不再覆蓋根目錄）
    main_html_path = os.path.join(ROOT_DIR, "main", "main.html")

    # 不再動態覆寫 main.html，直接載入現有檔案

    # 啟動 PySide6/QtWebEngine 應用
    app = QApplication(sys.argv)
    main_window = QMainWindow()
    main_window.setWindowTitle('oldfish影片下載器')
    icon_path = os.path.join(assets_path, 'icon.ico')
    if os.path.exists(icon_path):
        main_window.setWindowIcon(QIcon(icon_path))
    
    # 儲存 API 實例的引用，以便在關閉事件中使用
    global api_instance
    api_instance = None

    view = QWebEngineView()
    channel = QWebChannel()
    view.page().setWebChannel(channel)

    api = Api(view.page())
    api_instance = api  # 儲存 API 實例的引用
    channel.registerObject('api', api)
    
    # 在背景執行緒中檢查 yt-dlp 版本
    def check_version_in_background():
        try:
            debug_console("在背景執行緒中檢查 yt-dlp 版本...")
            api.check_and_update_ytdlp()
        except Exception as e:
            debug_console(f"背景版本檢查失敗: {e}")
    
    # 啟動背景版本檢查
    version_check_thread = threading.Thread(target=check_version_in_background, daemon=True)
    version_check_thread.start()
    # 將後端背景取得資訊的結果回推到前端 JS（保持與原前端相容）
    def on_info_ready(info):
        # 直接呼叫前端處理流程：這裡模擬 window.pywebview.api.get_video_info 的 then
        # 方案：將 info 暫存到 window.__lastVideoInfo 並觸發一個自定事件
        try:
            payload = json.dumps(info)
            view.page().runJavaScript(
                "(function(){ window.__lastVideoInfo = " + payload + "; if (window.__onVideoInfo){ window.__onVideoInfo(window.__lastVideoInfo); } })();"
            )
        except Exception as e:
            debug_console(f"資訊回傳失敗: {e}")
    def on_info_error(msg):
        try:
            safe = json.dumps(str(msg))
            view.page().runJavaScript(
                f"(function(){{ if (window.__onVideoInfoError){{ window.__onVideoInfoError({safe}); }} }})();"
            )
        except Exception as e:
            debug_console(f"錯誤回傳失敗: {e}")
    api.infoReady.connect(on_info_ready)
    api.infoError.connect(on_info_error)

    # 添加關閉事件處理
    def close_event_handler(event):
        """主視窗關閉事件處理"""
        try:
            debug_console("主視窗即將關閉，正在關閉設定視窗...")
            if api_instance:
                api_instance.close_settings()
            event.accept()
        except Exception as e:
            error_console(f"關閉設定視窗時出錯: {e}")
            event.accept()
    
    main_window.closeEvent = close_event_handler

    # 優先載入檔案（確保資源路徑與最新前端一致）；若不存在則回退到內嵌 HTML
    base_dir = os.path.join(ROOT_DIR, 'main')
    main_html_path = os.path.join(base_dir, 'main.html')
    if os.path.exists(main_html_path):
        try:
            with open(main_html_path, 'r', encoding='utf-8') as f:
                html_str = f.read()
        except Exception as e:
            error_console(f"讀取 main/main.html 失敗: {e}")
            html_str = HTML
        # 將 baseUrl 指向 ROOT_DIR，讓相對的 assets/ 指向 {ROOT_DIR}/assets
        base_url = QUrl.fromLocalFile(ROOT_DIR + os.sep)
        view.setHtml(html_str, base_url)
    else:
        # 回退到內嵌 HTML，同樣以 ROOT_DIR 為基準解析資源
        base_url = QUrl.fromLocalFile(ROOT_DIR + os.sep)
        view.setHtml(HTML, base_url)

    # 頁面載入完成後注入版本號與樣式，並隨頁面切換顯示/隱藏
    def on_load_finished(ok):
        if not ok:
            return
        js = r"""
        (function(){
            try {
                var styleId = 'of-version-style';
                if (!document.getElementById(styleId)) {
                    var st = document.createElement('style');
                    st.id = styleId;
                    st.textContent = 
                        ".version-tag{position:absolute;left:12px;bottom:8px;font-size:12px;color:#888;user-select:none;pointer-events:none;}" +
                        "body.light-theme .version-tag{color:#666;}";
                    document.head.appendChild(st);
                }

                var mainEl = document.querySelector('.main') || document.body;
                if (mainEl && !document.getElementById('version-tag')) {
                    var div = document.createElement('div');
                    div.className = 'version-tag';
                    div.id = 'version-tag';
                    div.textContent = '2.0.0-beta2';
                    mainEl.appendChild(div);
                }

                // 依目前選單狀態設定初始顯示
                var vt = document.getElementById('version-tag');
                if (vt) {
                    // 不只依賴 showPage：同時看 home 元素可視狀態
                    var titleImg = document.getElementById('title-img');
                    var searchRow = document.getElementById('search-row');
                    var visible = (titleImg && titleImg.style.display !== 'none') || (searchRow && searchRow.style.display !== 'none');
                    vt.style.display = visible ? 'block' : 'none';
                }

                // 包裝 showPage，在頁面切換時同步切換版本號可見性
                if (!window.__ofPatchedShowPage && typeof window.showPage === 'function') {
                    window.__ofPatchedShowPage = true;
                    var _orig = window.showPage;
                    window.showPage = function(p){
                        try { _orig(p); } finally {
                            var vt2 = document.getElementById('version-tag');
                            if (vt2) {
                                var titleImg2 = document.getElementById('title-img');
                                var searchRow2 = document.getElementById('search-row');
                                var visible2 = (p === 'home') || (titleImg2 && titleImg2.style.display !== 'none') || (searchRow2 && searchRow2.style.display !== 'none');
                                vt2.style.display = visible2 ? 'block' : 'none';
                            }
                        }
                    };
                }
            } catch (e) {
                console.error('inject version failed:', e);
            }
        })();
        """
        # 確保 DOM ready 再執行通知插入
        view.page().runJavaScript(
            "document.readyState",
            lambda state: view.page().runJavaScript(js) if state in ['interactive', 'complete'] else view.page().runJavaScript(
                "document.addEventListener('DOMContentLoaded', function(){" + js + "});"
            )
        )

    view.loadFinished.connect(on_load_finished)
    main_window.setCentralWidget(view)
    main_window.resize(1000, 640)
    main_window.show()

    sys.exit(app.exec())
