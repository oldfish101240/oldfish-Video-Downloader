#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主要 API 類別模組
"""

print("api.py is starting...")

import os
import sys
import json
import threading
import subprocess
import yt_dlp

# 添加父目錄到路徑，以便導入其他模組
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # main/scripts
root_dir = os.path.dirname(parent_dir)  # main
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from PySide6.QtCore import QObject, Slot, Signal
from PySide6.QtWidgets import QFileDialog
from scripts.utils.logger import api_console, download_console, video_info_console, LogLevel
from scripts.utils.file_utils import safe_path_join, get_download_path, resolve_relative_path, get_deno_path
from scripts.utils.version_utils import compare_versions
from scripts.config.settings import SettingsManager
from .video_info import extract_video_info, is_playlist_url, extract_playlist_info, get_video_qualities_and_formats
from .downloader import Downloader, DownloadScheduler

class Api(QObject):
    """主要 API 類別"""
    
    # 信號定義
    eval_js_requested = Signal(str)
    infoReady = Signal('QVariant')
    infoError = Signal(str)
    notificationRequested = Signal(str, str)
    updateDialogRequested = Signal('QVariant')  # 更新對話框請求信號
    
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
        self.task_download_paths = {}  # 追蹤每個任務的下載路徑
        self.notification_handler = None
        self._last_progress_percent = {}
        
        # 初始化組件
        self.settings_manager = SettingsManager(root_dir)
        self.downloader = Downloader(
            root_dir,
            progress_callback=self._download_progress_hook,
            complete_callback=self._notify_download_complete_safely
        )

        # 全域下載排程器：同時下載上限/重試次數（先用設定或預設值）
        try:
            settings = self.settings_manager.load_settings()
            max_c = int(settings.get('maxConcurrentDownloads', 3) or 3)
        except Exception:
            max_c = 3
        self.scheduler = DownloadScheduler(
            self.downloader,
            max_concurrent=max_c,
            retry_count=3,
            status_callback=self._scheduler_status_update,
        )
        
        # 連接信號
        self.eval_js_requested.connect(self._on_eval_js_requested)
        self.notificationRequested.connect(self._on_notification_requested)
        self.updateDialogRequested.connect(self._on_update_dialog_requested)
    def set_notification_handler(self, handler):
        """設定通知處理器，由主視窗提供"""
        self.notification_handler = handler
    
    def _format_eta(self, eta_seconds):
        """格式化 ETA（預估剩餘時間）"""
        try:
            if eta_seconds is None or eta_seconds < 0:
                return ''
            
            eta_seconds = int(eta_seconds)
            
            if eta_seconds < 60:
                return f"{eta_seconds}秒"
            elif eta_seconds < 3600:
                minutes = eta_seconds // 60
                seconds = eta_seconds % 60
                if seconds > 0:
                    return f"{minutes}分{seconds}秒"
                else:
                    return f"{minutes}分鐘"
            else:
                hours = eta_seconds // 3600
                minutes = (eta_seconds % 3600) // 60
                if minutes > 0:
                    return f"{hours}小時{minutes}分鐘"
                else:
                    return f"{hours}小時"
        except Exception:
            return ''

    
    @Slot(str, result=str)
    def start_get_video_info(self, url):
        """開始獲取影片資訊（自動檢測播放清單）"""
        def task():
            try:
                api_console(f"start_get_video_info 被調用，URL: {url}")
                # 檢測是否為播放清單
                if is_playlist_url(url):
                    api_console("檢測到播放清單URL", level=LogLevel.INFO)
                    api_console(f"確認為播放清單URL，開始提取...")
                    playlist_info = extract_playlist_info(url, self.root_dir)
                    api_console(f"播放清單資訊提取完成，結果: {playlist_info is not None}")
                    if playlist_info:
                        api_console(f"播放清單資訊結構: is_playlist={playlist_info.get('is_playlist')}, video_count={playlist_info.get('video_count')}")
                        api_console(f"準備發送 infoReady 信號...")
                        self.infoReady.emit(playlist_info)
                        api_console(f"infoReady 信號已發送")
                    else:
                        api_console(f"播放清單資訊為 None，發送錯誤信號")
                        self.infoError.emit("無法獲取播放清單資訊")
                else:
                    api_console(f"不是播放清單URL，按單個影片處理")
                    info = extract_video_info(url, self.root_dir)
                    if info:
                        api_console(f"影片資訊提取完成，發送 infoReady 信號")
                        self.infoReady.emit(info)
                    else:
                        api_console(f"影片資訊為 None，發送錯誤信號")
                        self.infoError.emit("無法獲取影片資訊")
            except Exception as e:
                api_console(f"start_get_video_info 發生異常: {e}", level=LogLevel.ERROR)
                api_console(f"異常詳情: {type(e).__name__}: {str(e)}")
                import traceback
                api_console(f"完整堆疊:\n{traceback.format_exc()}")
                self.infoError.emit(str(e))
        
        api_console(f"啟動背景執行緒處理 URL: {url}")
        threading.Thread(target=task, daemon=True).start()
        return 'started'
    
    @Slot(str, result='QVariant')
    def get_playlist_info(self, url):
        """獲取播放清單資訊"""
        try:
            api_console(f"獲取播放清單資訊: {url}", level=LogLevel.INFO)
            playlist_info = extract_playlist_info(url, self.root_dir)
            return playlist_info
        except Exception as e:
            api_console(f"獲取播放清單資訊失敗: {e}", level=LogLevel.ERROR)
            return None
    
    @Slot(str, result='QVariant')
    def get_video_qualities_formats(self, url):
        """獲取單個影片的畫質和格式選項（用於播放清單）"""
        try:
            return get_video_qualities_and_formats(url, self.root_dir)
        except Exception as e:
            api_console(f"獲取影片畫質和格式失敗: {e}", level=LogLevel.ERROR)
            return {
                'qualities': [{'label': '1080p', 'ratio': ''}, {'label': '720p', 'ratio': ''}, {'label': '480p', 'ratio': ''}],
                'formats': [{'value': 'mp4', 'label': 'mp4', 'desc': '影片'}, {'value': 'mp3', 'label': 'mp3', 'desc': '音訊'}]
            }

    @Slot(str, result=str)
    def start_playlist_qualities_fetch(self, videos_json):
        """播放清單：背景逐支提取每部影片可用畫質（eager）。

        videos_json: JSON字串，格式：
          [
            {"index": 0, "url": "https://..."},
            ...
          ]

        會逐支回推前端：
          window.__onPlaylistVideoQualities(index, qualitiesArray)
        """
        try:
            items = json.loads(videos_json or '[]')
            if not isinstance(items, list):
                return "FAILED: invalid payload"

            # 受控併發，避免同時開太多 yt-dlp extract_info
            max_concurrent = 4
            sem = threading.Semaphore(max_concurrent)

            def worker(idx, url):
                if url is None:
                    return
                u = str(url).strip()
                if not u:
                    return
                sem.acquire()
                try:
                    result = get_video_qualities_and_formats(u, self.root_dir) or {}
                    qualities = result.get('qualities') or []
                    # 用 JS 物件回推（_safe_eval_js 會把 list 轉成字串，不適合）
                    payload = json.dumps(qualities, ensure_ascii=False)
                    js = f"(function(){{ try{{ if (window.__onPlaylistVideoQualities){{ window.__onPlaylistVideoQualities({int(idx)}, {payload}); }} }}catch(e){{ console.error(e); }} }})();"
                    self._eval_js(js)
                except Exception as e:
                    # 失敗時回推空陣列（前端可維持預設）
                    try:
                        js = f"(function(){{ try{{ if (window.__onPlaylistVideoQualities){{ window.__onPlaylistVideoQualities({int(idx)}, []); }} }}catch(e){{}} }})();"
                        self._eval_js(js)
                    except Exception:
                        pass
                    video_info_console(f"提取畫質失敗 idx={idx}: {e}", level=LogLevel.ERROR)
                finally:
                    try:
                        sem.release()
                    except Exception:
                        pass

            started = 0
            for it in items:
                if not isinstance(it, dict):
                    continue
                idx = it.get('index')
                url = it.get('url')
                if idx is None or url is None:
                    continue
                t = threading.Thread(target=worker, args=(idx, url), daemon=True)
                t.start()
                started += 1

            return f"OK:{started}"
        except Exception as e:
            api_console(f"start_playlist_qualities_fetch 失敗: {e}", level=LogLevel.ERROR)
            return f"FAILED:{e}"
    
    @Slot(str, result='QVariant')
    def get_video_info(self, url):
        """獲取影片資訊"""
        api_console(f"取得影片資訊: {url}", level=LogLevel.INFO)
        try:
            # 直接使用 yt-dlp 獲取資訊，與原始版本一致
            import yt_dlp
            
            # 設定 FFMPEG 路徑（使用相對路徑）
            ffmpeg_path = safe_path_join(self.root_dir, "lib", "ffmpeg-7.1.1-essentials_build", "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
            api_console(f"ffmpeg 路徑: {ffmpeg_path}")
            api_console(f"ffmpeg 存在: {os.path.exists(ffmpeg_path)}")
            
            # 設定 yt-dlp 選項（不限制格式，以獲取所有可用格式）
            ydl_opts = {
                'quiet': False,  # 改為 False 以查看警告信息
                'simulate': True,
                'skip_download': True,
                'no_playlist': True,  # 確保只提取單個視頻
                # 不設定 format，以獲取所有可用格式
            }
            
            # 設定 ffmpeg 路徑（如果存在）
            if os.path.exists(ffmpeg_path):
                ydl_opts['ffmpeg_location'] = ffmpeg_path
            
            # 配置 Deno 作為外部 JavaScript 執行時（用於 YouTube 支援）
            deno_path = get_deno_path(self.root_dir)
            api_console(f"Deno 路徑查找結果: {deno_path}")
            if deno_path and os.path.exists(deno_path):
                ydl_opts['js_runtimes'] = {'deno': {'path': deno_path}}
                api_console(f"已配置 Deno 路徑: {deno_path}")
                api_console(f"js_runtimes 配置: {ydl_opts.get('js_runtimes')}")
            else:
                api_console(f"Deno 未找到或不存在: {deno_path}")
                if deno_path:
                    api_console(f"Deno 路徑存在性檢查: {os.path.exists(deno_path)}")
            
            api_console(f"yt-dlp 選項: simulate=True")
            api_console("即將呼叫 yt-dlp.extract_info(download=False)")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
            api_console("yt-dlp.extract_info 完成")
            
            # 詳細調試信息
            api_console(f"info_dict 類型: {type(info_dict)}")
            api_console(f"info_dict 鍵: {list(info_dict.keys())[:10] if isinstance(info_dict, dict) else 'N/A'}")
            
            # 檢查是否成功獲取格式列表
            formats_list = info_dict.get('formats', [])
            formats_count = len(formats_list)
            api_console(f"獲取到 {formats_count} 個格式")
            
            if formats_count == 0:
                api_console("警告：未獲取到任何格式，可能是 JavaScript runtime 配置問題", level=LogLevel.WARNING)
                # 打印 info_dict 的部分內容以便調試
                api_console(f"info_dict 部分內容: title={info_dict.get('title', 'N/A')}, id={info_dict.get('id', 'N/A')}")
            else:
                # 打印前幾個格式的詳細信息
                api_console(f"前 5 個格式的詳細信息:")
                for i, fmt in enumerate(formats_list[:5]):
                    fmt_id = fmt.get('format_id', 'N/A')
                    height = fmt.get('height', 'N/A')
                    width = fmt.get('width', 'N/A')
                    ext = fmt.get('ext', 'N/A')
                    vcodec = fmt.get('vcodec', 'N/A')
                    acodec = fmt.get('acodec', 'N/A')
                    api_console(f"  格式 {i+1}: id={fmt_id}, height={height}, width={width}, ext={ext}, vcodec={vcodec}, acodec={acodec}")
            
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
            api_console(f"取得縮圖 URL: {bool(thumbnail)}")
            
            # 處理畫質和格式（使用與 extract_video_info 相同的邏輯）
            seen_heights = set()
            qualities = []
            
            def _quality_label_from_height(h):
                """高度轉為大眾常見畫質"""
                try:
                    h_int = int(h)
                except Exception:
                    return f"{h}p"
                if h_int >= 4320:
                    return "4320p(8K)"
                if h_int >= 2160:
                    return "2160p(4K)"
                if h_int >= 1440:
                    return "1440p(2K)"
                if h_int >= 1080:
                    return "1080p"
                if h_int >= 720:
                    return "720p"
                if h_int >= 480:
                    return "480p"
                return "360p"
            
            # 從 formats 中提取畫質
            api_console(f"開始提取畫質，formats_list 長度: {len(formats_list)}")
            
            # 打印所有格式的詳細信息
            api_console(f"所有格式的詳細信息:")
            for i, fmt in enumerate(formats_list):
                fmt_id = fmt.get('format_id', 'N/A')
                height = fmt.get('height', 'N/A')
                width = fmt.get('width', 'N/A')
                ext = fmt.get('ext', 'N/A')
                vcodec = fmt.get('vcodec', 'N/A')
                acodec = fmt.get('acodec', 'N/A')
                api_console(f"  格式 {i+1}: id={fmt_id}, height={height}, width={width}, ext={ext}, vcodec={vcodec}, acodec={acodec}")
            
            height_count = 0
            filtered_count = 0
            mhtml_count = 0
            for fmt in formats_list:
                ext = fmt.get('ext', '').lower()
                # 過濾掉縮圖格式（mhtml）
                if ext == 'mhtml':
                    mhtml_count += 1
                    api_console(f"  跳過縮圖格式: {fmt.get('format_id', 'N/A')} (ext=mhtml)")
                    continue
                
                height = fmt.get('height')
                vcodec = fmt.get('vcodec', 'none')
                # 只處理有視頻編碼的格式（vcodec != 'none'）
                if vcodec == 'none':
                    api_console(f"  跳過無視頻編碼格式: {fmt.get('format_id', 'N/A')} (vcodec=none)")
                    continue
                
                if height is not None:
                    height_count += 1
                    api_console(f"  處理視頻格式: height={height}, vcodec={vcodec}, ext={ext}")
                    # 過濾掉低於360p的畫質選項
                    if height >= 360 and height not in seen_heights:
                        label = _quality_label_from_height(height)
                        qualities.append({'label': label, 'ratio': ''})
                        seen_heights.add(height)
                        filtered_count += 1
                        api_console(f"  添加畫質: {label} (原始高度: {height})")
                    elif height < 360:
                        api_console(f"  跳過低畫質: {height}p (低於360p)")
                    else:
                        api_console(f"  跳過重複畫質: {height}p")
                else:
                    api_console(f"  跳過無高度格式: {fmt.get('format_id', 'N/A')} (height=None)")
            
            api_console(f"畫質提取統計: 總格式數={len(formats_list)}, 縮圖格式={mhtml_count}, 有高度的視頻格式={height_count}, 過濾後畫質數={filtered_count}")
            
            # 由高到低排序
            qualities.sort(key=lambda q: int(''.join(ch for ch in q['label'] if ch.isdigit()) or '0'), reverse=True)
            api_console(f"最終提取到 {len(qualities)} 個畫質選項: {[q['label'] for q in qualities]}")
            
            # 格式：與 extract_video_info 一致
            has_any_audio = any((f.get('acodec') and f.get('acodec') != 'none') for f in formats_list)
            formats_out = [{'value': 'mp4', 'label': 'mp4', 'desc': '影片'}]
            if has_any_audio:
                formats_out.append({'value': 'mp3', 'label': 'mp3', 'desc': '音訊'})
            
            result = {
                'title': title,
                'duration': duration,
                'uploader': uploader,
                'thumb': thumbnail,  # 使用原始縮圖 URL
                'qualities': qualities,
                'formats': formats_out
            }
            
            api_console(f"返回結果: title={title}, qualities數量={len(qualities)}, formats數量={len(formats_out)}")
            api_console(f"返回的畫質列表: {[q['label'] for q in qualities]}")
            
            return result
            
        except Exception as e:
            api_console(f"獲取影片資訊失敗: {e}", level=LogLevel.ERROR)
            import traceback
            api_console(f"錯誤堆疊: {traceback.format_exc()}")
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
            api_console(f"安全JavaScript執行失敗: {e}", level=LogLevel.WARNING)
            try:
                safe_script = f"{function_name}()"
                self._eval_js(safe_script)
            except Exception as e2:
                api_console(f"後備JavaScript執行也失敗: {e2}", level=LogLevel.WARNING)
    
    @Slot(str)
    def _on_eval_js_requested(self, script):
        """處理 JavaScript 執行請求"""
        try:
            self.page.runJavaScript(script)
        except Exception as e:
            api_console(f"JavaScript執行失敗: {e}", level=LogLevel.ERROR)
    
    def _on_update_dialog_requested(self, version_info):
        """處理更新對話框請求（在主線程中執行）"""
        try:
            # 使用 QTimer 延遲執行，確保頁面加載完成
            from PySide6.QtCore import QTimer
            def show_dialog():
                self.show_update_dialog(version_info)
                current_version = version_info.get('current_version', '')
                latest_version = version_info.get('latest_version', '')
                api_console(f"已顯示 yt-dlp 更新對話框（目前版本: {current_version}, 最新版本: {latest_version}）", level=LogLevel.INFO)
            QTimer.singleShot(500, show_dialog)  # 500ms 後執行
        except Exception as e:
            api_console(f"顯示更新對話框失敗: {e}", level=LogLevel.ERROR)
    
    def _download_progress_hook(self, task_id, d):
        """下載進度回調"""
        try:
            status_key = d.get('status')
            if not status_key:
                download_console(f"【任務{task_id}】進度回調缺少 status 欄位")
                return
            
            if status_key == 'downloading':
                downloaded_bytes = d.get('downloaded_bytes', 0)
                
                # 計算進度百分比
                if d.get('total_bytes'):
                    total_bytes = d['total_bytes']
                    if total_bytes > 0:
                        percent = min(100, max(0, downloaded_bytes / total_bytes * 100))
                        status = "下載中"
                    else:
                        percent = 0
                        status = "下載中 (未知進度)"
                elif d.get('total_bytes_estimate'):
                    total_bytes_estimate = d['total_bytes_estimate']
                    if total_bytes_estimate > 0:
                        percent = min(100, max(0, downloaded_bytes / total_bytes_estimate * 100))
                        status = "下載中 (預估)"
                    else:
                        percent = 0
                        status = "下載中 (未知進度)"
                else:
                    percent = 0
                    status = "下載中 (未知進度)"
                
                # 提取並格式化 ETA（預估剩餘時間）
                eta = d.get('eta')
                if eta is not None and isinstance(eta, (int, float)) and eta >= 0:
                    eta_str = self._format_eta(eta)
                    if eta_str:
                        status = f"{status} - 剩餘 {eta_str}"
                
                download_console(f"[進度] 任務{task_id}: {percent:.1f}% - {status}", level=LogLevel.INFO)
                try:
                    with self._lock:
                        self._last_progress_percent[str(task_id)] = float(percent)
                except Exception:
                    pass
                # 傳遞當前檔案路徑（若可得）以保持與舊版一致
                file_arg = d.get('filename') or ''
                safe_file_arg = (file_arg or '').replace('\\', '/')
                # 傳遞 status（已包含 ETA）給前端
                self._safe_eval_js("window.updateDownloadProgress", task_id, percent, status, '', safe_file_arg)
            elif status_key == 'finished':
                try:
                    download_console(f"任務 {task_id} 已完成", level=LogLevel.INFO)
                    file_arg = d.get('filename') or ''
                    safe_file_arg = (file_arg or '').replace('\\', '/')
                    self._safe_eval_js("window.updateDownloadProgress", task_id, 100, "已完成", '', safe_file_arg)
                except Exception as e:
                    download_console(f"完成進度回報失敗: {e}", level=LogLevel.ERROR)
            else:
                # 處理其他未知狀態
                download_console(f"【任務{task_id}】未知狀態: {status_key}")
        except KeyError as e:
            download_console(f"【任務{task_id}】進度回調缺少必要欄位: {e}", level=LogLevel.ERROR)
        except Exception as e:
            download_console(f"【任務{task_id}】進度回調處理失敗: {e}", level=LogLevel.ERROR)

    def _scheduler_status_update(self, task_id, status_text):
        """排程器狀態更新（例如重試中），只更新狀態文字，不重置進度條。"""
        try:
            with self._lock:
                p = self._last_progress_percent.get(str(task_id), 0.0)
            self._safe_eval_js("window.updateDownloadProgress", int(task_id), float(p), str(status_text), '', '')
        except Exception:
            pass
    
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
                # 記錄最終檔案路徑到任務追蹤中
                if file_path:
                    with self._lock:
                        self.task_download_paths[str(task_id)] = file_path
                    download_console(f"任務 {task_id} 最終檔案路徑已記錄: {file_path}")
                
                # 與舊版一致，將最終檔案路徑傳給前端以啟用「開啟資料夾」按鈕
                safe_file = (file_path or '').replace('\\', '/')
                self._safe_eval_js("window.updateDownloadProgress", task_id, 100, "已完成", '', safe_file)
                self._safe_eval_js("window.onDownloadComplete", task_id)
                
                # 發送通知
                settings = self.settings_manager.load_settings()
                if settings.get('enableNotifications', True):
                    try:
                        self._safe_eval_js("window.__ofShowToast", "下載完成", f"任務 {task_id} 已完成")
                    except Exception as toast_err:
                        download_console(f"顯示 Toast 失敗: {toast_err}")
                    self._send_notification("下載完成", f"任務 {task_id} 已完成")
                    
        except Exception as e:
            download_console(f"通知下載完成失敗: {e}", level=LogLevel.WARNING)

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
            api_console(f"選擇資料夾失敗: {e}", level=LogLevel.ERROR)
            return ''
    
    @Slot(str, result=str)
    def download(self, url):
        """下載按鈕被點擊"""
        download_console(f"收到下載請求: {url}", level=LogLevel.INFO)
        return "下載功能尚未實作"
    
    def _check_file_exists(self, url, quality, format_type, downloads_dir, add_resolution):
        """檢查目標文件是否存在，返回文件路徑（如果存在）"""
        try:
            # 先獲取視頻信息以確定標題和高度
            import yt_dlp
            ffmpeg_path = safe_path_join(self.root_dir, "lib", "ffmpeg-7.1.1-essentials_build", "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
            ydl_opts = {
                'quiet': True,
                'simulate': True,
                'extract_flat': False,
            }
            
            # 設定 ffmpeg 路徑（如果存在）
            if os.path.exists(ffmpeg_path):
                ydl_opts['ffmpeg_location'] = ffmpeg_path
            
            # 配置 Deno 作為外部 JavaScript 執行時（用於 YouTube 支援）
            deno_path = get_deno_path(self.root_dir)
            if deno_path:
                ydl_opts['js_runtimes'] = {'deno': {'path': deno_path}}
                api_console(f"已配置 Deno 路徑: {deno_path}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
            
            title = info_dict.get('title', '無標題影片')
            # 清理標題中的非法字符
            import re
            safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
            
            # 規範化格式和畫質
            fmt = (format_type or '').strip().lower()
            if fmt in ('mp3', 'aac', 'flac', 'wav', 'audio'):
                normalized_format = '音訊'
                ext = 'mp3'
            else:
                normalized_format = '影片'
                ext = 'mp4'
            
            q = (quality or '').strip()
            import re as re_module
            m = re_module.search(r"(\d+)", q)
            qnum = m.group(1) if m else ('320' if normalized_format == '音訊' else '1080')
            
            # 構建可能的文件名列表（因為 yt-dlp 可能會使用不同的格式）
            possible_files = []
            
            # 獲取實際高度（用於影片）
            height = None
            if normalized_format == '影片':
                formats = info_dict.get('formats', [])
                for f in formats:
                    h = f.get('height')
                    if h and h >= int(qnum):
                        height = h
                        break
                if not height:
                    height = qnum
            
            # 根據設定構建可能的文件名
            if add_resolution:
                if normalized_format == '音訊':
                    # 音訊格式：標題_320kbps.mp3
                    possible_files.append(f"{safe_title}_{qnum}kbps.{ext}")
                else:
                    # 影片格式：標題_1080p.mp4
                    possible_files.append(f"{safe_title}_{height}p.{ext}")
            else:
                # 預設格式：標題.mp4
                possible_files.append(f"{safe_title}.{ext}")
            
            # 檢查文件是否存在（包括不同的擴展名）
            for filename in possible_files:
                file_path = os.path.join(downloads_dir, filename)
                if os.path.exists(file_path):
                    return file_path
            
            # 也檢查其他可能的擴展名（mp4, mkv, webm等）
            if normalized_format == '影片':
                for ext_alt in ['mp4', 'mkv', 'webm', 'flv']:
                    if add_resolution:
                        alt_path = os.path.join(downloads_dir, f"{safe_title}_{height}p.{ext_alt}")
                    else:
                        alt_path = os.path.join(downloads_dir, f"{safe_title}.{ext_alt}")
                    if os.path.exists(alt_path):
                        return alt_path
            
            return None
        except Exception as e:
            api_console(f"檢查文件是否存在時出錯: {e}")
            return None
    
    @Slot(str, result=str)
    def start_batch_download(self, video_data_json):
        """批量下載（主要給播放清單使用）
        video_data_json: JSON字串，格式：
          [
            { "id": 123, "url": "...", "quality": "1080p", "format": "mp4" },
            ...
          ]

        - **重要**：`id` 會直接當作任務ID回報進度/完成，必須與前端佇列對齊。
        """
        try:
            video_list = json.loads(video_data_json or '[]')
            if not isinstance(video_list, list):
                return "批量下載失敗: 參數格式錯誤（需為 JSON 陣列）"

            download_console(f"開始批量下載，共 {len(video_list)} 部影片", level=LogLevel.INFO)

            def delayed_start(delay_s, tid, u, q, f):
                import time
                try:
                    if delay_s and delay_s > 0:
                        time.sleep(delay_s)
                    # 直接使用前端提供的 task id（不可亂轉換，避免對不到 UI）
                    self.start_download(int(tid), u, q, f)
                except Exception as e:
                    download_console(f"批量下載啟動失敗(task_id={tid}): {e}", level=LogLevel.ERROR)
                    try:
                        self._notify_download_complete_safely(int(tid), u, error=str(e))
                    except Exception:
                        pass

            started = 0
            for idx, item in enumerate(video_list):
                if not isinstance(item, dict):
                    continue
                url = (item.get('url') or '').strip()
                if not url:
                    continue
                task_id = item.get('id')
                if task_id is None:
                    # 若前端未提供，退回用序號（仍維持 int）
                    task_id = idx
                quality = item.get('quality', '1080p')
                format_type = item.get('format', 'mp4')

                # 以背景執行緒做簡單排程，避免一次啟動太多 yt-dlp 實例
                t = threading.Thread(
                    target=delayed_start,
                    args=(idx * 0.5, task_id, url, quality, format_type),
                    daemon=True,
                )
                t.start()
                started += 1

            return f"已開始批量下載 {started} 部影片"
        except Exception as e:
            download_console(f"批量下載失敗: {e}", level=LogLevel.ERROR)
            return f"批量下載失敗: {e}"
    
    @Slot(int, str, str, str, result=str)
    def start_download(self, task_id, url, quality, format_type):
        """開始下載"""
        try:
            download_console(f"開始下載任務 {task_id}: {url}", level=LogLevel.INFO)
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
            resolved_download_dir = get_download_path(self.root_dir, self.settings_manager)
            download_console(f"使用下載路徑: {resolved_download_dir}", level=LogLevel.INFO)
            
            try:
                os.makedirs(resolved_download_dir, exist_ok=True)
            except Exception as e:
                download_console(f"創建下載資料夾失敗，改用預設: {e}", level=LogLevel.ERROR)
                resolved_download_dir = safe_path_join(self.root_dir, 'downloads')
                os.makedirs(resolved_download_dir, exist_ok=True)

            # 檢查文件是否已存在
            existing_file = self._check_file_exists(url, normalized_quality, normalized_format, 
                                                   resolved_download_dir, add_resolution)
            if existing_file:
                # 文件已存在，返回特殊狀態讓前端顯示確認對話框
                download_console(f"發現已存在的文件: {existing_file}")
                # 將信息存儲在臨時變量中，等待用戶確認
                with self._lock:
                    if not hasattr(self, '_pending_downloads'):
                        self._pending_downloads = {}
                    self._pending_downloads[str(task_id)] = {
                        'url': url,
                        'quality': normalized_quality,
                        'format': normalized_format,
                        'original_format': fmt,  # 保留原始格式（如 mp3, mp4）
                        'downloads_dir': resolved_download_dir,
                        'add_resolution': add_resolution,
                        'existing_file': existing_file
                    }
                return f"FILE_EXISTS:{existing_file}"

            # 記錄任務的下載路徑
            with self._lock:
                self.task_download_paths[str(task_id)] = resolved_download_dir
            
            download_console(f"任務 {task_id} 下載路徑已記錄: {resolved_download_dir}")

            # 丟給全域排程器（控制同時下載上限 + 重試）
            self.scheduler.submit(
                task_id,
                url,
                normalized_quality,
                normalized_format,
                downloads_dir=resolved_download_dir,
                add_resolution_to_filename=add_resolution,
                original_format=fmt,
            )
            return "已加入下載佇列"
        except Exception as e:
            download_console(f"開始下載失敗: {e}", level=LogLevel.ERROR)
            return f"下載失敗: {e}"
    
    @Slot(int, bool, result=str)
    def confirm_redownload(self, task_id, should_delete):
        """確認是否重新下載（刪除舊文件）"""
        try:
            with self._lock:
                if not hasattr(self, '_pending_downloads'):
                    return "沒有待處理的下載任務"
                
                pending = self._pending_downloads.get(str(task_id))
                if not pending:
                    return "找不到待處理的下載任務"
                
                url = pending['url']
                normalized_quality = pending['quality']
                normalized_format = pending['format']
                original_format = pending.get('original_format', None)  # 獲取原始格式
                resolved_download_dir = pending['downloads_dir']
                add_resolution = pending['add_resolution']
                existing_file = pending['existing_file']
                
                # 如果用戶確認刪除，刪除舊文件
                if should_delete:
                    try:
                        if os.path.exists(existing_file):
                            os.remove(existing_file)
                            download_console(f"已刪除舊文件: {existing_file}", level=LogLevel.INFO)
                    except Exception as e:
                        download_console(f"刪除舊文件失敗: {e}", level=LogLevel.ERROR)
                        return f"刪除舊文件失敗: {e}"
                else:
                    # 用戶取消，移除待處理任務
                    del self._pending_downloads[str(task_id)]
                    return "已取消下載"
                
                # 記錄任務的下載路徑
                self.task_download_paths[str(task_id)] = resolved_download_dir
                
                # 開始下載，傳遞原始格式
                self.scheduler.submit(
                    task_id,
                    url,
                    normalized_quality,
                    normalized_format,
                    downloads_dir=resolved_download_dir,
                    add_resolution_to_filename=add_resolution,
                    original_format=original_format,
                )
                
                # 移除待處理任務
                del self._pending_downloads[str(task_id)]
                
                return "已加入下載佇列"
        except Exception as e:
            download_console(f"確認重新下載失敗: {e}", level=LogLevel.ERROR)
            return f"失敗: {e}"

    @Slot(int, result=str)
    def open_file_location_by_task(self, task_id):
        """根據任務ID開啟檔案所在資料夾"""
        try:
            if task_id is None:
                return "任務ID不可用"
            
            task_key = str(task_id).strip()
            if not task_key:
                return "任務ID不可用"
            
            # 從任務追蹤中獲取檔案路徑
            with self._lock:
                file_path = self.task_download_paths.get(task_key)
            
            if not file_path:
                return f"找不到任務 {task_key} 的檔案路徑"
            
            download_console(f"任務 {task_id} 的檔案路徑: {file_path}")
            
            # 檢查檔案是否存在
            if os.path.exists(file_path):
                # 在 Windows 上使用 explorer /select,
                if sys.platform.startswith('win'):
                    import subprocess
                    try:
                        if os.path.isdir(file_path):
                            # 如果是資料夾，直接開啟
                            subprocess.Popen(["explorer", file_path], 
                                           creationflags=subprocess.CREATE_NO_WINDOW)
                        else:
                            # 如果是檔案，使用 /select, 選中檔案
                            # 注意：/select, 後面必須緊跟路徑，不能有空格
                            # 使用絕對路徑並確保路徑正確
                            abs_path = os.path.abspath(file_path)
                            # 使用 shell=True 確保命令正確執行
                            subprocess.Popen(f'explorer /select,"{abs_path}"', 
                                           shell=True,
                                           creationflags=subprocess.CREATE_NO_WINDOW)
                        api_console(f"已執行 explorer 命令開啟: {file_path}")
                        return "已開啟檔案位置"
                    except Exception as e:
                        api_console(f"開啟檔案位置失敗: {e}", level=LogLevel.ERROR)
                        # 嘗試開啟所在資料夾
                        try:
                            folder = os.path.dirname(file_path)
                            subprocess.Popen(["explorer", folder], 
                                           creationflags=subprocess.CREATE_NO_WINDOW)
                            return "已開啟資料夾"
                        except Exception as e2:
                            api_console(f"開啟資料夾也失敗: {e2}", level=LogLevel.ERROR)
                            return f"開啟失敗: {e2}"
                else:
                    # 其他平台開啟所在資料夾
                    folder = os.path.dirname(file_path)
                    import subprocess
                    subprocess.Popen(["xdg-open", folder])
                    return "已開啟資料夾"
            else:
                # 檔案不存在，嘗試開啟所在資料夾
                folder = os.path.dirname(file_path)
                if os.path.exists(folder):
                    if sys.platform.startswith('win'):
                        import subprocess
                        subprocess.Popen(["explorer", folder], 
                                       creationflags=subprocess.CREATE_NO_WINDOW)
                        return "檔案不存在，已開啟所在資料夾"
                    else:
                        import subprocess
                        subprocess.Popen(["xdg-open", folder])
                        return "檔案不存在，已開啟所在資料夾"
                return f"檔案不存在: {file_path}"
                
        except Exception as e:
            api_console(f"根據任務ID開啟檔案位置失敗: {e}", level=LogLevel.ERROR)
            return f"失敗: {e}"

    @Slot(str, result=str)
    def open_file_location(self, file_path):
        """開啟檔案所在資料夾（支援 Windows）"""
        try:
            if not file_path or not file_path.strip():
                return "檔案路徑不可用"
            
            # 統一分隔符並清理路徑
            fp = str(file_path).strip().replace('/', os.sep)
            
            # 如果檔案路徑是相對路徑，嘗試在設定檔的下載路徑中尋找
            if not os.path.isabs(fp):
                # 獲取設定檔中的自訂下載路徑
                settings = self.settings_manager.load_settings()
                custom_path = settings.get('customDownloadPath', '')
                
                # 優先使用設定檔中的路徑
                if custom_path and os.path.exists(custom_path):
                    # 在自訂路徑中尋找檔案
                    custom_file_path = os.path.join(custom_path, fp)
                    if os.path.exists(custom_file_path):
                        fp = custom_file_path
                        download_console(f"在自訂路徑中找到檔案: {fp}")
                    else:
                        # 如果自訂路徑中找不到，嘗試預設下載路徑
                        default_file_path = os.path.join(self.root_dir, 'downloads', fp)
                        if os.path.exists(default_file_path):
                            fp = default_file_path
                            download_console(f"在預設路徑中找到檔案: {fp}")
                        else:
                            # 最後嘗試相對於根目錄的路徑
                            fp = os.path.join(self.root_dir, fp)
                else:
                    # 如果沒有自訂路徑，嘗試預設下載路徑
                    default_file_path = os.path.join(self.root_dir, 'downloads', fp)
                    if os.path.exists(default_file_path):
                        fp = default_file_path
                        download_console(f"在預設路徑中找到檔案: {fp}")
                    else:
                        # 最後嘗試相對於根目錄的路徑
                        fp = os.path.join(self.root_dir, fp)
            else:
                # 絕對路徑，檢查是否在允許範圍內
                if not fp.startswith(self.root_dir) and not fp.startswith(os.path.expanduser("~")):
                    return "檔案路徑不在允許範圍內"
            
            # 確保路徑是絕對路徑
            if not os.path.isabs(fp):
                fp = os.path.abspath(fp)
            
            if os.path.exists(fp):
                # 在 Windows 上使用 explorer /select,
                if sys.platform.startswith('win'):
                    import subprocess
                    # 直接傳遞路徑給 explorer，由 subprocess 處理跳脫
                    subprocess.Popen(["explorer", "/select,", fp])
                    return "已開啟檔案位置"
                else:
                    # 其他平台開啟所在資料夾
                    folder = os.path.dirname(fp)
                    import subprocess
                    subprocess.Popen(["xdg-open", folder])
                    return "已開啟資料夾"
            return "檔案不存在"
        except Exception as e:
            api_console(f"開啟檔案位置失敗: {e}", level=LogLevel.ERROR)
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
            
            api_console(f"已開啟外部連結: {url}", level=LogLevel.INFO)
            return "已開啟外部連結"
        except Exception as e:
            api_console(f"開啟外部連結失敗: {e}", level=LogLevel.ERROR)
            return f"失敗: {e}"
    
    @Slot(str, result=str)
    def cancel_download(self, task_id):
        """取消下載"""
        try:
            self.downloader.cancel_download(task_id)
            return "下載已取消"
        except Exception as e:
            download_console(f"取消下載失敗: {e}", level=LogLevel.ERROR)
            return f"取消失敗: {e}"
    
    @Slot(result=str)
    def open_settings(self):
        """開啟設定視窗"""
        api_console("開啟設定視窗", level=LogLevel.INFO)
        try:
            # 檢查是否已經有設定視窗在運行
            if self.settings_process is not None and self.settings_process.poll() is None:
                api_console("設定視窗已經開啟，嘗試調到該視窗", level=LogLevel.INFO)
                return "設定視窗已經開啟"
            
            settings_script = safe_path_join(self.root_dir, 'settings.pyw')
            if os.path.exists(settings_script):
                self.settings_process = subprocess.Popen([sys.executable, settings_script])
                api_console("設定視窗已開啟", level=LogLevel.INFO)
                return "設定視窗已開啟"
            else:
                api_console("找不到設定腳本", level=LogLevel.ERROR)
                return "找不到設定腳本"
        except Exception as e:
            api_console(f"開啟設定視窗失敗: {e}", level=LogLevel.ERROR)
            return f"開啟失敗: {e}"
    
    @Slot()
    def close_settings(self):
        """關閉設定視窗"""
        try:
            if self.settings_process and self.settings_process.poll() is None:
                self.settings_process.terminate()
                api_console("設定視窗已關閉", level=LogLevel.INFO)
        except Exception as e:
            api_console(f"關閉設定視窗失敗: {e}")
    
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
            self.notificationRequested.emit(title or '', message or '')
        except Exception as e:
            api_console(f"發送通知失敗: {e}")

    def _on_notification_requested(self, title, message):
        """在主執行緒處理通知"""
        try:
            if callable(self.notification_handler):
                self.notification_handler(title or '', message or '')
            else:
                api_console(f"通知: {title} - {message}")
        except Exception as e:
            api_console(f"通知處理失敗: {e}")
    
    @Slot(result=str)
    def check_ytdlp_version(self):
        """檢查 yt-dlp 版本，並在 debug 中顯示目前與線上最新版本"""
        try:
            import urllib.request, json, time, os
            
            current_version = yt_dlp.version.__version__
            api_console(f"目前 yt-dlp 版本: {current_version}")
            
            # 檢查快取檔案
            cache_file = safe_path_join(self.root_dir, 'main', 'ytdlp_version_cache.json')
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
                        api_console(f"使用快取的版本資訊: {latest}")
                except Exception as e:
                    api_console(f"讀取版本快取失敗: {e}")
            
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
                        api_console(f"版本資訊已快取: {latest}")
                    except Exception as e:
                        api_console(f"儲存版本快取失敗: {e}")
                        
                except Exception as e:
                    api_console(f"網路版本檢查失敗: {e}")
                    # 如果網路失敗但有舊快取，使用舊快取
                    if os.path.exists(cache_file):
                        try:
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                cache_data = json.load(f)
                            latest = cache_data.get('version', '')
                            api_console(f"使用舊快取版本: {latest}")
                        except Exception:
                            pass
            
            if latest:
                api_console(f"偵測到的最新 yt-dlp 版本: {latest}")
            else:
                api_console("無法取得最新 yt-dlp 版本")
            
            return current_version
        except Exception as e:
            api_console(f"檢查版本失敗: {e}", level=LogLevel.ERROR)
            return "未知版本"
    
    @Slot(result=str)
    def refresh_version(self):
        """重新整理版本號顯示"""
        try:
            # 動態重新導入模組以獲取最新版本號
            import importlib
            import config.constants
            importlib.reload(config.constants)
            from config.constants import APP_VERSION, APP_VERSION_HOME
            
            # 更新版本號顯示
            version_script = f"""
            (function(){{
                try {{
                    window.__APP_VERSION = '{APP_VERSION}';
                    window.__APP_VERSION_HOME = '{APP_VERSION_HOME}';
                    
                    var versionTag = document.getElementById('version-tag');
                    if (versionTag) {{
                        versionTag.textContent = '{APP_VERSION_HOME}';
                    }}
                    
                    var aboutVersion = document.getElementById('about-version');
                    if (aboutVersion) {{
                        aboutVersion.textContent = '{APP_VERSION}';
                    }}
                }} catch(e) {{
                    console.error('更新版本號失敗:', e);
                }}
            }})();
            """
            
            self._eval_js(version_script)
            return f"版本號已更新為: {APP_VERSION_HOME}"
        except Exception as e:
            api_console(f"重新整理版本號失敗: {e}", level=LogLevel.ERROR)
            return f"更新失敗: {e}"

    @Slot(result=str)
    def restart_app(self):
        """重啟應用程式（舊版等價：優先重啟打包 exe，否則重啟腳本）"""
        try:
            api_console("應用程式重啟請求")
            # 嘗試啟動同一資料夾上一層的 exe
            exe_path = os.path.normpath(os.path.join(self.root_dir, os.pardir, 'oldfish影片下載器.exe'))
            started = False
            try:
                if os.path.exists(exe_path):
                    api_console(f"嘗試啟動 exe: {exe_path}")
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
                api_console(f"啟動 exe 失敗: {e}")

            if not started:
                # 退而求其次：重啟目前 Python 腳本（優先使用內嵌 pythonw，若無則 python.exe，最後使用目前解譯器）
                pyw = safe_path_join(self.root_dir, 'main.pyw')
                embed_dir = safe_path_join(self.root_dir, 'lib', 'python_embed')
                pythonw = safe_path_join(embed_dir, 'pythonw.exe')
                python = safe_path_join(embed_dir, 'python.exe')
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
                                api_console(f"跳過過小的可執行檔: {exe_path}")
                                continue
                            api_console(f"嘗試以解譯器啟動: {exe_path} {script_path}")
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
                            api_console(f"嘗試使用 {exe} 重啟失敗: {inner_e}")
                except Exception as e:
                    api_console(f"啟動內嵌解譯器失敗: {e}")

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
                api_console(f"結束目前應用失敗: {e}", level=LogLevel.ERROR)
                return "重啟流程已嘗試，請確認是否已開啟新視窗。"
        except Exception as e:
            api_console(f"重啟失敗: {e}", level=LogLevel.ERROR)
            return f"重啟失敗: {e}"

    @Slot()
    def restartApp(self):
        """為相容舊版 JS 呼叫名稱，轉呼叫 restart_app"""
        try:
            self.restart_app()
        except Exception as e:
            api_console(f"restartApp 失敗: {e}", level=LogLevel.ERROR)
    
    @Slot()
    def test_update_dialog(self):
        """測試更新對話框顯示（用於調試）"""
        try:
            api_console("測試更新對話框...")
            version_info = {
                'update_available': True,
                'current_version': '2023.12.30',
                'latest_version': '2024.01.15'
            }
            self.show_update_dialog(version_info)
            return "測試對話框已觸發"
        except Exception as e:
            api_console(f"測試更新對話框失敗: {e}", level=LogLevel.ERROR)
            return f"測試失敗: {e}"
    
    def check_and_update_ytdlp(self):
        """檢查 yt-dlp 是否需要更新；若有新版本則彈出與舊版一致的更新對話框"""
        try:
            import urllib.request, json, time, os
            
            # 檢查快取檔案
            cache_file = safe_path_join(self.root_dir, 'main', 'ytdlp_version_cache.json')
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
                        api_console(f"使用快取的版本資訊: {latest}")
                except Exception as e:
                    api_console(f"讀取版本快取失敗: {e}")
            
            # 如果快取無效，從網路獲取
            if not cache_valid:
                api_console("檢查 yt-dlp 版本...")
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
                        api_console(f"版本資訊已快取: {latest}")
                    except Exception as e:
                        api_console(f"儲存版本快取失敗: {e}")
                        
                except Exception as e:
                    api_console(f"網路版本檢查失敗: {e}")
                    # 如果網路失敗但有舊快取，使用舊快取
                    if os.path.exists(cache_file):
                        try:
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                cache_data = json.load(f)
                            latest = cache_data.get('version', '')
                            api_console(f"使用舊快取版本: {latest}")
                        except Exception:
                            pass
            
            api_console(f"目前版本: {current_version}")
            if latest:
                api_console(f"偵測到的最新版本: {latest}")
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
                    # 使用信號在主線程中顯示對話框（因為 check_and_update_ytdlp 在後台線程執行）
                    api_console(f"發現 yt-dlp 新版本（目前版本: {current_version}, 最新版本: {latest}），準備顯示更新對話框", level=LogLevel.INFO)
                    self.updateDialogRequested.emit(version_info)
            return current_version
        except Exception as e:
            api_console(f"版本檢查失敗: {e}")
            return None

    @Slot(result='QVariant')
    def check_ytdlp_update_detail(self):
        """回傳是否需要更新的詳細資訊（對齊舊版資料結構）"""
        try:
            import urllib.request, json, time, os
            
            # 檢查快取檔案
            cache_file = safe_path_join(self.root_dir, 'main', 'ytdlp_version_cache.json')
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
                    api_console(f"讀取版本快取失敗: {e}")
            
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
                        api_console(f"儲存版本快取失敗: {e}")
                        
                except Exception as e:
                    api_console(f"網路版本檢查失敗: {e}")
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
            api_console(f"檢查版本細節失敗: {e}")
            return None

    @Slot()
    def startYtDlpUpdate(self):
        """由前端呼叫，啟動 yt-dlp 更新（背景執行並回報進度）——對齊舊版行為"""
        def run_update():
            try:
                self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(0, '開始更新…');")
                # 選擇 python 執行檔：優先內嵌，否則使用目前執行環境
                python_exe = safe_path_join(self.root_dir, 'lib', 'python_embed', 'python.exe')
                if not os.path.exists(python_exe):
                    python_exe = sys.executable
                cmd = [python_exe, '-m', 'pip', 'install', '--upgrade', 'yt-dlp', '--disable-pip-version-check']
                api_console(f"執行更新命令: {' '.join(cmd)}")
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
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    startupinfo=si,
                    creationflags=flags,
                )
                try:
                    import time
                    progress = 3
                    last_emit = 0.0
                    output_lines = []
                    for line in proc.stdout:
                        ln = (line or '').strip()
                        if not ln:
                            continue
                        output_lines.append(ln)
                        api_console(f"pip 輸出: {ln}")
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
                    
                    # 等待進程完成
                    ret = proc.wait()
                    output_text = '\n'.join(output_lines)
                    api_console(f"pip 更新完成，返回碼: {ret}")
                    api_console(f"pip 輸出內容: {output_text[:500]}")  # 只記錄前500字符
                    
                    if ret == 0:
                        # 驗證更新是否成功：檢查當前版本
                        try:
                            # 重新加載 yt-dlp 模組以使用新版本
                            import importlib
                            
                            # 檢查 yt-dlp 的實際安裝路徑
                            python_embed_path = safe_path_join(self.root_dir, 'lib', 'python_embed')
                            if python_embed_path not in sys.path:
                                sys.path.insert(0, python_embed_path)
                            
                            # 清除模組緩存，強制重新加載
                            modules_to_remove = [k for k in sys.modules.keys() if k.startswith('yt_dlp')]
                            for mod_name in modules_to_remove:
                                del sys.modules[mod_name]
                            
                            # 重新導入 yt_dlp 模組
                            import yt_dlp
                            # 更新全局引用
                            globals()['yt_dlp'] = yt_dlp
                            
                            # 檢查模組實際路徑
                            yt_dlp_path = yt_dlp.__file__ if hasattr(yt_dlp, '__file__') else 'unknown'
                            debug_console(f"yt-dlp 模組路徑: {yt_dlp_path}")
                            
                            new_version = yt_dlp.version.__version__
                            api_console(f"更新後 yt-dlp 版本: {new_version}", level=LogLevel.INFO)
                            
                            # 檢查是否真的安裝了新版本
                            was_updated = 'successfully installed' in output_text.lower()
                            is_latest = 'already satisfied' in output_text.lower()
                            
                            if was_updated:
                                # 真的更新了
                                self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(100, '更新完成');")
                                self._eval_js(f"window.__ofUpdateDone && window.__ofUpdateDone(true, 'yt-dlp 已成功更新到最新版本！\\n\\n目前版本: {new_version}');")
                            elif is_latest:
                                # 已經是最新版本
                                self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(100, '檢查完成');")
                                self._eval_js(f"window.__ofUpdateDone && window.__ofUpdateDone(true, 'yt-dlp 已經是最新版本！\\n\\n目前版本: {new_version}');")
                            else:
                                # 其他情況
                                self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(100, '更新完成');")
                                self._eval_js(f"window.__ofUpdateDone && window.__ofUpdateDone(true, 'yt-dlp 已更新！\\n\\n目前版本: {new_version}');")
                        except Exception as verify_err:
                            api_console(f"驗證更新版本失敗: {verify_err}", level=LogLevel.ERROR)
                            import traceback
                            api_console(traceback.format_exc(), level=LogLevel.ERROR)
                            self._eval_js("window.__ofUpdateProgress && window.__ofUpdateProgress(100, '更新完成');")
                            self._eval_js("window.__ofUpdateDone && window.__ofUpdateDone(true, 'yt-dlp 更新完成，請重新啟動應用程式以確保新版本生效。');")
                    else:
                        api_console(f"pip 更新失敗，返回碼: {ret}", level=LogLevel.ERROR)
                        api_console(f"pip 錯誤輸出: {output_text[-500:]}", level=LogLevel.ERROR)  # 只記錄最後500字符
                        self._eval_js("window.__ofUpdateDone && window.__ofUpdateDone(false, 'yt-dlp 更新失敗，請稍後再試或手動更新。');")
                finally:
                    # 確保進程資源被釋放
                    if proc.stdout:
                        proc.stdout.close()
                    if proc.poll() is None:
                        proc.terminate()
                        proc.wait()
            except Exception as e:
                api_console(f"更新執行失敗: {e}", level=LogLevel.ERROR)
                safe_msg = str(e).replace('\\', '/')
                self._eval_js(f"window.__ofUpdateDone && window.__ofUpdateDone(false, '更新過程發生錯誤：{safe_msg}');")
        threading.Thread(target=run_update, daemon=True).start()

    def show_update_dialog(self, version_info):
        """顯示更新對話框（完全對齊舊版樣式與互動）"""
        try:
            # 確保在頁面加載完成後執行
            # 注入舊版的進度對話與完成對話
            update_js = """
            if (typeof window.__executeUpdate === 'undefined') {
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
            }
            """
            self._eval_js(update_js)

            # 再注入舊版對話框，帶入具體版本號
            current_version = version_info.get('current_version', '')
            latest_version = version_info.get('latest_version', '')
            # 使用 setTimeout 確保在頁面加載完成後執行
            dialog_html = """
            setTimeout(function() {
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
            }, 100);
            """
            dialog_html = dialog_html.replace("__CURR__", str(current_version).replace('\\', '/')).replace("__LATEST__", str(latest_version).replace('\\', '/'))
            # 使用 runJavaScript 直接執行，確保立即顯示
            try:
                self.page.runJavaScript(dialog_html)
            except Exception as js_err:
                api_console(f"直接執行 JavaScript 失敗，使用信號: {js_err}")
                self._eval_js(dialog_html)
            return "update"
        except Exception as e:
            api_console(f"注入更新對話框失敗: {e}")
