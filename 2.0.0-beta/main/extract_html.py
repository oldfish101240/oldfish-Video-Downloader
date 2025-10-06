#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提取原始 HTML 內容
"""

def extract_html():
    with open('oldfish_downloader.pyw', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 找到 HTML 開始和結束
    start_line = -1
    end_line = -1
    for i, line in enumerate(lines):
        if 'HTML = fr"""' in line:
            start_line = i
        elif start_line != -1 and '"""' in line and i > start_line:
            end_line = i
            break

    if start_line != -1 and end_line != -1:
        html_lines = lines[start_line+1:end_line]
        html_content = ''.join(html_lines)
        
        # 處理 f-string 變數
        html_content = html_content.replace('{MENU_ICON}', 'assets/menu.png')
        html_content = html_content.replace('{HOME_ICON}', 'assets/home.png')
        html_content = html_content.replace('{QUEUE_ICON}', 'assets/quene.png')
        html_content = html_content.replace('{ICON_TEXT}', 'assets/icon_text.png')
        html_content = html_content.replace('{SETTINGS_ICON}', 'assets/settings.png')
        html_content = html_content.replace('{ICON}', 'assets/icon.png')
        
        with open('main.html', 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f'HTML 內容已提取到 main.html (行 {start_line+1} 到 {end_line})')
        return True
    else:
        print('未找到 HTML 內容')
        return False

if __name__ == '__main__':
    extract_html()
