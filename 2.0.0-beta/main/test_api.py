#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 API 功能
"""

import sys
import os

# 添加當前目錄到 Python 路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 確保使用內嵌的 Python 環境
python_embed_dir = os.path.join(current_dir, 'python_embed')
if python_embed_dir not in sys.path:
    sys.path.insert(0, python_embed_dir)

try:
    # 直接測試 get_video_info 的邏輯
    import yt_dlp
    
    print("模組導入成功")
    
    def test_get_video_info(url, root_dir):
        """測試獲取影片資訊"""
        try:
            # 設定 FFMPEG 路徑
            ffmpeg_path = os.path.join(root_dir, "ffmpeg-7.1.1-essentials_build", "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
            
            # 設定 yt-dlp 選項
            ydl_opts = {
                'quiet': True,
                'simulate': True,
                'format': 'best[height<=1080]/bestaudio/best',
                'ffmpeg_location': ffmpeg_path,
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
            
            uploader = info_dict.get('uploader', '未知上傳者')
            thumbnail = info_dict.get('thumbnail', '')
            
            # 處理畫質和格式
            qualities = []
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
                'thumb': thumbnail,
                'qualities': qualities,
                'format_types': format_types
            }
            
        except Exception as e:
            print(f"獲取影片資訊失敗: {e}")
            return None
    
    # 測試 URL
    test_url = "https://www.youtube.com/watch?v=vCTRNKPJr40"
    
    print("開始測試 get_video_info...")
    result = test_get_video_info(test_url, current_dir)
    
    if result:
        print("影片資訊獲取成功！")
        print(f"標題: {result.get('title', '無標題')}")
        print(f"上傳者: {result.get('uploader', '未知')}")
        print(f"時長: {result.get('duration', '00:00')}")
        print(f"畫質: {result.get('qualities', [])}")
        print(f"格式: {result.get('format_types', [])}")
    else:
        print("影片資訊獲取失敗")
    
except Exception as e:
    print(f"錯誤: {e}")
    import traceback
    traceback.print_exc()
