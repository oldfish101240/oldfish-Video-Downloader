#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 HTML 內容載入
"""

import sys
import os

# 添加當前目錄到 Python 路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from ui.html_content import get_html_content
    html = get_html_content()
    print(f'HTML 長度: {len(html)}')
    print(f'包含 CSS: {"background: #181a20" in html}')
    print(f'包含 body: {"<body>" in html}')
    print(f'包含 style: {"<style>" in html}')
    
    # 檢查是否載入了 main.html
    if len(html) > 50000:
        print("✅ 成功載入完整的 HTML 內容")
    else:
        print("❌ 載入的是簡化版本")
        
except Exception as e:
    print(f"錯誤: {e}")
    import traceback
    traceback.print_exc()
