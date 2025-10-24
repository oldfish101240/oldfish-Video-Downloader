#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
下載功能模組
"""

import os
import threading
import yt_dlp
from utils.logger import debug_console, info_console, error_console
from utils.file_utils import safe_path_join

class Downloader:
    """下載器類別"""
    
    def __init__(self, root_dir, progress_callback=None, complete_callback=None):
        self.root_dir = root_dir
        self.downloads_dir = safe_path_join(root_dir, 'downloads')
        self.progress_callback = progress_callback
        self.complete_callback = complete_callback
        self.active_downloads = {}
    
    def start_download(self, task_id, url, quality, format_type, downloads_dir=None, add_resolution_to_filename=False):
        """開始下載"""
        def download_task():
            try:
                info_console(f"【任務{task_id}】開始下載: {url}")
                
                # 設定下載選項
                ydl_opts = self._build_download_options(quality, format_type, downloads_dir, add_resolution_to_filename)
                
                # 設定進度回調（注入 task_id，便於前端對應）
                last_filename = {'path': ''}
                def hook(d):
                    try:
                        d['task_id'] = task_id
                        # 記錄最後檔名以便完成時回傳
                        fn = d.get('filename')
                        if fn:
                            last_filename['path'] = fn
                    except Exception:
                        pass
                    self._progress_hook(d, task_id)
                ydl_opts['progress_hooks'] = [hook]
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                info_console(f"【任務{task_id}】下載完成")
                
                # 通知完成
                if self.complete_callback:
                    try:
                        final_path = last_filename['path'] if last_filename['path'] else None
                    except Exception:
                        final_path = None
                    self.complete_callback(task_id, url, file_path=final_path)
                    
            except Exception as e:
                error_console(f"【任務{task_id}】下載失敗: {e}")
                if self.complete_callback:
                    self.complete_callback(task_id, url, error=str(e))
        
        # 在單獨的執行緒中執行下載
        thread = threading.Thread(target=download_task, daemon=True)
        thread.start()
        self.active_downloads[task_id] = thread
    
    def _build_download_options(self, quality, format_type, downloads_dir=None, add_resolution_to_filename=False):
        """建構下載選項"""
        # 設定 FFMPEG 路徑
        ffmpeg_path = os.path.join(self.root_dir, "ffmpeg-7.1.1-essentials_build", "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
        # 解析下載目錄
        target_dir = downloads_dir or self.downloads_dir
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception as e:
            error_console(f"建立下載目錄失敗: {e}")
            # 回退到預設 downloads 目錄
            target_dir = self.downloads_dir
        
        # 正規化輸入
        fmt_type = (format_type or '').strip()
        qval = (quality or '').strip()
        # 若畫質帶有 'p'，僅取數字
        try:
            import re
            m = re.search(r"(\d+)", qval)
            qnum = m.group(1) if m else qval
        except Exception:
            qnum = qval or '1080'

        # 根據設定決定檔名模板
        if add_resolution_to_filename:
            if fmt_type == "音訊":
                # 音訊格式：標題_320kbps.mp3（使用自定義位元率）
                outtmpl = os.path.join(target_dir, f'%(title)s_{qnum}kbps.%(ext)s')
            else:
                # 影片格式：標題_1080p.mp4
                outtmpl = os.path.join(target_dir, '%(title)s_%(height)sp.%(ext)s')
        else:
            # 預設格式：標題.mp4
            outtmpl = os.path.join(target_dir, '%(title)s.%(ext)s')

        ydl_opts = {
            'outtmpl': outtmpl,
            'format': self._get_format_selector(qnum, fmt_type),
            'ffmpeg_location': ffmpeg_path,
            'quiet': True,
        }
        
        # 根據格式類型設定額外選項
        if fmt_type == "音訊":
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    # 音訊位元率使用純數字，如 '320'
                    'preferredquality': str(qnum or '320'),
                }],
            })
        
        return ydl_opts
    
    def _get_format_selector(self, quality, format_type):
        """獲取格式選擇器"""
        # 影片：依高度限制，音訊：無高度限制
        if format_type == "音訊":
            return "bestaudio/best"
        # 預設影片
        return f"best[height<={quality}]/best"
    
    def _progress_hook(self, d, task_id):
        """進度回調"""
        if d['status'] == 'downloading':
            if self.progress_callback:
                self.progress_callback(task_id, d)
        elif d['status'] == 'finished':
            debug_console(f"【任務{task_id}】檔案處理完成: {d['filename']}")
    
    def cancel_download(self, task_id):
        """取消下載"""
        if task_id in self.active_downloads:
            # 注意：yt-dlp 沒有直接的取消方法，這裡只是移除追蹤
            del self.active_downloads[task_id]
            debug_console(f"【任務{task_id}】下載已取消")
    
    def get_download_status(self, task_id):
        """獲取下載狀態"""
        return task_id in self.active_downloads
