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
from PySide6.QtWidgets import QFileDialog
from utils.logger import debug_console, info_console, error_console, warning_console
from utils.file_utils import safe_path_join
from utils.version_utils import compare_versions
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
        info_console(f"取得影片資訊: {url}")
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
            error_console(f"獲取影片資訊失敗: {e}")
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
            warning_console(f"安全JavaScript執行失敗: {e}")
            try:
                safe_script = f"{function_name}()"
                self._eval_js(safe_script)
            except Exception as e2:
                warning_console(f"後備JavaScript執行也失敗: {e2}")
    
    @Slot(str)
    def _on_eval_js_requested(self, script):
        """處理 JavaScript 執行請求"""
        try:
            self.page.runJavaScript(script)
        except Exception as e:
            error_console(f"JavaScript執行失敗: {e}")
    
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
            info_console(f"[進度] 任務{task_id}: {percent:.1f}% - {status}")
            # 傳遞當前檔案路徑（若可得）以保持與舊版一致
            file_arg = d.get('filename') or ''
            safe_file_arg = (file_arg or '').replace('\\', '/')
            self._safe_eval_js("window.updateDownloadProgress", task_id, percent, status, '', safe_file_arg)
        elif d['status'] == 'finished':
            try:
                info_console(f"任務 {task_id} 已完成")
                file_arg = d.get('filename') or ''
                safe_file_arg = (file_arg or '').replace('\\', '/')
                self._safe_eval_js("window.updateDownloadProgress", task_id, 100, "已完成", '', safe_file_arg)
            except Exception as e:
                error_console(f"完成進度回報失敗: {e}")
    
    def _notify_download_complete_safely(self, task_id, url, error=None, file_path=None):
        """安全地通知下載完成"""
        try:
            with self._lock:
                if task_id in self.completed_tasks:
                    return
                self.completed_tasks.add(task_id)
            
            if error:
                self._safe_eval_js("window.onDownloadError", task_id, error)
            else:
                # 與舊版一致，將最終檔案路徑傳給前端以啟用「開啟資料夾」按鈕
                safe_file = (file_path or '').replace('\\', '/')
                self._safe_eval_js("window.updateDownloadProgress", task_id, 100, "已完成", '', safe_file)
                self._safe_eval_js("window.onDownloadComplete", task_id)
                
                # 發送通知
                settings = self.settings_manager.load_settings()
                if settings.get('enableNotifications', True):
                    self._send_notification("下載完成", f"任務 {task_id} 已完成")
                    
        except Exception as e:
            warning_console(f"通知下載完成失敗: {e}")

    @Slot(result=str)
    def choose_folder(self):
        """開啟 Windows 檔案總管的資料夾選擇對話方塊，回傳所選路徑（空字串代表取消）"""
        try:
            # 使用原生對話框
            options = QFileDialog.Options()
            # 注意：PySide6 預設會用 native dialog，這裡保持預設即可
            directory = QFileDialog.getExistingDirectory(None, '選擇資料夾', self.root_dir, QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
            if directory:
                return directory
            return ''
        except Exception as e:
            error_console(f"選擇資料夾失敗: {e}")
            return ''
    
    @Slot(str, result=str)
    def download(self, url):
        """下載按鈕被點擊"""
        info_console(f"收到下載請求: {url}")
        return "下載功能尚未實作"
    
    @Slot(int, str, str, str, result=str)
    def start_download(self, task_id, url, quality, format_type):
        """開始下載"""
        try:
            info_console(f"開始下載任務 {task_id}: {url}")
            # 規範化前端傳入的格式與畫質
            fmt = (format_type or '').strip().lower()
            # 對齊下載器分支：將具體副檔名映射為語義分類
            if fmt in ('mp3', 'aac', 'flac', 'wav', 'audio'):
                normalized_format = '音訊'
            else:
                # 預設走影片路徑（包含 mp4、mkv、webm 或未指定時）
                normalized_format = '影片'

            # 將畫質轉為下載器可理解的數值或保留音訊位元率
            q = (quality or '').strip()
            if normalized_format == '影片':
                # 允許 '1080p' 或 '1080'，只取數字
                import re
                m = re.search(r"(\d+)", q)
                normalized_quality = m.group(1) if m else '1080'
            else:
                # 音訊使用位元率數字（例如 '320'）
                import re
                m = re.search(r"(\d+)", q)
                normalized_quality = m.group(1) if m else '320'

            # 讀取設定中的下載路徑和解析度檔名選項
            settings = self.settings_manager.load_settings()
            custom_path = settings.get('customDownloadPath', '')
            add_resolution = settings.get('addResolutionToFilename', False)
            
            # 決定下載目錄
            if custom_path and os.path.exists(custom_path):
                resolved_download_dir = custom_path
                info_console(f"使用自訂下載路徑: {resolved_download_dir}")
            else:
                resolved_download_dir = os.path.join(self.root_dir, 'downloads')
                info_console(f"使用預設下載路徑: {resolved_download_dir}")
            
            try:
                os.makedirs(resolved_download_dir, exist_ok=True)
            except Exception as e:
                error_console(f"創建下載資料夾失敗，改用預設: {e}")
                resolved_download_dir = os.path.join(self.root_dir, 'downloads')
                os.makedirs(resolved_download_dir, exist_ok=True)

            self.downloader.start_download(task_id, url, normalized_quality, normalized_format, 
                                         downloads_dir=resolved_download_dir, 
                                         add_resolution_to_filename=add_resolution)
            return "下載已開始"
        except Exception as e:
            error_console(f"開始下載失敗: {e}")
            return f"下載失敗: {e}"

    @Slot(str, result=str)
    def open_file_location(self, file_path):
        """開啟檔案所在資料夾（支援 Windows）"""
        try:
            if not file_path or not file_path.strip():
                return "檔案路徑不可用"
            
            # 統一分隔符並清理路徑
            fp = str(file_path).strip().replace('/', os.sep)
            
            # 驗證檔案路徑安全性
            if not os.path.isabs(fp):
                fp = os.path.abspath(fp)
            
            # 檢查路徑是否在允許的範圍內（防止目錄遍歷攻擊）
            if not fp.startswith(self.root_dir) and not fp.startswith(os.path.expanduser("~")):
                return "檔案路徑不在允許範圍內"
            
            if os.path.exists(fp):
                # 在 Windows 上使用 explorer /select,
                if sys.platform.startswith('win'):
                    import subprocess
                    # 使用引號包圍路徑以防止特殊字符問題
                    escaped_path = f'"{fp}"'
                    subprocess.Popen(["explorer", "/select,", escaped_path])
                    return "已開啟檔案位置"
                else:
                    # 其他平台開啟所在資料夾
                    folder = os.path.dirname(fp)
                    import subprocess
                    subprocess.Popen(["xdg-open", folder])
                    return "已開啟資料夾"
            return "檔案不存在"
        except Exception as e:
            error_console(f"開啟檔案位置失敗: {e}")
            return f"失敗: {e}"
    
    @Slot(str, result=str)
    def open_external_link(self, url):
        """使用系統預設瀏覽器開啟外部連結"""
        try:
            if not url or not url.strip():
                return "連結不可用"
            
            url = url.strip()
            
            # 驗證URL格式
            import re
            url_pattern = re.compile(
                r'^https?://'  # http:// 或 https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # 域名
                r'localhost|'  # localhost
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP地址
                r'(?::\d+)?'  # 可選端口
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            
            # 確保 URL 格式正確
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # 驗證URL格式
            if not url_pattern.match(url):
                return "無效的URL格式"
            
            # 使用系統預設瀏覽器開啟
            if sys.platform.startswith('win'):
                subprocess.Popen(['cmd', '/c', 'start', '', url], 
                               creationflags=subprocess.CREATE_NO_WINDOW)
            elif sys.platform.startswith('darwin'):  # macOS
                subprocess.Popen(['open', url])
            else:  # Linux 和其他 Unix-like 系統
                subprocess.Popen(['xdg-open', url])
            
            info_console(f"已開啟外部連結: {url}")
            return "已開啟外部連結"
        except Exception as e:
            error_console(f"開啟外部連結失敗: {e}")
            return f"失敗: {e}"
    
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
        info_console("開啟設定視窗")
        try:
            # 檢查是否已經有設定視窗在運行
            if self.settings_process is not None and self.settings_process.poll() is None:
                info_console("設定視窗已經開啟，嘗試調到該視窗")
                return "設定視窗已經開啟"
            
            settings_script = safe_path_join(self.root_dir, 'settings.pyw')
            if os.path.exists(settings_script):
                self.settings_process = subprocess.Popen([sys.executable, settings_script])
                info_console("設定視窗已開啟")
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
                info_console("設定視窗已關閉")
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
        """檢查 yt-dlp 版本，並在 debug 中顯示目前與線上最新版本"""
        try:
            import urllib.request, json, time, os
            
            current_version = yt_dlp.version.__version__
            debug_console(f"目前 yt-dlp 版本: {current_version}")
            
            # 檢查快取檔案
            cache_file = os.path.join(self.root_dir, 'main', 'ytdlp_version_cache.json')
            latest = None
            
            # 檢查快取是否有效（24小時內）
            cache_valid = False
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    cache_time = cache_data.get('timestamp', 0)
                    cache_version = cache_data.get('version', '')
                    
                    # 檢查快取是否在24小時內且版本不為空
                    if (time.time() - cache_time < 86400) and cache_version:
                        latest = cache_version
                        cache_valid = True
                        debug_console(f"使用快取的版本資訊: {latest}")
                except Exception as e:
                    debug_console(f"讀取版本快取失敗: {e}")
            
            # 如果快取無效，從網路獲取
            if not cache_valid:
                try:
                    # 減少超時時間到5秒
                    with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=5) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        latest = data.get('info', {}).get('version') or ''
                    
                    # 儲存到快取
                    try:
                        cache_data = {
                            'version': latest,
                            'timestamp': time.time()
                        }
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(cache_data, f, ensure_ascii=False, indent=2)
                        debug_console(f"版本資訊已快取: {latest}")
                    except Exception as e:
                        debug_console(f"儲存版本快取失敗: {e}")
                        
                except Exception as e:
                    debug_console(f"網路版本檢查失敗: {e}")
                    # 如果網路失敗但有舊快取，使用舊快取
                    if os.path.exists(cache_file):
                        try:
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                cache_data = json.load(f)
                            latest = cache_data.get('version', '')
                            debug_console(f"使用舊快取版本: {latest}")
                        except Exception:
                            pass
            
            if latest:
                debug_console(f"偵測到的最新 yt-dlp 版本: {latest}")
            else:
                debug_console("無法取得最新 yt-dlp 版本")
            
            return current_version
        except Exception as e:
            error_console(f"檢查版本失敗: {e}")
            return "未知版本"
    
    @Slot(result=str)
    def restart_app(self):
        """重啟應用程式（舊版等價：優先重啟打包 exe，否則重啟腳本）"""
        try:
            debug_console("應用程式重啟請求")
            # 嘗試啟動同一資料夾上一層的 exe
            exe_path = os.path.normpath(os.path.join(self.root_dir, os.pardir, 'oldfish影片下載器.exe'))
            started = False
            try:
                if os.path.exists(exe_path):
                    debug_console(f"嘗試啟動 exe: {exe_path}")
                    try:
                        si = None
                        flags = 0
                        if sys.platform.startswith('win'):
                            si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW; si.wShowWindow = 0
                            flags |= getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                        subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path), startupinfo=si, creationflags=flags)
                    except Exception:
                        subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path))
                    started = True
            except Exception as e:
                debug_console(f"啟動 exe 失敗: {e}")

            if not started:
                # 退而求其次：重啟目前 Python 腳本（優先使用內嵌 pythonw，若無則 python.exe，最後使用目前解譯器）
                pyw = os.path.normpath(os.path.join(self.root_dir, 'main.pyw'))
                embed_dir = os.path.normpath(os.path.join(self.root_dir, 'python_embed'))
                pythonw = os.path.normpath(os.path.join(embed_dir, 'pythonw.exe'))
                python = os.path.normpath(os.path.join(embed_dir, 'python.exe'))
                candidates = []
                if os.path.isfile(pythonw):
                    candidates.append(pythonw)
                if os.path.isfile(python):
                    candidates.append(python)
                # 最後退回目前執行中的解譯器
                candidates.append(os.path.normpath(sys.executable))
                try:
                    for exe in candidates:
                        try:
                            exe_path = os.path.normpath(exe)
                            script_path = os.path.normpath(pyw)
                            # 額外檢查：檔案存在且大小合理，避免誤選無效檔
                            if not (os.path.isfile(exe_path) and os.path.isfile(script_path)):
                                continue
                            try:
                                size_ok = os.path.getsize(exe_path) > 1024 * 50
                            except Exception:
                                size_ok = True
                            if not size_ok:
                                debug_console(f"跳過過小的可執行檔: {exe_path}")
                                continue
                            debug_console(f"嘗試以解譯器啟動: {exe_path} {script_path}")
                            try:
                                si = None
                                flags = 0
                                if sys.platform.startswith('win'):
                                    si = subprocess.STARTUPINFO(); si.dwFlags |= subprocess.STARTF_USESHOWWINDOW; si.wShowWindow = 0
                                    flags |= getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                                subprocess.Popen([exe_path, script_path], cwd=os.path.dirname(script_path), startupinfo=si, creationflags=flags)
                            except Exception:
                                subprocess.Popen([exe_path, script_path], cwd=os.path.dirname(script_path))
                            started = True
                            break
                        except Exception as inner_e:
                            debug_console(f"嘗試使用 {exe} 重啟失敗: {inner_e}")
                except Exception as e:
                    debug_console(f"啟動內嵌解譯器失敗: {e}")

            # 關閉目前應用
            try:
                from PySide6.QtWidgets import QApplication
                if started:
                    QApplication.quit()
                    return "正在重啟"
                else:
                    # 未能啟動新程序，只回報訊息
                    return "未找到可重啟目標，請手動重新啟動。"
            except Exception as e:
                error_console(f"結束目前應用失敗: {e}")
                return "重啟流程已嘗試，請確認是否已開啟新視窗。"
        except Exception as e:
            error_console(f"重啟失敗: {e}")
            return f"重啟失敗: {e}"

    @Slot()
    def restartApp(self):
        """為相容舊版 JS 呼叫名稱，轉呼叫 restart_app"""
        try:
            self.restart_app()
        except Exception as e:
            error_console(f"restartApp 失敗: {e}")
    
    @Slot()
    def test_update_dialog(self):
        """測試更新對話框顯示（用於調試）"""
        try:
            debug_console("測試更新對話框...")
            version_info = {
                'update_available': True,
                'current_version': '2023.12.30',
                'latest_version': '2024.01.15'
            }
            self.show_update_dialog(version_info)
            return "測試對話框已觸發"
        except Exception as e:
            error_console(f"測試更新對話框失敗: {e}")
            return f"測試失敗: {e}"
    
    def check_and_update_ytdlp(self):
        """檢查 yt-dlp 是否需要更新；若有新版本則彈出與舊版一致的更新對話框"""
        try:
            import urllib.request, json, time, os
            
            # 檢查快取檔案
            cache_file = os.path.join(self.root_dir, 'main', 'ytdlp_version_cache.json')
            current_version = yt_dlp.version.__version__
            latest = None
            
            # 檢查快取是否有效（24小時內）
            cache_valid = False
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    cache_time = cache_data.get('timestamp', 0)
                    cache_version = cache_data.get('version', '')
                    
                    # 檢查快取是否在24小時內且版本不為空
                    if (time.time() - cache_time < 86400) and cache_version:
                        latest = cache_version
                        cache_valid = True
                        debug_console(f"使用快取的版本資訊: {latest}")
                except Exception as e:
                    debug_console(f"讀取版本快取失敗: {e}")
            
            # 如果快取無效，從網路獲取
            if not cache_valid:
                debug_console("檢查 yt-dlp 版本...")
                try:
                    # 減少超時時間到5秒
                    with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=5) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        latest = data.get('info', {}).get('version') or ''
                    
                    # 儲存到快取
                    try:
                        cache_data = {
                            'version': latest,
                            'timestamp': time.time()
                        }
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(cache_data, f, ensure_ascii=False, indent=2)
                        debug_console(f"版本資訊已快取: {latest}")
                    except Exception as e:
                        debug_console(f"儲存版本快取失敗: {e}")
                        
                except Exception as e:
                    debug_console(f"網路版本檢查失敗: {e}")
                    # 如果網路失敗但有舊快取，使用舊快取
                    if os.path.exists(cache_file):
                        try:
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                cache_data = json.load(f)
                            latest = cache_data.get('version', '')
                            debug_console(f"使用舊快取版本: {latest}")
                        except Exception:
                            pass
            
            debug_console(f"目前版本: {current_version}")
            if latest:
                debug_console(f"偵測到的最新版本: {latest}")
                try:
                    needs_update = compare_versions(current_version, latest) < 0
                except Exception:
                    needs_update = False
                if needs_update:
                    version_info = {
                        'update_available': True,
                        'current_version': current_version,
                        'latest_version': latest
                    }
                    self.show_update_dialog(version_info)
            return current_version
        except Exception as e:
            debug_console(f"版本檢查失敗: {e}")
            return None

    @Slot(result='QVariant')
    def check_ytdlp_update_detail(self):
        """回傳是否需要更新的詳細資訊（對齊舊版資料結構）"""
        try:
            import urllib.request, json, time, os
            
            # 檢查快取檔案
            cache_file = os.path.join(self.root_dir, 'main', 'ytdlp_version_cache.json')
            current_version = yt_dlp.version.__version__
            latest_version = None
            
            # 檢查快取是否有效（24小時內）
            cache_valid = False
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    cache_time = cache_data.get('timestamp', 0)
                    cache_version = cache_data.get('version', '')
                    
                    # 檢查快取是否在24小時內且版本不為空
                    if (time.time() - cache_time < 86400) and cache_version:
                        latest_version = cache_version
                        cache_valid = True
                except Exception as e:
                    debug_console(f"讀取版本快取失敗: {e}")
            
            # 如果快取無效，從網路獲取
            if not cache_valid:
                try:
                    # 減少超時時間到5秒
                    with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=5) as resp:
                        data = json.loads(resp.read().decode('utf-8'))
                        latest_version = data.get('info', {}).get('version') or ''
                    
                    # 儲存到快取
                    try:
                        cache_data = {
                            'version': latest_version,
                            'timestamp': time.time()
                        }
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(cache_data, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        debug_console(f"儲存版本快取失敗: {e}")
                        
                except Exception as e:
                    debug_console(f"網路版本檢查失敗: {e}")
                    # 如果網路失敗但有舊快取，使用舊快取
                    if os.path.exists(cache_file):
                        try:
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                cache_data = json.load(f)
                            latest_version = cache_data.get('version', '')
                        except Exception:
                            pass
            
            if latest_version:
                if compare_versions(current_version, latest_version) < 0:
                    return {
                        'update_available': True,
                        'current_version': current_version,
                        'latest_version': latest_version
                    }
                return {
                    'update_available': False,
                    'current_version': current_version,
                    'latest_version': latest_version
                }
            return None
        except Exception as e:
            debug_console(f"檢查版本細節失敗: {e}")
            return None

    @Slot()
    def startYtDlpUpdate(self):
        """由前端呼叫，啟動 yt-dlp 更新（背景執行並回報進度）——對齊舊版行為"""
        def run_update():
            try:
                self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(0, '開始更新…');")
                # 選擇 python 執行檔：優先內嵌，否則使用目前執行環境
                python_exe = safe_path_join(self.root_dir, 'python_embed', 'python.exe')
                if not os.path.exists(python_exe):
                    python_exe = sys.executable
                cmd = [python_exe, '-m', 'pip', 'install', '--upgrade', 'yt-dlp', '--disable-pip-version-check']
                debug_console(f"執行更新命令: {' '.join(cmd)}")
                # 在 Windows 隱藏 console 啟動 pip 更新
                si = None
                flags = 0
                if sys.platform.startswith('win'):
                    try:
                        si = subprocess.STARTUPINFO()
                        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        si.wShowWindow = 0
                        flags |= getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                    except Exception:
                        si = None
                with subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    startupinfo=si,
                    creationflags=flags,
                ) as proc:
                    import time
                    progress = 3
                    last_emit = 0.0
                    for line in proc.stdout:
                        ln = (line or '').strip()
                        if not ln:
                            continue
                        lower = ln.lower()
                        if 'collecting' in lower or 'downloading' in lower:
                            self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(undefined, '正在下載套件…');")
                            progress = max(progress, 10)
                        elif 'installing collected packages' in lower:
                            self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(undefined, '正在安裝…');")
                            progress = max(progress, 60)
                        elif 'successfully installed' in lower or 'already satisfied' in lower:
                            progress = max(progress, 95)
                        now = time.time()
                        if now - last_emit > 0.2:
                            progress = min(progress + 1, 97)
                            self._eval_js(f"window.__ofUpdateProgress && window.__ofUpdateProgress({progress}, undefined);")
                            last_emit = now
                    ret = proc.wait()
                    if ret == 0:
                        self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(100, '更新完成');")
                        self._eval_js("window.__ofUpdateDone && window.__ofUpdateDone(true, 'yt-dlp 已成功更新到最新版本！');")
                    else:
                        self._eval_js("window.__ofUpdateDone && window.__ofUpdateDone(false, 'yt-dlp 更新失敗，請稍後再試或手動更新。');")
            except Exception as e:
                error_console(f"更新執行失敗: {e}")
                safe_msg = str(e).replace('\\', '/')
                self._eval_js(f"window.__ofUpdateDone && window.__ofUpdateDone(false, '更新過程發生錯誤：{safe_msg}');")
        threading.Thread(target=run_update, daemon=True).start()

    def show_update_dialog(self, version_info):
        """顯示更新對話框（完全對齊舊版樣式與互動）"""
        try:
            # 注入舊版的進度對話與完成對話
            update_js = """
            window.__executeUpdate = function() {
                const progressOverlay = document.createElement('div');
                progressOverlay.id = 'update-progress-overlay';
                progressOverlay.style.cssText = `position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.7); z-index: 10001; display: flex; align-items: center; justify-content: center; font-family: 'Segoe UI', Arial, sans-serif;`;
                const progressDialog = document.createElement('div');
                progressDialog.style.cssText = `background: #23262f; border-radius: 16px; padding: 32px; max-width: 380px; width: 90%; box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3); border: 1px solid #444; text-align: center;`;
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
                window.__ofUpdateProgress = function(percent, tipText){
                    try { if (typeof percent === 'number') { const el = document.getElementById('of-update-bar'); if (el) el.style.width = Math.max(0, Math.min(100, percent)) + '%'; } if (typeof tipText === 'string') { const t = document.getElementById('of-update-tip'); if (t) t.textContent = tipText; } } catch(_){ }
                };
                window.__ofUpdateDone = function(success, message){
                    try { document.getElementById('update-progress-overlay')?.remove(); } catch(_){ }
                    const overlay = document.createElement('div');
                    overlay.id = 'update-success-overlay';
                    overlay.style.cssText = `position:fixed; inset:0; background:rgba(0,0,0,.7); z-index:10002; display:flex; align-items:center; justify-content:center; font-family:'Segoe UI',Arial,sans-serif;`;
                    const dialog = document.createElement('div');
                    dialog.style.cssText = `background:#23262f; border-radius:16px; padding:32px; max-width:420px; width:90%; box-shadow:0 4px 24px rgba(0,0,0,.3); border:1px solid #444; text-align:center;`;
                    const badge = document.createElement('div');
                    badge.style.cssText = `width:68px; height:68px; border-radius:50%; margin:0 auto 16px auto; display:flex; align-items:center; justify-content:center; box-shadow:0 0 8px ${success?"#27ae60":"#c0392b"}; background:${success?"#2ecc71":"#e74c3c"}; color:#fff; font-size:28px;`;
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
                    if (success) { const restartBtn = document.createElement('button'); restartBtn.textContent = '立即重啟'; restartBtn.style.cssText = 'background:#27ae60; color:#fff; border:none; padding:10px 20px; border-radius:8px; cursor:pointer; font-size:14px; font-weight:bold;'; restartBtn.onclick = ()=> { try { window.api.restartApp(); } catch(_){} }; btnRow.appendChild(restartBtn); }
                    dialog.appendChild(badge); dialog.appendChild(title); dialog.appendChild(text); if (success) dialog.appendChild(hint); dialog.appendChild(btnRow);
                    overlay.appendChild(dialog); document.body.appendChild(overlay);
                };
                try { window.api.startYtDlpUpdate(); } catch (e) { console.error(e); }
            };
            """
            self._eval_js(update_js)

            # 再注入舊版對話框，帶入具體版本號
            current_version = version_info.get('current_version', '')
            latest_version = version_info.get('latest_version', '')
            dialog_html = """
            (function() {
                const overlay = document.createElement('div');
                overlay.id = 'update-dialog-overlay';
                overlay.style.cssText = `position: fixed; top:0; left:0; width:100%; height:100%; background: rgba(0, 0, 0, 0.7); z-index: 10000; display: flex; align-items: center; justify-content: center; font-family: 'Segoe UI', Arial, sans-serif;`;
                const dialog = document.createElement('div');
                dialog.id = 'update-dialog';
                dialog.style.cssText = `background: #23262f; border-radius: 16px; padding: 32px; max-width: 420px; width: 90%; box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3); border: 1px solid #444;`;
                const titleDiv = document.createElement('div');
                titleDiv.style.cssText = `display: flex; align-items: center; margin-bottom: 16px;`;
                const iconDiv = document.createElement('div');
                iconDiv.style.cssText = `width: 48px; height: 48px; background: #2ecc71; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 16px; box-shadow: 0 0 6px #27ae60;`;
                iconDiv.innerHTML = '<img src="assets/update.png" alt="update" style="width:24px;height:24px;object-fit:contain;filter:brightness(1);">';
                const title = document.createElement('h3');
                title.style.cssText = `margin: 0; color: #e5e7eb; font-size: 20px; font-weight: bold;`;
                title.textContent = 'yt-dlp 更新提醒';
                titleDiv.appendChild(iconDiv); titleDiv.appendChild(title);
                const desc = document.createElement('p');
                desc.style.cssText = `color: #e5e7eb; margin: 0 0 24px 0; line-height: 1.5; font-size: 16px; font-weight: 600;`;
                desc.textContent = '發現 yt-dlp 新版本！';
                const versionDiv = document.createElement('div');
                versionDiv.style.cssText = `background: #181a20; border-radius: 12px; padding: 18px; margin-bottom: 24px; border: 1px solid #444;`;
                const currentVersionDiv = document.createElement('div');
                currentVersionDiv.style.cssText = 'margin-bottom: 12px;';
                currentVersionDiv.innerHTML = `<span style=\"color: #aaa; font-size: 15px;\">目前版本:</span> <span style=\"color: #e5e7eb; font-weight: 500; margin-left: 12px;\">__CURR__</span>`;
                const latestVersionDiv = document.createElement('div');
                latestVersionDiv.innerHTML = `<span style=\"color: #aaa; font-size: 15px;\">最新版本:</span> <span style=\"color: #2ecc71; font-weight: 500; margin-left: 12px;\">__LATEST__</span>`;
                versionDiv.appendChild(currentVersionDiv); versionDiv.appendChild(latestVersionDiv);
                const question = document.createElement('p');
                question.style.cssText = `color: #e5e7eb; margin: 16px 0 8px 0; font-size: 15px; font-weight: 600;`;
                question.textContent = '是否要更新到最新版本？';
                const actionsRow = document.createElement('div');
                actionsRow.style.cssText = `display: flex; align-items: center; justify-content: flex-start; gap: 16px; margin: 0 0 8px 0;`;
                const note = document.createElement('p');
                note.style.cssText = `color: #888; margin: 0; font-size: 12px; line-height: 1.4; font-style: italic; flex: 1;`;
                note.textContent = '※yt-dlp為下載器的重要核心元件，建議更新以避免錯誤及獲得更好的使用體驗';
                const buttonDiv = document.createElement('div');
                buttonDiv.style.cssText = `display: flex; gap: 16px; justify-content: flex-end; margin: 0 0 24px 0;`;
                const skipBtn = document.createElement('button');
                skipBtn.id = 'skip-update-btn';
                skipBtn.style.cssText = `background: #23262f; color: #e5e7eb; border: 1px solid #444; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 15px; font-weight: 500; transition: all 0.2s ease;`;
                skipBtn.textContent = '稍後提醒';
                skipBtn.onmouseover = function(){ this.style.background = '#2b2e37'; this.style.borderColor = '#2ecc71'; };
                skipBtn.onmouseout = function(){ this.style.background = '#23262f'; this.style.borderColor = '#444'; };
                const updateBtn = document.createElement('button');
                updateBtn.id = 'update-now-btn';
                updateBtn.style.cssText = `background: #27ae60; color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 15px; font-weight: bold; transition: all 0.2s ease; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);`;
                updateBtn.textContent = '立即更新';
                updateBtn.onmouseover = function(){ this.style.background = '#219150'; this.style.transform = 'scale(1.03)'; this.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.3)'; };
                updateBtn.onmouseout = function(){ this.style.background = '#27ae60'; this.style.transform = 'scale(1)'; this.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.2)'; };
                buttonDiv.appendChild(skipBtn); buttonDiv.appendChild(updateBtn);
                actionsRow.appendChild(note);
                dialog.appendChild(titleDiv); dialog.appendChild(desc); dialog.appendChild(versionDiv); dialog.appendChild(question); dialog.appendChild(actionsRow); dialog.appendChild(buttonDiv);
                overlay.appendChild(dialog); document.body.appendChild(overlay);
                updateBtn.addEventListener('click', function(){ overlay.remove(); window.__executeUpdate(); });
                skipBtn.addEventListener('click', function(){ overlay.remove(); });
                overlay.addEventListener('click', function(e){ if (e.target === this) { this.remove(); if (window.__onUpdateDialogResult) { window.__onUpdateDialogResult('skip'); } } });
            })();
            """
            dialog_html = dialog_html.replace("__CURR__", str(current_version).replace('\\', '/')).replace("__LATEST__", str(latest_version).replace('\\', '/'))
            self._eval_js(dialog_html)
            return "update"
        except Exception as e:
            debug_console(f"注入更新對話框失敗: {e}")
