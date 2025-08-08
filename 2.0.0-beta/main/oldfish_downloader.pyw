import webview
import os
import time
import yt_dlp # 導入 yt-dlp 庫
import math # 導入 math 模組用於計算 GCD
import threading # 導入 threading 模組用於非同步下載
import subprocess # 導入 subprocess 模組用於開啟檔案位置

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
            position: absolute;
            right: 24px;
            bottom: 24px;
            width: 28px;
            height: 28px;
            background: none;
            border: none;
            cursor: pointer;
        }}
        .settings-btn img {{
            width: 28px;
            height: 28px;
            filter: brightness(0.85);
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
        .video-modal-select {{
            width: 100%;
            padding: 8px 12px;
            border-radius: 8px;
            border: 1px solid #444;
            background: #23262f;
            color: #e5e7eb;
            font-size: 15px;
            margin-bottom: 0;
        }}
        .video-modal-actions {{
            display: flex;
            justify-content: flex-end;
            align-items: center;
            gap: 12px;
            padding: 24px 32px 32px 32px;
        }}
        .video-modal-btn {{
            background: #27ae60;
            color: #fff;
            border: none;
            border-radius: 8px;
            padding: 0 28px;
            height: 38px;
            font-size: 16px;
            cursor: pointer;
            font-weight: bold;
            transition: background 0.2s;
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
                    <select class="video-modal-select" id="video-modal-quality"></select>
                    <div class="video-modal-label" style="margin-top:18px;">影片格式</div>
                    <select class="video-modal-select" id="video-modal-format" onchange="onFormatChange()"></select>
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
            const settingsBtn = document.getElementById('settings-btn');
            const queuePage = document.getElementById('queue-page');
            const queueList = document.getElementById('queue-list'); // Get reference to queue list

            if (pageName === 'home') {{
                document.getElementById('nav-home').classList.add('selected');
                
                titleImg.style.display = 'block'; // 顯示主頁元素
                searchRow.style.display = 'flex';
                settingsBtn.style.display = 'block';
                
                queuePage.style.display = 'none'; // 隱藏佇列頁面
                queueList.innerHTML = ''; // 清空佇列列表內容

            }} else if (pageName === 'queue') {{
                document.getElementById('nav-queue').classList.add('selected');
                
                titleImg.style.display = 'none'; // 隱藏主頁元素
                searchRow.style.display = 'none';
                settingsBtn.style.display = 'none';
                
                queuePage.style.display = 'flex'; // 顯示佇列頁面
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
            showVideoModal(url);
        }}

        /**
         * 開啟設定視窗/模態視窗。
         */
        function openSettings() {{
            showModal("提醒", "設定功能尚未實作");
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
            // 取得影片資訊
            window.pywebview.api.get_video_info(url).then(function(info) {{
                lastVideoInfo = info; // 儲存資訊以供格式變更時使用

                // 畫質選項（由高到低排序）
                var sel = document.getElementById('video-modal-quality');
                sel.innerHTML = '';
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
                    var opt = document.createElement('option');
                    opt.value = q.label;
                    opt.innerText = q.label + (q.ratio ? ' ' + q.ratio : ''); // 顯示畫面比例
                    if (q.label === '1080p') opt.selected = true;
                    sel.appendChild(opt);
                }});

                // 格式選項（mp4和mp3優先）
                var formatSel = document.getElementById('video-modal-format');
                formatSel.innerHTML = '';
                var formats = (info.formats || []).slice();
                formats.sort(function(a, b) {{
                    var priority = {{"影片+音訊": 3, "影片": 2, "音訊": 1}};
                    var pa = priority[a.desc] || 0;
                    var pb = priority[b.desc] || 0;
                    if (pa !== pb) return pb - pa;
                    return a.value.localeCompare(b.value);
                }});
                formats.forEach(function(f) {{
                    var opt = document.createElement('option');
                    opt.value = f.value;
                    opt.innerText = f.label + (f.desc ? ' (' + f.desc + ')' : '');
                    formatSel.appendChild(opt);
                }});

                // 觸發格式變更以正確設定畫質/音訊選項
                onFormatChange();

                // 縮圖處理：如果 info.thumb 不存在或載入失敗，顯示文字
                const thumbElement = document.getElementById('video-modal-thumb');
                if (info.thumb) {{
                    thumbElement.src = info.thumb;
                    thumbElement.style.display = ''; // 顯示圖片
                    thumbElement.alt = "影片縮圖";
                    // 移除可能存在的「找不到縮圖」文字元素
                    const existingNoThumbText = thumbElement.parentNode.querySelector('.video-modal-thumb-text');
                    if (existingNoThumbText) {{
                        existingNoThumbText.remove();
                    }}
                }} else {{
                    thumbElement.src = ''; // 清空圖片源
                    thumbElement.style.display = 'none'; // 隱藏圖片
                    // 檢查是否已存在「找不到縮圖」文字，避免重複添加
                    let noThumbText = thumbElement.parentNode.querySelector('.video-modal-thumb-text');
                    if (!noThumbText) {{
                        noThumbText = document.createElement('div');
                        noThumbText.classList.add('video-modal-thumb-text'); // 添加一個 class 以便識別和移除
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
            }}).catch(function(error) {{
                console.error("獲取影片資訊時出錯:", error);
                showModal('錯誤', '顯示找不到影片，請確認網址是否輸入正確'); // 特定錯誤訊息
                closeVideoModal();
            }});
        }}

        /**
         * 處理影片格式選擇的變更。
         * 根據選擇的影片或音訊格式調整畫質選項。
         */
        function onFormatChange() {{
            const formatSelect = document.getElementById('video-modal-format');
            const qualitySelect = document.getElementById('video-modal-quality');
            const qualityLabel = document.getElementById('video-modal-quality-label');
            const audioTypes = ["mp3", "aac", "flac", "wav"];

            if (audioTypes.includes(formatSelect.value)) {{
                // 如果是音訊格式，顯示音訊品質
                qualitySelect.innerHTML = '';
                AUDIO_QUALITIES.forEach(q => {{
                    const opt = document.createElement('option');
                    opt.value = q.value;
                    opt.innerText = q.label;
                    qualitySelect.appendChild(opt);
                }});
                qualitySelect.value = "320"; // 預設音訊品質
                qualityLabel.innerText = "音質";
            }} else {{
                // 如果是影片格式，從 lastVideoInfo 還原影片畫質
                if (lastVideoInfo && lastVideoInfo.qualities) {{
                    qualitySelect.innerHTML = '';
                    let sortedQualities = sortQualities(lastVideoInfo.qualities);
                    sortedQualities.forEach(q => {{
                        const opt = document.createElement('option');
                        opt.value = q.label;
                        opt.innerText = q.label + (q.ratio ? ' ' + q.ratio : '');
                        qualitySelect.appendChild(opt);
                    }});
                    // 還原原始預設或第一個選項
                    const default1080p = Array.from(qualitySelect.options).find(o => o.value === "1080p");
                    if (default1080p) qualitySelect.value = "1080p";
                    else if (qualitySelect.options.length > 0) qualitySelect.selectedIndex = 0;
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
            const quality = document.getElementById('video-modal-quality').value;
            const format = document.getElementById('video-modal-format').value;

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

        // 首次載入時，確保顯示主頁
        document.addEventListener('DOMContentLoaded', () => {{
            showPage('home');
        }});
    </script>
</body>
</html>
"""

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

class Api:
    def __init__(self, window):
        self.window = window
        self.download_threads = {} # 用於儲存下載執行緒

    def _download_progress_hook(self, d):
        """
        yt-dlp 的進度回調函數。
        將進度更新發送到前端。
        """
        task_id = d['task_id'] # 從下載選項中獲取任務ID
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
            self.window.evaluate_js(f"window.updateDownloadProgress({task_id}, {percent}, '{status}');")
            debug_console(f"任務 {task_id}: {status} {percent:.1f}%")

        elif d['status'] == 'finished':
            # 下載完成
            # yt-dlp 在 finished 狀態下會提供最終檔案路徑
            filepath = d.get('filepath', '')
            if not filepath: # 備用方案，如果 filepath 不存在
                filename = d.get('filename')
                if filename:
                    filepath = os.path.join(ROOT_DIR, 'downloads', filename)
            
            self.window.evaluate_js(f"window.updateDownloadProgress({task_id}, 100, '已完成', '', '{filepath.replace(os.sep, '/')}')") # 將路徑傳遞給前端
            info_console(f"任務 {task_id}: 下載完成 - {d['filename']}")
        elif d['status'] == 'error':
            # 下載錯誤
            self.window.evaluate_js(f"window.updateDownloadProgress({task_id}, 0, '錯誤', '{d.get('error', '未知錯誤')}');")
            error_console(f"任務 {task_id}: 下載錯誤 - {d.get('error', '未知錯誤')}")
        else:
            # 其他狀態
            self.window.evaluate_js(f"window.updateDownloadProgress({task_id}, 0, '{d['status']}');")
            debug_console(f"任務 {task_id}: 狀態 - {d['status']}")


    def download(self, url):
        debug_console(f"下載按鈕被點擊，網址: {url}")
        info_console(f"收到下載請求: {url}")
        return "下載功能尚未實作"

    def open_settings(self):
        debug_console("設定按鈕被點擊")
        info_console("開啟設定視窗（尚未實作）")
        return "設定功能尚未實作"

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
                'format': 'bestvideo+bestaudio/best', # 獲取所有格式以便分析
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

            for f in info_dict.get('formats', []):
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

            info_console(f"成功取得影片資訊: {title}")
            return {
                "title": title,
                "duration": duration,
                "uploader": uploader,
                "thumb": thumb,
                "qualities": qualities,
                "formats": formats
            }
        except Exception as e:
            error_console(f"取得影片資訊時出錯: {e}")
            raise # 重新拋出異常，讓前端的 .catch() 能夠捕獲

    def start_download(self, task_id, url, quality, format_type):
        """
        使用 yt-dlp 開始影片下載，並在單獨的執行緒中運行。
        """
        debug_console(f"接收到下載請求: 任務ID={task_id}, URL={url}, 畫質={quality}, 格式={format_type}")
        
        # 確保下載目錄存在
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
            except Exception:
                height = 1080
            # 讓 yt-dlp 自動選擇最佳影片與音訊並合併為 mp4
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
            ydl_opts['merge_output_format'] = 'mp4'
            postprocessors.append({
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4'
            })
        else:
            # 默認情況，或者處理其他格式
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
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
                error_msg = str(e).replace("'", "\\'");
                self.window.evaluate_js(
                    f"window.updateDownloadProgress({task_id}, 0, '錯誤', '下載失敗: {error_msg}');"
                )

        # 在單獨的執行緒中啟動下載
        download_thread = threading.Thread(target=_download_task);
        download_thread.start();
        self.download_threads[task_id] = download_thread  # 儲存執行緒引用

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

    # 啟動 pywebview 應用
    window = webview.create_window(
        'oldfish影片下載器',
        url=main_html_path,
        width=900,
        height=700, # 調整高度以更好地顯示佇列
        min_size=(700, 600)
    )
    api = Api(window)
    # 修正：將 Api 類別中的方法作為函數公開
    window.expose(api.get_video_info, api.start_download, api.download, api.open_settings, api.open_file_location)
    webview.start(icon=f"{assets_path}/icon.ico")
