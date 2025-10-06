#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
簡單測試版本
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
    from PySide6.QtWidgets import QApplication, QMainWindow, QLabel
    from PySide6.QtCore import Qt
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtCore import QUrl
    
    print("所有模組導入成功")
    
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("OldFish 影片下載器 - 測試版")
    window.setGeometry(100, 100, 1000, 640)
    
    # 創建 WebEngineView
    web_view = QWebEngineView()
    window.setCentralWidget(web_view)
    
    # 載入簡單的 HTML
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>測試</title>
        <style>
            body { background: #181a20; color: #e5e7eb; font-family: Arial; padding: 20px; }
            h1 { color: #2ecc71; }
        </style>
    </head>
    <body>
        <h1>OldFish 影片下載器</h1>
        <p>測試版本正在運行...</p>
    </body>
    </html>
    """
    
    web_view.setHtml(html_content)
    
    window.show()
    
    print("視窗已顯示")
    sys.exit(app.exec())
    
except Exception as e:
    print(f"錯誤: {e}")
    import traceback
    traceback.print_exc()
