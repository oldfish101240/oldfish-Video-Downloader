 #!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主程式入口點(隱藏 console)
"""

import os
import sys

# 添加當前目錄到 Python 路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 確保使用內嵌的 Python 環境
python_embed_dir = os.path.join(current_dir, 'python_embed')
if python_embed_dir not in sys.path:
    sys.path.insert(0, python_embed_dir)

from ui.main_window import create_app
from utils.logger import debug_console, info_console, error_console
from utils.file_utils import ensure_directories

def main():
    """主函數"""
    try:
        # 獲取根目錄
        ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
        if not os.path.isabs(ROOT_DIR):
            ROOT_DIR = os.path.abspath(ROOT_DIR)
        
        info_console("啟動 oldfish影片下載器...")
        info_console(f"根目錄: {ROOT_DIR}")
        
        # 確保必要的目錄存在
        ensure_directories(ROOT_DIR)
        
        # 創建應用程式
        app, window = create_app(ROOT_DIR)
        
        # 運行應用程式
        sys.exit(app.exec())
        
    except Exception as e:
        error_console(f"啟動應用程式失敗: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
