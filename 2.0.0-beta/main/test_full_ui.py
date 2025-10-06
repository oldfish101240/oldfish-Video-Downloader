#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試完整 UI
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
    from PySide6.QtWidgets import QApplication, QMainWindow
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QIcon
    
    print("所有模組導入成功")
    
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("OldFish 影片下載器")
    window.setGeometry(100, 100, 1000, 640)
    
    # 設定視窗圖示
    icon_path = os.path.join(current_dir, 'assets', 'icon.ico')
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    
    # 創建 WebEngineView
    web_view = QWebEngineView()
    window.setCentralWidget(web_view)
    
    # 直接讀取 main.html
    main_html_path = os.path.join(current_dir, 'main.html')
    if os.path.exists(main_html_path):
        with open(main_html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        print(f"成功讀取 main.html，長度: {len(html_content)}")
        
        # 設定基礎 URL
        base_url = QUrl.fromLocalFile(current_dir + os.sep)
        web_view.setHtml(html_content, base_url)
        
        window.show()
        print("視窗已顯示")
        sys.exit(app.exec())
    else:
        print("找不到 main.html 檔案")
    
except Exception as e:
    print(f"錯誤: {e}")
    import traceback
    traceback.print_exc()
