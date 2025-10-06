#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
影片資訊處理模組
"""

import os
import math
import hashlib
import urllib.request
import yt_dlp
from utils.logger import debug_console, error_console
from utils.file_utils import safe_path_join

def extract_video_info(url, root_dir):
    """提取影片資訊"""
    try:
        debug_console(f"開始提取影片資訊: {url}")
        
        # 設定 FFMPEG 路徑
        ffmpeg_path = os.path.join(root_dir, "ffmpeg-7.1.1-essentials_build", "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
        debug_console(f"ffmpeg 路徑: {ffmpeg_path}")
        debug_console(f"ffmpeg 存在: {os.path.exists(ffmpeg_path)}")
        
        # 設定 yt-dlp 選項
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'simulate': True,
            'extract_flat': False,
            'ffmpeg_location': ffmpeg_path,
        }
        debug_console("yt-dlp 選項: quiet=True, no_warnings=True, simulate=True, extract_flat=False, ffmpeg_location=<ffmpeg.exe>")
        debug_console("呼叫 yt-dlp.extract_info(download=False) 開始")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
        debug_console("yt-dlp.extract_info 結束")

        title = info_dict.get('title', '無標題影片')
        uploader = info_dict.get('uploader', '未知上傳者')
        duration_seconds = info_dict.get('duration', 0)
        duration_str = format_duration(duration_seconds)
        
        # 縮圖：先取 thumbnail，否則從 thumbnails 取解析度最大者，並嘗試快取到本地
        thumbnail = info_dict.get('thumbnail') or ''
        if not thumbnail:
            thumbs = info_dict.get('thumbnails') or []
            if isinstance(thumbs, list) and thumbs:
                try:
                    best = sorted(thumbs, key=lambda t: max(t.get('width', 0) or 0, t.get('height', 0) or 0))[-1]
                    thumbnail = best.get('url') or ''
                except Exception:
                    try:
                        thumbnail = thumbs[-1].get('url') or ''
                    except Exception:
                        thumbnail = ''
        cached_thumb = cache_thumbnail(thumbnail, root_dir) if thumbnail else ''
        
        # 畫質：依 formats 的 height 建立唯一的 label 與比例
        seen_heights = set()
        qualities = []
        def gcd(a, b):
            while b:
                a, b = b, a % b
            return a
        for f in info_dict.get('formats', []) or []:
            h = f.get('height')
            w = f.get('width')
            if h and h not in seen_heights:
                ratio = ''
                if w and h:
                    g = gcd(w, h)
                    calculated = f"({w//g}:{h//g})"
                    # 僅顯示主流比例，其餘標記為 Custom
                    if calculated in ["(16:9)", "(4:3)", "(19:6)"]:
                        ratio = calculated
                    else:
                        ratio = "(Custom)"
                qualities.append({'label': f"{h}p", 'ratio': ratio})
                seen_heights.add(h)
        # 由高到低排序
        qualities.sort(key=lambda q: int(''.join(ch for ch in q['label'] if ch.isdigit()) or '0'), reverse=True)
        
        # 格式：與舊版一致，預設提供 mp4（影片）；若偵測到任何音訊流，額外提供 mp3（音訊）
        has_any_audio = any((f.get('acodec') and f.get('acodec') != 'none') for f in (info_dict.get('formats') or []))
        formats_out = [{'value': 'mp4', 'label': 'mp4', 'desc': '影片'}]
        if has_any_audio:
            formats_out.append({'value': 'mp3', 'label': 'mp3', 'desc': '音訊'})
        
        return {
            'title': title,
            'uploader': uploader,
            'duration': duration_str,
            'thumb': cached_thumb or thumbnail or '',
            'qualities': qualities,
            'formats': formats_out,
            'url': url
        }
        
    except Exception as e:
        error_console(f"提取影片資訊失敗: {e}")
        try:
            import traceback
            error_console(traceback.format_exc())
        except Exception:
            pass
        return None

def format_duration(seconds):
    """格式化時長"""
    if not seconds:
        return "未知時長"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def cache_thumbnail(thumb_url, root_dir):
    """快取縮圖"""
    if not thumb_url:
        return ""
    
    try:
        # 生成快取檔名
        thumb_hash = hashlib.md5(thumb_url.encode()).hexdigest()
        cache_dir = safe_path_join(root_dir, 'thumb_cache')
        cache_file = safe_path_join(cache_dir, f"{thumb_hash}.jpg")
        
        # 如果已存在，直接返回
        if os.path.exists(cache_file):
            return f"thumb_cache/{thumb_hash}.jpg"
        
        # 下載縮圖
        urllib.request.urlretrieve(thumb_url, cache_file)
        return f"thumb_cache/{thumb_hash}.jpg"
        
    except Exception as e:
        debug_console(f"快取縮圖失敗: {e}")
        return thumb_url

def process_formats(formats):
    """處理格式和畫質"""
    def gcd(a, b):
        while b:
            a, b = b, a % b
        return a
    
    def format_sort_key(f):
        # 優先級：影片+音訊 > 影片 > 音訊
        priority = {"影片+音訊": 3, "影片": 2, "音訊": 1}
        return (priority.get(f.get('desc', ''), 0), f.get('height', 0) or 0)
    
    # 收集所有畫質
    qualities = set()
    format_types = []
    
    for fmt in formats:
        height = fmt.get('height')
        if height:
            # 計算寬高比
            width = fmt.get('width', 0)
            if width and height:
                ratio_gcd = gcd(width, height)
                ratio = f"{width//ratio_gcd}:{height//ratio_gcd}"
            else:
                ratio = None
            
            quality_label = f"{height}p"
            qualities.add((quality_label, ratio))
        
        # 收集格式類型
        desc = fmt.get('desc', '')
        if desc and desc not in [f['desc'] for f in format_types]:
            format_types.append({
                'desc': desc,
                'value': fmt.get('format_id', ''),
                'ext': fmt.get('ext', '')
            })
    
    # 轉換為列表並排序
    qualities_list = [{'label': q[0], 'ratio': q[1]} for q in sorted(qualities, key=lambda x: int(x[0][:-1]), reverse=True)]
    format_types.sort(key=format_sort_key, reverse=True)
    
    return qualities_list, format_types
