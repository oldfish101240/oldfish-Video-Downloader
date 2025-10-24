#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日誌和輸出工具模組
"""

import os
import sys

class LogLevel:
    """日誌等級"""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3

# 全域日誌等級設定
_log_level = LogLevel.INFO

def set_log_level(level):
    """設定日誌等級"""
    global _log_level
    _log_level = level

def get_log_level():
    """獲取當前日誌等級"""
    return _log_level

class AnsiCodes:
    OKBLUE = '\033[94m'
    FAIL = '\033[91m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'
    DEBUG = '\033[36m'
    WARNING = '\033[93m'

def _should_log(level):
    """檢查是否應該輸出日誌"""
    return level >= _log_level

def info_console(message):
    """資訊輸出"""
    if _should_log(LogLevel.INFO):
        print(f"{AnsiCodes.OKBLUE}[INFO]{AnsiCodes.ENDC} {message}")

def error_console(message):
    """錯誤輸出"""
    if _should_log(LogLevel.ERROR):
        print(f"{AnsiCodes.FAIL}{AnsiCodes.BOLD}[ERROR]{AnsiCodes.ENDC} {message}")

def debug_console(message):
    """除錯輸出"""
    if _should_log(LogLevel.DEBUG):
        print(f"{AnsiCodes.DEBUG}[DEBUG]{AnsiCodes.ENDC} {message}")

def warning_console(message):
    """警告輸出"""
    if _should_log(LogLevel.WARNING):
        print(f"{AnsiCodes.WARNING}[WARNING]{AnsiCodes.ENDC} {message}")

def progress_console(message):
    """進度輸出"""
    if _should_log(LogLevel.INFO):
        try:
            sys.stdout.write('\r' + message)
            sys.stdout.flush()
        except Exception:
            # 後備：若 stdout 不可寫，使用一般列印
            print(message)

def end_progress_line():
    """結束進度行"""
    if _should_log(LogLevel.INFO):
        try:
            sys.stdout.write('\n')
            sys.stdout.flush()
        except Exception:
            pass
