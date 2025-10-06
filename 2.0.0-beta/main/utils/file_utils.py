#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
檔案和路徑處理工具模組
"""

import os
from .logger import debug_console, error_console

def ensure_directories(root_dir):
    """確保必要的目錄存在"""
    try:
        downloads_dir = os.path.join(root_dir, 'downloads')
        os.makedirs(downloads_dir, exist_ok=True)
        
        thumb_cache_dir = os.path.join(root_dir, 'thumb_cache')
        os.makedirs(thumb_cache_dir, exist_ok=True)
        
        debug_console("必要目錄已確保存在")
    except OSError as e:
        error_console(f"創建必要目錄失敗: {e}")

def safe_path_join(*paths):
    """安全地連接路徑，處理相對路徑和絕對路徑"""
    try:
        # 過濾掉空字串和 None
        valid_paths = [p for p in paths if p and p.strip()]
        if not valid_paths:
            return ""
        
        # 如果第一個路徑是絕對路徑，從它開始
        if os.path.isabs(valid_paths[0]):
            result = valid_paths[0]
            for path in valid_paths[1:]:
                result = os.path.join(result, path)
        else:
            # 否則使用 os.path.join 正常連接
            result = os.path.join(*valid_paths)
        
        # 正規化路徑
        return os.path.normpath(result)
    except Exception as e:
        error_console(f"路徑連接失敗: {e}")
        return ""

def get_assets_path(root_dir):
    """獲取資源檔案路徑"""
    return safe_path_join(root_dir, 'assets')
