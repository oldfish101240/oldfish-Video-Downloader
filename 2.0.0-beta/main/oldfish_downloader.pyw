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
        .queue-list {{
            width: 90%; /* 調整列表寬度 */
            max-width: 800px; /* 最大寬度限制 */
            margin-top: 30px; /* 距離頂部間距 */
            display: flex;
            flex-direction: column;
            align-items: center; /* 讓列表項居中 */
            padding-bottom: 50px; /* 底部留白 */
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
            margin: 20px auto; /* 居中並調整間距 */
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
            const queueList = document.getElementById('queue-list'); // Get reference to queue list
            const settingsBtn = document.getElementById('settings-btn'); // 獲取設定按鈕

            if (pageName === 'home') {{
                document.getElementById('nav-home').classList.add('selected');
                
                if (titleImg) titleImg.style.display = 'block'; // 顯示主頁元素
                if (searchRow) searchRow.style.display = 'flex';
                if (settingsBtn) settingsBtn.style.display = 'block'; // 顯示設定按鈕
                
                if (queuePage) queuePage.style.display = 'none'; // 隱藏其他頁面
                if (queueList) queueList.innerHTML = ''; // 清空佇列列表內容

            }} else if (pageName === 'queue') {{
                document.getElementById('nav-queue').classList.add('selected');
                
                if (titleImg) titleImg.style.display = 'none'; // 隱藏主頁元素
                if (searchRow) searchRow.style.display = 'none';
                if (settingsBtn) settingsBtn.style.display = 'none'; // 隱藏設定按鈕
                
                if (queuePage) queuePage.style.display = 'flex'; // 顯示佇列頁面
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
                    showModal('錯誤', '顯示找不到影片，請確認網址是否輸入正確');
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
            const urlInput = document.getElementById('video-url');
            const url = urlInput.value.trim();
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

            // 點擊下載後清空輸入框
            urlInput.value = '';

            // 呼叫 Python API 開始下載 (在背景執行)
            // 將任務的ID傳遞給Python，以便Python可以回報進度
            window.pywebview.api.start_download(downloadQueue[downloadQueue.length - 1].id, url, quality, format)
                .then(result => {{
                    console.log("下載任務啟動結果:", result);
                    // 這裡可以根據Python回傳的結果更新任務狀態
                    // 例如：updateDownloadProgress(taskId, 100, '已完成');
                }})
                .catch(error => {{
                    console.error("啟動下載任務時出錯:", error);
                    // 如果啟動失敗，更新任務狀態為錯誤
                    // 例如：updateDownloadProgress(taskId, 0, '錯誤');
                }});
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
            // 這裡不再檢查 task.filePath，因為後端會固定開啟 downloads 資料夾
            window.pywebview.api.open_file_location("") // 傳遞空字串，因為後端會忽略它
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

        // 首次載入時，確保顯示主頁
        document.addEventListener('DOMContentLoaded', () => {{
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

    def _extract_video_info(self, url):
        ydl_opts = {
            'quiet': True,
            'simulate': True,
            'force_generic_extractor': True,
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
        for f in info_dict.get('formats', []):
            if f.get('vcodec') != 'none' and f.get('height'):
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
        if has_mp4_video_audio:
            formats.append({'value': 'mp4', 'label': 'mp4', 'desc': '影片+音訊'})
        if has_mp3_audio or has_any_audio:
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
            # 下載完成
            debug_console(f"【任務{task_id}】檢測到下載完成狀態: {d}")
            
            # yt-dlp 在 finished 狀態下會提供最終檔案路徑
            filepath = d.get('filepath', '')
            if not filepath: # 備用方案，如果 filepath 不存在
                filename = d.get('filename')
                if filename:
                    filepath = os.path.join(ROOT_DIR, 'downloads', filename)
            
            debug_console(f"【任務{task_id}】最終檔案路徑: {filepath}")
            
            self._eval_js(f"window.updateDownloadProgress({task_id}, 100, '已完成', '', '{filepath.replace(os.sep, '/')}')") # 將路徑傳遞給前端
            end_progress_line()
            info_console(f"任務 {task_id}: 下載完成 - {d['filename']}")
            
            # 下載完成通知
            debug_console(f"【任務{task_id}】開始處理下載完成通知")
            try:
                settings = self.load_settings()
                debug_console(f"【任務{task_id}】載入設定: {settings}")
                debug_console(f"【任務{task_id}】下載完成通知設定檢查: enableNotifications = {settings.get('enableNotifications', True)}")
                
                if settings.get('enableNotifications', True):
                    filename = d.get('filename', '未知檔案')
                    # 只提取檔案名稱，不包含路徑
                    if os.path.sep in filename:
                        filename = os.path.basename(filename)
                    
                    title = "下載完成"
                    message = f"影片已成功下載：{filename}"
                    debug_console(f"【任務{task_id}】準備發送通知: {title} - {message}")
                    
                    # 強制發送通知
                    debug_console(f"【任務{task_id}】調用show_notification方法")
                    self.show_notification(title, message)
                    debug_console(f"【任務{task_id}】show_notification方法調用完成")
                    
                    info_console(f"影片下載完成：{filename}")
                else:
                    debug_console(f"【任務{task_id}】通知已停用，跳過通知")
            except Exception as e:
                debug_console(f"【任務{task_id}】處理下載完成通知失敗: {e}")
                import traceback
                debug_console(f"【任務{task_id}】錯誤詳情: {traceback.format_exc()}")
                filename = d.get('filename', '未知檔案')
                info_console(f"影片下載完成：{filename}")
            
            # 線程安全的添加完成任務
            try:
                with self._lock:
                    self.completed_tasks.add(task_id)
            except Exception:
                pass
        elif d['status'] == 'error':
            # 下載錯誤
            self._eval_js(f"window.updateDownloadProgress({task_id}, 0, '錯誤', '{d.get('error', '未知錯誤')}');")
            end_progress_line()
            error_console(f"任務 {task_id}: 下載錯誤 - {d.get('error', '未知錯誤')}")
        else:
            # 其他狀態
            self._eval_js(f"window.updateDownloadProgress({task_id}, 0, '{d['status']}');")
            end_progress_line()
            debug_console(f"任務 {task_id}: 狀態 - {d['status']}")


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
                # 設定視窗已經開啟，嘗試將焦點調到該視窗
                try:
                    # 嘗試將設定視窗調到最前面
                    import ctypes
                    user32 = ctypes.windll.user32
                    
                    # 查找設定視窗
                    def find_settings_window(hwnd, windows):
                        if user32.IsWindowVisible(hwnd):
                            length = user32.GetWindowTextLengthW(hwnd)
                            if length > 0:
                                buffer = ctypes.create_unicode_buffer(length + 1)
                                user32.GetWindowTextW(hwnd, buffer, length + 1)
                                if "設定" in buffer.value and "oldfish" in buffer.value:
                                    windows.append(hwnd)
                        return True
                    
                    windows = []
                    from ctypes import wintypes
                    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
                    user32.EnumWindows(EnumWindowsProc(find_settings_window), 0)
                    
                    if windows:
                        # 將視窗提到最前面
                        user32.SetForegroundWindow(windows[0])
                        user32.ShowWindow(windows[0], 9)  # SW_RESTORE
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
                python_exe = os.path.join(ROOT_DIR, 'python_embed', 'python.exe')
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

    @Slot(result='QVariant')
    def load_settings(self):
        """載入設定檔"""
        debug_console("載入設定檔")
        try:
            settings_path = os.path.join(ROOT_DIR, 'settings.json')
            default_settings = {
                'downloadPath': 'downloads',  # 使用相對路徑，確保程式可移植性
                'enableNotifications': True
            }
            
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    # 處理下載路徑：如果是相對路徑，轉換為絕對路徑
                    if 'downloadPath' in settings:
                        if not os.path.isabs(settings['downloadPath']):
                            settings['downloadPath'] = os.path.join(ROOT_DIR, settings['downloadPath'])
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
                'downloadPath': 'downloads',  # 使用相對路徑，確保程式可移植性
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
            ydl_opts = {
                'quiet': True,
                'simulate': True,
                'force_generic_extractor': True,
                # 改進format參數，避免嘗試下載不可用的格式
                'format': 'best[height<=1080]/bestaudio/best',
                'ffmpeg_location': FFMPEG, # 明確指定 ffmpeg 路徑
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
                # 跳過明顯不可用的格式
                if f.get('filesize') == 0 or f.get('filesize') is None:
                    continue
                    
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

            # 確保僅有 mp4 (影片+音訊) 和 mp3 (音訊) 選項
            # 如果原始資訊中沒有找到，則手動添加
            if has_mp4_video_audio:
                formats.append({"value": "mp4", "label": "mp4", "desc": "影片+音訊"})
            if has_mp3_audio or has_any_audio:
                formats.append({"value": "mp3", "label": "mp3", "desc": "音訊"})

            # 格式排序：優先級 (影片+音訊 > 音訊)，然後按擴展名字母順序
            def format_sort_key(f):
                desc_priority = {"影片+音訊": 2, "音訊": 1} # 調整優先級
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
        
        # 確保下載目錄存在，使用設定中的路徑
        try:
            settings = self.load_settings()
            download_path = settings.get('downloadPath', 'downloads')
            # 如果是相對路徑，轉換為絕對路徑
            if not os.path.isabs(download_path):
                download_dir = os.path.join(ROOT_DIR, download_path)
            else:
                download_dir = download_path
        except:
            download_dir = os.path.join(ROOT_DIR, 'downloads')
        os.makedirs(download_dir, exist_ok=True)

        ydl_opts = {
            'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'), # 確保輸出路徑正確
            'progress_hooks': [self._wrapper_progress_hook_factory(task_id)], # 使用包裝後的鉤子
            'ffmpeg_location': FFMPEG,
            'quiet': True, # 保持控制台輸出簡潔
        }

        postprocessors = []

        if format_type == 'mp3':
            ydl_opts['format'] = 'bestaudio/best'
            postprocessors.append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': quality  # 這裡的 quality 是 kbps，yt-dlp 會處理
            })
        elif format_type == 'mp4':
            # 只根據畫質選擇 mp4 格式，讓 yt-dlp 自動合併
            try:
                height = int(quality.replace("p", "").replace("K", "000"))
                if height <= 0:
                    height = 1080
            except (ValueError, AttributeError) as e:
                debug_console(f"畫質解析失敗: {e}，使用預設值1080")
                height = 1080
            # 改進format參數，使用更安全的選擇邏輯
            ydl_opts['format'] = f'best[height<={height}][ext=mp4]/best[height<={height}]/best'
            ydl_opts['merge_output_format'] = 'mp4'
            postprocessors.append({
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4'
            })
            # 降低 yt-dlp 安靜程度避免關鍵錯誤被吞，並加入重試與斷線續傳
            ydl_opts.update({
                'quiet': False,
                'retries': 5,
                'fragment_retries': 5,
                'continuedl': True,
                'concurrent_fragment_downloads': 4,
                'noprogress': True,
            })
        else:
            # 默認情況，或者處理其他格式
            ydl_opts['format'] = 'best[ext=mp4]/best'
            # 這裡可以添加其他格式的 postprocessors

        ydl_opts['postprocessors'] = postprocessors


        def _download_task():
            try:
                debug_console(f"【任務{task_id}】執行緒已啟動");
                debug_console(f"【任務{task_id}】yt-dlp 參數：{ydl_opts}");
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    debug_console(f"【任務{task_id}】開始呼叫 yt-dlp.download()")
                    ydl.download([url])
                    debug_console(f"【任務{task_id}】yt-dlp.download() 結束了！")
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
                # 線程安全的檢查完成狀態
                try:
                    with self._lock:
                        already_done = task_id in self.completed_tasks
                except Exception:
                    already_done = False
                if not already_done:
                    self._eval_js(
                        f"window.updateDownloadProgress({task_id}, 0, '已停止');"
                    )

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
    def open_file_location(self, filepath_ignored): # 參數名稱更改為 filepath_ignored
        """
        總是開啟下載檔案的資料夾 (即 downloads 目錄)。
        """
        debug_console(f"嘗試開啟下載資料夾...")
        try:
            target_dir = os.path.join(ROOT_DIR, 'downloads')
            
            # 確保目標資料夾存在
            os.makedirs(target_dir, exist_ok=True) # 確保資料夾存在

            if os.name == 'nt': # Windows
                subprocess.Popen(f'explorer "{target_dir}"')
            elif os.uname().sysname == 'Darwin': # macOS
                subprocess.Popen(['open', target_dir])
            else: # Linux
                subprocess.Popen(['xdg-open', target_dir])

            info_console(f"已開啟資料夾: {target_dir}")
            return "成功開啟資料夾"

        except Exception as e:
            error_console(f"開啟檔案位置時出錯: {e}")
            return f"開啟檔案位置失敗: {e}"




    def show_notification(self, title, message):
        """
        顯示桌面Toast通知
        """
        debug_console(f"🔔 顯示Toast通知: {title} - {message}")
        debug_console(f"🔔 作業系統: {os.name}")
        
        try:
            if os.name == 'nt':  # Windows
                debug_console("🔔 開始嘗試Windows通知方法")
                
                # 方法1: 嘗試使用Windows Toast API (最推薦)
                debug_console("🔔 嘗試Windows Toast API...")
                if self._try_windows_toast_api(title, message):
                    debug_console("🔔 Windows Toast API成功")
                    return
                debug_console("🔔 Windows Toast API失敗，嘗試下一個方法")
                
                # 方法2: 嘗試使用plyer (跨平台)
                debug_console("🔔 嘗試plyer...")
                if self._try_plyer_notification(title, message):
                    debug_console("🔔 plyer成功")
                    return
                debug_console("🔔 plyer失敗，嘗試下一個方法")
                
                # 方法3: 嘗試使用win10toast
                debug_console("🔔 嘗試win10toast...")
                if self._try_win10toast(title, message):
                    debug_console("🔔 win10toast成功")
                    return
                debug_console("🔔 win10toast失敗，嘗試下一個方法")
                
                # 方法4: 回退到MessageBox
                debug_console("🔔 嘗試MessageBox回退...")
                self._try_messagebox_fallback(title, message)
                debug_console("🔔 MessageBox回退完成")
                
                # 方法5: 強制視覺通知 - 在主視窗顯示訊息
                debug_console("🔔 嘗試強制視覺通知...")
                self._try_visual_notification(title, message)
                debug_console("🔔 強制視覺通知完成")
                
            else:
                # Linux/macOS 可以使用其他通知方式
                debug_console("🔔 非Windows系統，嘗試plyer")
                try:
                    from plyer import notification
                    notification.notify(
                        title=title,
                        message=message,
                        timeout=5
                    )
                    debug_console("🔔 plyer通知成功")
                except Exception as e:
                    debug_console(f"🔔 plyer通知失敗: {e}")
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
            
            debug_console(f"圖示路徑: {icon_path}")
            
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
            
            debug_console(f"Toast API結果: {result.returncode}")
            if result.stdout:
                debug_console(f"Toast API輸出: {result.stdout.decode()}")
            if result.stderr:
                debug_console(f"Toast API錯誤: {result.stderr.decode()}")
            
            if result.returncode == 0:
                debug_console("Windows Toast API通知發送成功")
                return True
            else:
                debug_console(f"Windows Toast API失敗: {result.stderr.decode() if result.stderr else '未知錯誤'}")
                return False
                
        except Exception as e:
            debug_console(f"Windows Toast API異常: {e}")
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
                # 使用JavaScript在前端顯示通知
                js_notification = f"""
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
                    <div style="font-weight: bold; margin-bottom: 8px; font-size: 16px;">🎉 {title}</div>
                    <div style="opacity: 0.9;">{message}</div>
                `;
                
                // 添加動畫樣式
                const style = document.createElement('style');
                style.textContent = `
                    @keyframes slideIn {{
                        from {{ transform: translateX(100%); opacity: 0; }}
                        to {{ transform: translateX(0); opacity: 1; }}
                    }}
                `;
                document.head.appendChild(style);
                
                // 添加到頁面
                document.body.appendChild(notification);
                
                // 自動移除通知
                setTimeout(() => {{
                    notification.style.animation = 'slideOut 0.3s ease-in';
                    setTimeout(() => {{
                        if (notification.parentNode) {{
                            notification.parentNode.removeChild(notification);
                        }}
                    }}, 300);
                }}, 5000);
                
                // 添加滑出動畫
                const slideOutStyle = document.createElement('style');
                slideOutStyle.textContent = `
                    @keyframes slideOut {{
                        from {{ transform: translateX(0); opacity: 1; }}
                        to {{ transform: translateX(100%); opacity: 0; }}
                    }}
                `;
                document.head.appendChild(slideOutStyle);
                """
                
                # 執行JavaScript通知
                self._eval_js(js_notification)
                debug_console("前端視覺通知已執行")
                
            except Exception as e:
                debug_console(f"前端通知失敗: {e}")
            
            return True
            
        except Exception as e:
            debug_console(f"視覺通知失敗: {e}")
            return False

    @Slot(str, str, result=str)
    def test_notification(self, title, message):
        """
        測試通知功能
        """
        try:
            self.show_notification(title, message)
            return "通知已發送"
        except Exception as e:
            error_console(f"測試通知失敗: {e}")
            return f"通知發送失敗: {e}"

# 創建 pywebview 視窗
if __name__ == '__main__':
    # 將 HTML 寫入 main.html
    main_html_path = os.path.join(ROOT_DIR, "main.html")

    # 檢查檔案是否存在，如果存在則刪除
    if os.path.exists(main_html_path):
        try:
            os.remove(main_html_path)
            info_console(f"已刪除現有的 main.html 檔案: {main_html_path}")
        except OSError as e:
            error_console(f"刪除 main.html 檔案時出錯: {e}")

    # 寫入 HTML
    try:
        with open(main_html_path, "w", encoding="utf-8") as f:
            f.write(HTML)
        debug_console(f"HTML已寫入: {main_html_path}")
    except IOError as e:
        error_console(f"寫入 main.html 檔案時出錯: {e}")

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

    # 載入本地 HTML
    view.load(QUrl.fromLocalFile(main_html_path))
    main_window.setCentralWidget(view)
    main_window.resize(900, 700)
    main_window.show()

    sys.exit(app.exec())
