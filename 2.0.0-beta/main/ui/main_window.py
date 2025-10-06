#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主視窗模組
"""

import os
import sys
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon
from core.api import Api
from config.constants import APP_NAME, WINDOW_WIDTH, WINDOW_HEIGHT
from utils.logger import debug_console, info_console, error_console
from utils.file_utils import get_assets_path
from ui.html_content import get_html_content

class MainWindow(QMainWindow):
    """主視窗類別"""
    
    def __init__(self, root_dir):
        super().__init__()
        self.root_dir = root_dir
        self.api_instance = None
        self.init_ui()
    
    def init_ui(self):
        """初始化 UI"""
        self.setWindowTitle(APP_NAME)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        
        # 設定視窗圖示
        icon_path = os.path.join(get_assets_path(self.root_dir), 'icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # 創建 WebEngineView
        self.web_view = QWebEngineView()
        self.setCentralWidget(self.web_view)
        
        # 創建 API 和 WebChannel
        self.api_instance = Api(self.web_view.page(), self.root_dir)
        self.web_channel = QWebChannel()
        self.web_channel.registerObject('api', self.api_instance)
        
        # 將 WebChannel 注入到 WebEngineView
        self.web_view.page().setWebChannel(self.web_channel)
        
        # 載入 HTML 內容
        self.load_html_content()
        
        # 連接信號
        self.api_instance.infoReady.connect(self.on_info_ready)
        self.api_instance.infoError.connect(self.on_info_error)
        
        # 啟動背景版本檢查
        self.start_background_version_check()
    
    def load_html_content(self):
        """載入 HTML 內容"""
        try:
            # 使用 html_content.py 中的邏輯
            html_str = get_html_content()
            info_console(f"載入 HTML 內容，長度: {len(html_str)}")
            
            # 設定基礎 URL
            base_url = QUrl.fromLocalFile(self.root_dir + os.sep)
            self.web_view.setHtml(html_str, base_url)
            
            # 頁面載入完成後執行初始化
            self.web_view.loadFinished.connect(self.on_load_finished)
            
        except Exception as e:
            error_console(f"載入 HTML 內容失敗: {e}")
    
    def on_load_finished(self, ok):
        """頁面載入完成處理"""
        if not ok:
            return
        
        # 注入版本號和樣式
        js = self.get_version_injection_script()
        self.web_view.page().runJavaScript(js)
        # 注入下載完成/錯誤回呼的相容層，對齊舊版命名
        shim_js = r"""
        (function(){
          try {
            // 下載進度即時更新：若 DOM 存在，直接更新目前進度條，否則回退到資料結構
            window.updateDownloadProgress = window.updateDownloadProgress || function(taskId, progress, status, message, filePath){
              try{
                const itemDiv = document.querySelector(`.queue-item[data-task-id="${taskId}"]`);
                if (itemDiv){
                  const bar = itemDiv.querySelector('.progress-bar');
                  const text = itemDiv.querySelector('.progress-text');
                  if (bar) bar.style.width = `${Math.max(0, Math.min(100, Number(progress||0)))}%`;
                  if (text) text.textContent = `${status||'下載中'} (${Number(progress||0).toFixed(1)}%)`;
                }
              }catch(e){ console.error(e); }
            };
            if (typeof window.onDownloadComplete !== 'function') {
              window.onDownloadComplete = function(taskId){
                try { window.updateDownloadProgress && window.updateDownloadProgress(taskId, 100, '已完成'); } catch(e) {}
              };
            }
            if (typeof window.onDownloadError !== 'function') {
              window.onDownloadError = function(taskId, error){
                try { window.updateDownloadProgress && window.updateDownloadProgress(taskId, 0, '錯誤', String(error||'')); } catch(e) {}
              };
            }
          } catch(e) { console.error('inject shims failed', e); }
        })();
        """
        self.web_view.page().runJavaScript(shim_js)
    
    def get_version_injection_script(self):
        """獲取版本注入腳本"""
        from config.constants import APP_VERSION
        
        return f"""
        (function(){{
            try {{
                var styleId = 'of-version-style';
                if (!document.getElementById(styleId)) {{
                    var st = document.createElement('style');
                    st.id = styleId;
                    st.textContent = 
                        ".version-tag{{position:absolute;left:12px;bottom:8px;font-size:12px;color:#888;user-select:none;pointer-events:none;}}" +
                        "body.light-theme .version-tag{{color:#666;}}";
                    document.head.appendChild(st);
                }}

                var mainEl = document.querySelector('.main') || document.body;
                if (mainEl && !document.getElementById('version-tag')) {{
                    var div = document.createElement('div');
                    div.className = 'version-tag';
                    div.id = 'version-tag';
                    div.textContent = '{APP_VERSION}';
                    mainEl.appendChild(div);
                }}

                // 依目前選單狀態設定初始顯示
                var vt = document.getElementById('version-tag');
                if (vt) {{
                    var titleImg = document.getElementById('title-img');
                    var searchRow = document.getElementById('search-row');
                    var visible = (titleImg && titleImg.style.display !== 'none') || (searchRow && searchRow.style.display !== 'none');
                    vt.style.display = visible ? 'block' : 'none';
                }}

                // 包裝 showPage，在頁面切換時同步切換版本號可見性
                if (!window.__ofPatchedShowPage && typeof window.showPage === 'function') {{
                    window.__ofPatchedShowPage = true;
                    var _orig = window.showPage;
                    window.showPage = function(p){{
                        try {{ _orig(p); }} finally {{
                            var vt2 = document.getElementById('version-tag');
                            if (vt2) {{
                                var titleImg2 = document.getElementById('title-img');
                                var searchRow2 = document.getElementById('search-row');
                                var visible2 = (p === 'home') || (titleImg2 && titleImg2.style.display !== 'none') || (searchRow2 && searchRow2.style.display !== 'none');
                                vt2.style.display = visible2 ? 'block' : 'none';
                            }}
                        }}
                    }};
                }}
            }} catch (e) {{
                console.error('inject version failed:', e);
            }}
        }})();
        """
    
    def on_info_ready(self, info):
        """影片資訊準備就緒"""
        try:
            import json
            safe_info = json.dumps(info, ensure_ascii=False)
            self.web_view.page().runJavaScript(
                f"(function(){{ if (window.__onVideoInfo){{ window.__onVideoInfo({safe_info}); }} }})();"
            )
        except Exception as e:
            error_console(f"發送影片資訊失敗: {e}")
    
    def on_info_error(self, error_msg):
        """影片資訊錯誤"""
        try:
            import json
            safe_error = json.dumps(str(error_msg), ensure_ascii=False)
            self.web_view.page().runJavaScript(
                f"(function(){{ if (window.__onVideoInfoError){{ window.__onVideoInfoError({safe_error}); }} }})();"
            )
        except Exception as e:
            error_console(f"發送錯誤資訊失敗: {e}")
    
    def start_background_version_check(self):
        """啟動背景版本檢查"""
        def check_version_in_background():
            try:
                info_console("在背景執行緒中檢查 yt-dlp 版本...")
                self.api_instance.check_and_update_ytdlp()
            except Exception as e:
                error_console(f"背景版本檢查失敗: {e}")
        
        import threading
        version_check_thread = threading.Thread(target=check_version_in_background, daemon=True)
        version_check_thread.start()
    
    def closeEvent(self, event):
        """視窗關閉事件"""
        try:
            info_console("主視窗即將關閉，正在清理資源...")
            if self.api_instance:
                self.api_instance.close_settings()
            event.accept()
        except Exception as e:
            error_console(f"關閉視窗時出錯: {e}")
            event.accept()

def create_app(root_dir):
    """創建應用程式"""
    app = QApplication(sys.argv)
    window = MainWindow(root_dir)
    window.show()
    return app, window


