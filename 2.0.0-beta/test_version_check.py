#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試版本檢查速度優化
"""

import time
import os
import sys

# 添加路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
main_dir = os.path.join(current_dir, 'main')
sys.path.insert(0, main_dir)

from core.api import Api
from PySide6.QtWebEngineWidgets import QWebEngineView

def test_version_check_speed():
    """測試版本檢查速度"""
    print("=== yt-dlp 版本檢查速度測試 ===")
    
    # 創建模擬的API實例
    class MockPage:
        pass
    
    api = Api(MockPage(), main_dir)
    
    # 測試1: 第一次檢查（可能需要網路請求）
    print("\n1. 第一次版本檢查:")
    start_time = time.time()
    result1 = api.check_ytdlp_version()
    end_time = time.time()
    print(f"   結果: {result1}")
    print(f"   耗時: {end_time - start_time:.2f} 秒")
    
    # 測試2: 第二次檢查（應該使用快取）
    print("\n2. 第二次版本檢查（快取）:")
    start_time = time.time()
    result2 = api.check_ytdlp_version()
    end_time = time.time()
    print(f"   結果: {result2}")
    print(f"   耗時: {end_time - start_time:.2f} 秒")
    
    # 測試3: 檢查更新詳情
    print("\n3. 檢查更新詳情:")
    start_time = time.time()
    result3 = api.check_ytdlp_update_detail()
    end_time = time.time()
    print(f"   結果: {result3}")
    print(f"   耗時: {end_time - start_time:.2f} 秒")
    
    # 測試4: 檢查並更新
    print("\n4. 檢查並更新:")
    start_time = time.time()
    result4 = api.check_and_update_ytdlp()
    end_time = time.time()
    print(f"   結果: {result4}")
    print(f"   耗時: {end_time - start_time:.2f} 秒")
    
    print("\n=== 測試完成 ===")

if __name__ == '__main__':
    test_version_check_speed()
