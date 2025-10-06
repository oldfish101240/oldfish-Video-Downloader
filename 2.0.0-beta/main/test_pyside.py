#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試 PySide6 是否正常工作
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel
from PySide6.QtCore import Qt

def test_pyside():
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("PySide6 測試")
    window.setGeometry(100, 100, 400, 300)
    
    label = QLabel("PySide6 測試視窗", window)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    window.setCentralWidget(label)
    
    window.show()
    
    print("PySide6 測試視窗已顯示")
    sys.exit(app.exec())

if __name__ == '__main__':
    test_pyside()
