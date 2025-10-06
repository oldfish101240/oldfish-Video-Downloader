#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主要 API 類別模組
"""

import os
import sys
import json
import threading
import subprocess
import yt_dlp
from PySide6.QtCore import QObject, Slot, Signal
from utils.logger import debug_console, error_console
from utils.file_utils import safe_path_join
from config.settings import SettingsManager
from core.video_info import extract_video_info
from core.downloader import Downloader

class Api(QObject):
    """主要 API 類別"""
    
    # 信號定義
    eval_js_requested = Signal(str)
    infoReady = Signal('QVariant')
    infoError = Signal(str)
    
    def __init__(self, page, root_dir):
        super().__init__()
        self.page = page
        self.root_dir = root_dir
        self.download_threads = {}
        self.completed_tasks = set()
        self.settings_process = None
        self._lock = threading.Lock()
        self.task_has_postprocessing = {}
        self.task_in_postprocessing = {}
        
        # 初始化組件
        self.settings_manager = SettingsManager(root_dir)
        self.downloader = Downloader(
            root_dir,
            progress_callback=self._download_progress_hook,
            complete_callback=self._notify_download_complete_safely
        )
        
        # 連接信號
        self.eval_js_requested.connect(self._on_eval_js_requested)
    
    @Slot(str, result=str)
    def start_get_video_info(self, url):
        """開始獲取影片資訊"""
        def task():
            try:
                info = extract_video_info(url, self.root_dir)
                if info:
                    self.infoReady.emit(info)
                else:
                    self.infoError.emit("無法獲取影片資訊")
            except Exception as e:
                self.infoError.emit(str(e))
        
        threading.Thread(target=task, daemon=True).start()
        return 'started'
    
    @Slot(str, result='QVariant')
    def get_video_info(self, url):
        """獲取影片資訊"""
        debug_console(f"取得影片資訊: {url}")
        try:
            # 直接使用 yt-dlp 獲取資訊，與原始版本一致
            import yt_dlp
            
            # 設定 FFMPEG 路徑
            ffmpeg_path = os.path.join(self.root_dir, "ffmpeg-7.1.1-essentials_build", "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
            debug_console(f"[API] ffmpeg 路徑: {ffmpeg_path}")
            debug_console(f"[API] ffmpeg 存在: {os.path.exists(ffmpeg_path)}")
            
            # 設定 yt-dlp 選項
            ydl_opts = {
                'quiet': True,
                'simulate': True,
                'format': 'best[height<=1080]/bestaudio/best',
                'ffmpeg_location': ffmpeg_path,
            }
            debug_console(f"[API] yt-dlp 選項: simulate=True, format='best[height<=1080]/bestaudio/best'")
            debug_console("[API] 即將呼叫 yt-dlp.extract_info(download=False)")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
            debug_console("[API] yt-dlp.extract_info 完成")
            
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
            
            uploader = info_dict.get('uploader', '未知上傳者')
            # 縮圖：優先使用 'thumbnail'，否則從 'thumbnails' 陣列中取解析度最高的一張
            thumbnail = info_dict.get('thumbnail') or ''
            if not thumbnail:
                thumbs = info_dict.get('thumbnails') or []
                if isinstance(thumbs, list) and thumbs:
                    try:
                        # 依寬或高度排序取最大
                        best = sorted(thumbs, key=lambda t: max(t.get('width', 0) or 0, t.get('height', 0) or 0))[-1]
                        thumbnail = best.get('url') or ''
                    except Exception:
                        try:
                            thumbnail = thumbs[-1].get('url') or ''
                        except Exception:
                            thumbnail = ''
            debug_console(f"[API] 取得縮圖 URL: {bool(thumbnail)}")
            
            # 處理畫質和格式
            qualities = []
            formats = []
            seen_qualities = set()
            
            for fmt in info_dict.get('formats', []):
                height = fmt.get('height')
                if height and height not in seen_qualities:
                    qualities.append(f"{height}p")
                    seen_qualities.add(height)
            
            # 添加音訊格式
            format_types = ["影片", "音訊"]
            
            return {
                'title': title,
                'duration': duration,
                'uploader': uploader,
                'thumb': thumbnail,  # 使用原始縮圖 URL
                'qualities': qualities,
                'format_types': format_types
            }
            
        except Exception as e:
            debug_console(f"獲取影片資訊失敗: {e}")
            return None
    
    def _eval_js(self, script):
        """執行 JavaScript"""
        self.eval_js_requested.emit(script)
    
    def _safe_eval_js(self, function_name, *args):
        """安全地執行JavaScript函數"""
        try:
            safe_args = []
            for arg in args:
                if isinstance(arg, str):
                    safe_args.append(json.dumps(arg))
                elif isinstance(arg, (int, float)):
                    safe_args.append(str(arg))
                elif arg is None:
                    safe_args.append('null')
                else:
                    safe_args.append(json.dumps(str(arg)))
            
            js_call = f"{function_name}({', '.join(safe_args)})"
            self._eval_js(js_call)
        except Exception as e:
            debug_console(f"安全JavaScript執行失敗: {e}")
            try:
                safe_script = f"{function_name}()"
                self._eval_js(safe_script)
            except Exception as e2:
                debug_console(f"後備JavaScript執行也失敗: {e2}")
    
    @Slot(str)
    def _on_eval_js_requested(self, script):
        """處理 JavaScript 執行請求"""
        try:
            self.page.runJavaScript(script)
        except Exception as e:
            debug_console(f"JavaScript執行失敗: {e}")
    
    def _download_progress_hook(self, task_id, d):
        """下載進度回調"""
        if d['status'] == 'downloading':
            if d.get('total_bytes'):
                percent = d['downloaded_bytes'] / d['total_bytes'] * 100
                status = "下載中"
            elif d.get('total_bytes_estimate'):
                percent = d['downloaded_bytes'] / d['total_bytes_estimate'] * 100
                status = "下載中 (預估)"
            else:
                percent = 0
                status = "下載中 (未知進度)"
            debug_console(f"[進度] 任務{task_id}: {percent:.1f}% - {status}")
            self._safe_eval_js("window.updateDownloadProgress", task_id, percent, status)
        elif d['status'] == 'finished':
            try:
                debug_console(f"[進度] 任務{task_id}: 100.0% - 已完成")
                self._safe_eval_js("window.updateDownloadProgress", task_id, 100, "已完成")
            except Exception as e:
                debug_console(f"完成進度回報失敗: {e}")
    
    def _notify_download_complete_safely(self, task_id, url, error=None):
        """安全地通知下載完成"""
        try:
            with self._lock:
                if task_id in self.completed_tasks:
                    return
                self.completed_tasks.add(task_id)
            
            if error:
                self._safe_eval_js("window.onDownloadError", task_id, error)
            else:
                self._safe_eval_js("window.onDownloadComplete", task_id)
                
                # 發送通知
                settings = self.settings_manager.load_settings()
                if settings.get('enableNotifications', True):
                    self._send_notification("下載完成", f"任務 {task_id} 已完成")
                    
        except Exception as e:
            debug_console(f"通知下載完成失敗: {e}")
    
    @Slot(str, result=str)
    def download(self, url):
        """下載按鈕被點擊"""
        debug_console(f"下載按鈕被點擊，網址: {url}")
        return "下載功能尚未實作"
    
    @Slot(int, str, str, str, result=str)
    def start_download(self, task_id, url, quality, format_type):
        """開始下載"""
        try:
            debug_console(f"開始下載任務 {task_id}: {url}")
            self.downloader.start_download(task_id, url, quality, format_type)
            return "下載已開始"
        except Exception as e:
            error_console(f"開始下載失敗: {e}")
            return f"下載失敗: {e}"
    
    @Slot(str, result=str)
    def cancel_download(self, task_id):
        """取消下載"""
        try:
            self.downloader.cancel_download(task_id)
            return "下載已取消"
        except Exception as e:
            error_console(f"取消下載失敗: {e}")
            return f"取消失敗: {e}"
    
    @Slot(result=str)
    def open_settings(self):
        """開啟設定視窗"""
        debug_console("設定按鈕被點擊")
        try:
            # 檢查是否已經有設定視窗在運行
            if self.settings_process is not None and self.settings_process.poll() is None:
                debug_console("設定視窗已經開啟，嘗試調到該視窗")
                return "設定視窗已經開啟"
            
            settings_script = safe_path_join(self.root_dir, 'settings.pyw')
            if os.path.exists(settings_script):
                self.settings_process = subprocess.Popen([sys.executable, settings_script])
                debug_console("設定視窗已開啟")
                return "設定視窗已開啟"
            else:
                error_console("找不到設定腳本")
                return "找不到設定腳本"
        except Exception as e:
            error_console(f"開啟設定視窗失敗: {e}")
            return f"開啟失敗: {e}"
    
    @Slot()
    def close_settings(self):
        """關閉設定視窗"""
        try:
            if self.settings_process and self.settings_process.poll() is None:
                self.settings_process.terminate()
                debug_console("設定視窗已關閉")
        except Exception as e:
            debug_console(f"關閉設定視窗失敗: {e}")
    
    @Slot(result=dict)
    def load_settings(self):
        """載入設定"""
        return self.settings_manager.load_settings()
    
    @Slot(dict)
    def save_settings(self, settings):
        """儲存設定"""
        self.settings_manager.save_settings(settings)
    
    @Slot(result=dict)
    def reset_to_defaults(self):
        """重設為預設值"""
        return self.settings_manager.reset_to_defaults()
    
    def _send_notification(self, title, message):
        """發送通知"""
        try:
            # 這裡可以實現各種通知方式
            # 目前使用簡單的調試輸出
            debug_console(f"通知: {title} - {message}")
        except Exception as e:
            debug_console(f"發送通知失敗: {e}")
    
    @Slot(result=str)
    def check_ytdlp_version(self):
        """檢查 yt-dlp 版本"""
        try:
            current_version = yt_dlp.version.__version__
            debug_console(f"目前 yt-dlp 版本: {current_version}")
            return current_version
        except Exception as e:
            error_console(f"檢查版本失敗: {e}")
            return "未知版本"
    
    @Slot(result=str)
    def restart_app(self):
        """重啟應用程式"""
        try:
            # 這裡可以實現重啟邏輯
            debug_console("應用程式重啟請求")
            return "重啟功能尚未實現"
        except Exception as e:
            error_console(f"重啟失敗: {e}")
            return f"重啟失敗: {e}"
    
    def check_and_update_ytdlp(self):
        """檢查並更新 yt-dlp"""
        try:
            debug_console("檢查 yt-dlp 版本...")
            current_version = yt_dlp.version.__version__
            debug_console(f"目前版本: {current_version}")
            
            # 這裡可以實現版本檢查和更新邏輯
            # 目前只是簡單的版本檢查
            return current_version
        except Exception as e:
            debug_console(f"版本檢查失敗: {e}")
            return None
