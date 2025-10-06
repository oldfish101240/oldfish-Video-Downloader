#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日誌和輸出工具模組
"""

class AnsiCodes:
    OKBLUE = '\033[94m'
    FAIL = '\033[91m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'
    DEBUG = '\033[36m'

def info_console(message):
    """資訊輸出"""
    print(f"{AnsiCodes.OKBLUE}[INFO]{AnsiCodes.ENDC} {message}")

def error_console(message):
    """錯誤輸出"""
    print(f"{AnsiCodes.FAIL}{AnsiCodes.BOLD}[ERROR]{AnsiCodes.ENDC} {message}")

def debug_console(message):
    """除錯輸出"""
    print(f"{AnsiCodes.DEBUG}[DEBUG]{AnsiCodes.ENDC} {message}")

def progress_console(message):
    """進度輸出"""
    import sys
    try:
        sys.stdout.write('\r' + message)
        sys.stdout.flush()
    except Exception:
        # 後備：若 stdout 不可寫，使用一般列印
        print(message)

def end_progress_line():
    """結束進度行"""
    import sys
    try:
        sys.stdout.write('\n')
        sys.stdout.flush()
    except Exception:
        pass
