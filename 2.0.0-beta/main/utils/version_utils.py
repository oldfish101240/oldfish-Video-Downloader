#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
版本處理工具模組
"""

import re

def compare_versions(version1, version2):
    """比較兩個版本號，返回 -1, 0, 1 分別表示 version1 <, =, > version2"""
    def version_tuple(v):
        # 將版本號轉換為元組，例如 "1.2.3" -> (1, 2, 3)
        parts = []
        for part in v.split('.'):
            # 移除非數字字符，只保留數字部分
            numeric_part = re.sub(r'[^\d]', '', part)
            if numeric_part:
                parts.append(int(numeric_part))
            else:
                parts.append(0)
        return tuple(parts)
    
    v1_tuple = version_tuple(version1)
    v2_tuple = version_tuple(version2)
    
    if v1_tuple < v2_tuple:
        return -1
    elif v1_tuple > v2_tuple:
        return 1
    else:
        return 0
