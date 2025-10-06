#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 yt-dlp 功能
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
    import yt_dlp
    print("yt-dlp 導入成功")
    
    # 測試 URL
    test_url = "https://www.youtube.com/watch?v=vCTRNKPJr40"
    
    # 設定 FFMPEG 路徑
    ffmpeg_path = os.path.join(current_dir, "ffmpeg-7.1.1-essentials_build", "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
    print(f"FFMPEG 路徑: {ffmpeg_path}")
    print(f"FFMPEG 存在: {os.path.exists(ffmpeg_path)}")
    
    # 設定 yt-dlp 選項
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'simulate': True,
        'extract_flat': False,
        'ffmpeg_location': ffmpeg_path,
    }
    
    print("開始提取影片資訊...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(test_url, download=False)
    
    print("影片資訊提取成功！")
    print(f"標題: {info_dict.get('title', '無標題')}")
    print(f"上傳者: {info_dict.get('uploader', '未知')}")
    print(f"時長: {info_dict.get('duration', 0)} 秒")
    
except Exception as e:
    print(f"錯誤: {e}")
    import traceback
    traceback.print_exc()
