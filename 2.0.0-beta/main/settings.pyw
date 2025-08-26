#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
設定頁面 - oldfish影片下載器
"""

import sys
import os
import json
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QObject, Slot, QUrl, Qt
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtGui import QIcon

# 添加主程式目錄到路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def debug_console(message):
    """控制台輸出"""
    print(f"[設定] {message}")

class SettingsApi(QObject):
    """設定頁面API類"""
    
    def __init__(self):
        super().__init__()
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.settings_file = os.path.join(self.root_dir, 'settings.json')
    
    @Slot(result=dict)
    def load_settings(self):
        """載入設定"""
        try:
            debug_console("載入設定中...")
            
            default_settings = {
                'downloadPath': os.path.join(self.root_dir, 'downloads'),
                'enableNotifications': True,
                'theme': 'dark'
            }
            
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                # 確保所有預設設定都存在
                for key, value in default_settings.items():
                    if key not in settings:
                        settings[key] = value
                debug_console(f"設定載入成功: {settings}")
                return settings
            else:
                debug_console("使用預設設定")
                return default_settings
                
        except Exception as e:
            debug_console(f"載入設定失敗: {e}")
            return {
                'downloadPath': os.path.join(self.root_dir, 'downloads'),
                'enableNotifications': True,
                'theme': 'dark'
            }
    
    @Slot(dict)
    def save_settings(self, settings):
        """儲存設定"""
        try:
            debug_console(f"儲存設定: {settings}")
            os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            debug_console("設定儲存成功")
        except Exception as e:
            debug_console(f"儲存設定失敗: {e}")
            raise
    
    @Slot(result=str)
    def select_download_path(self):
        """選擇下載路徑"""
        try:
            from PySide6.QtWidgets import QFileDialog
            
            current_path = self.load_settings().get('downloadPath', os.path.join(self.root_dir, 'downloads'))
            
            selected_path = QFileDialog.getExistingDirectory(
                None,
                "選擇下載資料夾",
                current_path
            )
            
            if selected_path:
                debug_console(f"選擇的路徑: {selected_path}")
                return selected_path
            return ""
            
        except Exception as e:
            debug_console(f"選擇路徑失敗: {e}")
            return ""

class SettingsWindow(QMainWindow):
    """設定視窗類"""
    
    def __init__(self):
        super().__init__()
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.init_ui()
        
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("設定 - oldfish影片下載器")
        self.setFixedSize(900, 700)
        
        # 創建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 創建佈局
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 創建WebEngineView
        self.web_view = QWebEngineView()
        self.web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # 禁用右鍵選單
        
        # 創建API實例和WebChannel
        self.api = SettingsApi()
        self.web_channel = QWebChannel()
        self.web_channel.registerObject('api', self.api)
        
        # 將WebChannel注入到WebEngineView
        self.web_view.page().setWebChannel(self.web_channel)
        
        # 載入HTML內容
        html_content = self.get_html_content()
        self.web_view.setHtml(html_content, QUrl.fromLocalFile(self.root_dir))
        
        layout.addWidget(self.web_view)
    
    def get_html_content(self):
        """獲取HTML內容"""
        return """
        <!DOCTYPE html>
        <html lang="zh-TW">
                 <head>
             <meta charset="UTF-8">
             <meta name="viewport" content="width=device-width, initial-scale=1.0">
             <title>設定 - oldfish影片下載器</title>
             <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                
                body {
                    font-family: 'Microsoft JhengHei', sans-serif;
                    background: #1a1d23;
                    color: #e5e7eb;
                    min-height: 100vh;
                    display: flex;
                    flex-direction: column;
                }
                
                .header {
                    background: #2b2e37;
                    padding: 20px;
                    border-bottom: 1px solid #444;
                    display: flex;
                    align-items: center;
                    gap: 16px;
                }
                
                .header h1 {
                    font-size: 24px;
                    font-weight: bold;
                    color: #2ecc71;
                }
                
                .settings-container {
                    flex: 1;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    width: 100%;
                }
                
                .settings-section {
                    background: #2b2e37;
                    border-radius: 12px;
                    padding: 24px;
                    margin-bottom: 24px;
                    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
                }
                
                .settings-section h2 {
                    font-size: 20px;
                    color: #2ecc71;
                    margin-bottom: 20px;
                    border-bottom: 2px solid #2ecc71;
                    padding-bottom: 8px;
                }
                
                .settings-item {
                    margin-bottom: 20px;
                }
                
                .settings-item:last-child {
                    margin-bottom: 0;
                }
                
                .settings-label {
                    display: block;
                    font-size: 16px;
                    font-weight: 500;
                    margin-bottom: 8px;
                    color: #e5e7eb;
                }
                
                .settings-description {
                    font-size: 14px;
                    color: #888;
                    margin-top: 6px;
                }
                
                .settings-input-group {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    margin-top: 8px;
                }
                
                .settings-path-display {
                    flex: 1;
                    background: #1a1d23;
                    border: 1px solid #444;
                    border-radius: 6px;
                    padding: 10px 12px;
                    color: #e5e7eb;
                    font-size: 14px;
                    word-break: break-all;
                }
                
                .settings-btn {
                    background: #27ae60;
                    color: #fff;
                    border: none;
                    border-radius: 8px;
                    padding: 12px 24px;
                    font-size: 16px;
                    cursor: pointer;
                    font-weight: 500;
                    transition: background 0.2s;
                    min-width: 100px;
                    min-height: 44px;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                }
                
                .settings-btn:hover {
                    background: #229954;
                }
                
                .settings-btn.primary {
                    background: #2ecc71;
                    padding: 14px 32px;
                    font-size: 18px;
                    min-width: 120px;
                    min-height: 48px;
                }
                
                .settings-toggle-group {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    margin-top: 8px;
                }
                
                .settings-toggle {
                    position: relative;
                    display: inline-block;
                    width: 60px;
                    height: 30px;
                    cursor: pointer;
                }
                
                .settings-toggle input {
                    opacity: 0;
                    width: 0;
                    height: 0;
                }
                
                .settings-toggle-slider {
                    position: absolute;
                    cursor: pointer;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background-color: #444;
                    transition: 0.3s;
                    border-radius: 30px;
                }
                
                .settings-toggle-slider:before {
                    position: absolute;
                    content: "";
                    height: 22px;
                    width: 22px;
                    left: 4px;
                    bottom: 4px;
                    background-color: #fff;
                    transition: 0.3s;
                    border-radius: 50%;
                }
                
                .settings-toggle input:checked + .settings-toggle-slider {
                    background-color: #2ecc71;
                }
                
                .settings-toggle input:checked + .settings-toggle-slider:before {
                    transform: translateX(30px);
                }
                
                .settings-toggle-text {
                    font-size: 14px;
                    color: #e5e7eb;
                    padding-left: 2px;
                }
                
                .settings-theme-display {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    margin-top: 8px;
                    padding: 12px 16px;
                    background: #2b2e37;
                    border-radius: 8px;
                    border: 1px solid #444;
                }
                
                .settings-theme-current {
                    font-size: 16px;
                    color: #e5e7eb;
                    font-weight: 500;
                }
                
                .settings-theme-note {
                    font-size: 12px;
                    color: #888;
                    font-style: italic;
                }
                
                .settings-actions {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-top: 32px;
                    padding-top: 24px;
                    border-top: 1px solid #444;
                }
                
                .modal {
                    display: none;
                    position: fixed;
                    z-index: 10000;
                    left: 0;
                    top: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.8);
                }
                
                .modal-content {
                    background: #2b2e37;
                    margin: 15% auto;
                    padding: 30px;
                    border-radius: 12px;
                    width: 90%;
                    max-width: 400px;
                    text-align: center;
                    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
                }
                
                .modal h3 {
                    color: #2ecc71;
                    margin-bottom: 16px;
                    font-size: 20px;
                }
                
                .modal p {
                    color: #e5e7eb;
                    margin-bottom: 24px;
                    line-height: 1.5;
                }
                
                .modal-btn {
                    background: #2ecc71;
                    color: #fff;
                    border: none;
                    padding: 10px 24px;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 16px;
                    font-weight: 500;
                }
                
                .modal-btn:hover {
                    background: #27ae60;
                }
                
                /* 淺色主題 */
                body.light-theme {
                    background: #f8f9fa;
                    color: #333;
                }
                
                body.light-theme .header {
                    background: #ffffff;
                    border-bottom-color: #ddd;
                }
                
                body.light-theme .settings-section {
                    background: #ffffff;
                    box-shadow: 0 4px 24px rgba(0,0,0,0.1);
                }
                
                body.light-theme .settings-path-display {
                    background: #f8f9fa;
                    border-color: #ddd;
                    color: #333;
                }
                
                body.light-theme .settings-toggle-text,
                body.light-theme .settings-label {
                    color: #333;
                }
                
                body.light-theme .settings-description {
                    color: #666;
                }
                
                body.light-theme .settings-theme-display {
                    background: #ffffff;
                    border-color: #ddd;
                }
                
                body.light-theme .settings-theme-current {
                    color: #333;
                }
                
                body.light-theme .settings-theme-note {
                    color: #666;
                }
                
                body.light-theme .modal-content {
                    background: #ffffff;
                }
                
                body.light-theme .modal h3 {
                    color: #2ecc71;
                }
                
                body.light-theme .modal p {
                    color: #333;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>⚙️ 設定</h1>
            </div>
            
            <div class="settings-container">
                <!-- 下載設定 -->
                <div class="settings-section">
                    <h2>📥 下載設定</h2>
                    
                    <div class="settings-item">
                        <label class="settings-label">下載目錄</label>
                        <div class="settings-input-group">
                            <div class="settings-path-display" id="download-path-display">
                                正在載入...
                            </div>
                            <button class="settings-btn" onclick="selectDownloadPath()">選擇資料夾</button>
                        </div>
                        <div class="settings-description">選擇影片檔案的儲存位置</div>
                    </div>
                    
                    <div class="settings-item">
                        <label class="settings-label">下載完成通知</label>
                        <div class="settings-toggle-group">
                            <label class="settings-toggle">
                                <input type="checkbox" id="enable-notifications">
                                <span class="settings-toggle-slider"></span>
                            </label>
                            <span class="settings-toggle-text">啟用桌面通知</span>
                        </div>
                        <div class="settings-description">下載完成時顯示桌面通知</div>
                    </div>
                </div>
                
                <!-- 介面設定 -->
                <div class="settings-section">
                    <h2>🎨 介面設定</h2>
                    
                    <div class="settings-item">
                        <label class="settings-label">主題選擇</label>
                        <div class="settings-theme-display">
                            <span class="settings-theme-current">深色主題</span>
                            <span class="settings-theme-note">（淺色主題開發中）</span>
                        </div>
                        <div class="settings-description">選擇應用程式的外觀主題</div>
                    </div>
                </div>
                
                <!-- 操作按鈕 -->
                <div class="settings-actions">
                    <button class="settings-btn" onclick="resetSettings()">重設為預設值</button>
                    <button class="settings-btn primary" onclick="saveSettings()">儲存設定</button>
                </div>
            </div>
            
            <!-- 模態視窗 -->
            <div id="modal" class="modal">
                <div class="modal-content">
                    <h3 id="modal-title">標題</h3>
                    <p id="modal-message">訊息</p>
                    <button class="modal-btn" onclick="closeModal()">確定</button>
                </div>
            </div>
            
            <script>
                                 // 當前設定
                 let currentSettings = {
                     downloadPath: 'downloads',  // 預設路徑
                     enableNotifications: true,
                     theme: 'dark'
                 };
                
                /**
                 * 載入設定
                 */
                                 function loadSettings() {
                     if (window.qt && window.qt.webChannelTransport) {
                         new QWebChannel(qt.webChannelTransport, function(channel) {
                             window.api = channel.objects.api;
                             
                             window.api.load_settings()
                                 .then(settings => {
                                     currentSettings = settings;
                                     updateSettingsUI();
                                     applyTheme(settings.theme);
                                     // 重新初始化事件監聽器
                                     initializeEventListeners();
                                 })
                                 .catch(error => {
                                     console.error('載入設定失敗:', error);
                                     updateSettingsUI();
                                     applyTheme('dark');
                                     // 重新初始化事件監聽器
                                     initializeEventListeners();
                                 });
                         });
                     } else {
                         console.error('WebChannel not available');
                         updateSettingsUI();
                         applyTheme('dark');
                         // 重新初始化事件監聽器
                         initializeEventListeners();
                     }
                 }
                
                /**
                 * 更新設定UI
                 */
                                 function updateSettingsUI() {
                     // 更新下載路徑顯示
                     const pathDisplay = document.getElementById('download-path-display');
                     if (pathDisplay) {
                         // 如果沒有設定路徑，顯示預設路徑
                         if (!currentSettings.downloadPath || currentSettings.downloadPath === '') {
                             pathDisplay.textContent = 'downloads';
                         } else {
                             pathDisplay.textContent = currentSettings.downloadPath;
                         }
                     }
                    
                    // 更新通知設定
                    const notificationsCheckbox = document.getElementById('enable-notifications');
                    if (notificationsCheckbox) {
                        notificationsCheckbox.checked = currentSettings.enableNotifications;
                    }
                }
                
                /**
                 * 選擇下載路徑
                 */
                                 function selectDownloadPath() {
                     if (window.api) {
                         window.api.select_download_path()
                             .then(path => {
                                 if (path) {
                                     currentSettings.downloadPath = path;
                                     updateSettingsUI();
                                 }
                             })
                             .catch(error => {
                                 console.error('選擇路徑失敗:', error);
                                 showModal('錯誤', '選擇路徑失敗');
                             });
                     } else {
                         showModal('錯誤', 'API未初始化');
                     }
                 }
                
                /**
                 * 應用主題
                 */
                function applyTheme(theme) {
                    if (theme === 'light') {
                        document.body.classList.add('light-theme');
                    } else {
                        document.body.classList.remove('light-theme');
                    }
                }
                
                /**
                 * 儲存設定
                 */
                function saveSettings() {
                    // 更新通知設定
                    const notificationsCheckbox = document.getElementById('enable-notifications');
                    if (notificationsCheckbox) {
                        currentSettings.enableNotifications = notificationsCheckbox.checked;
                    }
                    
                                         if (window.api) {
                         window.api.save_settings(currentSettings)
                             .then(() => {
                                 showModal('成功', '設定已儲存');
                             })
                             .catch(error => {
                                 console.error('儲存設定失敗:', error);
                                 showModal('錯誤', '儲存設定失敗');
                             });
                     } else {
                         showModal('錯誤', 'API未初始化');
                     }
                }
                
                /**
                 * 重設設定
                 */
                                 function resetSettings() {
                     if (confirm('確定要重設所有設定為預設值嗎？')) {
                         currentSettings = {
                             downloadPath: 'downloads',  // 預設路徑
                             enableNotifications: true,
                             theme: 'dark'
                         };
                        updateSettingsUI();
                        applyTheme('dark');
                        showModal('成功', '設定已重設為預設值');
                    }
                }
                
                /**
                 * 顯示模態視窗
                 */
                function showModal(title, message) {
                    const modal = document.getElementById('modal');
                    const modalTitle = document.getElementById('modal-title');
                    const modalMessage = document.getElementById('modal-message');
                    
                    if (modal && modalTitle && modalMessage) {
                        modalTitle.textContent = title;
                        modalMessage.textContent = message;
                        modal.style.display = 'block';
                    }
                }
                
                /**
                 * 關閉模態視窗
                 */
                function closeModal() {
                    const modal = document.getElementById('modal');
                    if (modal) {
                        modal.style.display = 'none';
                    }
                }
                
                // 初始化事件監聽器
                function initializeEventListeners() {
                    console.log('初始化事件監聽器...');
                    
                    // 通知開關事件監聽器
                    const notificationsCheckbox = document.getElementById('enable-notifications');
                    if (notificationsCheckbox) {
                        console.log('找到通知開關元素，綁定事件監聽器');
                        // 移除舊的事件監聽器（如果存在）
                        notificationsCheckbox.removeEventListener('change', handleNotificationChange);
                        // 添加新的事件監聽器
                        notificationsCheckbox.addEventListener('change', handleNotificationChange);
                    } else {
                        console.error('找不到通知開關元素');
                    }
                    
                    // 點擊模態視窗背景關閉
                    const modal = document.getElementById('modal');
                    if (modal) {
                        modal.removeEventListener('click', handleModalClick);
                        modal.addEventListener('click', handleModalClick);
                    }
                }
                
                // 通知開關變更處理函數
                function handleNotificationChange() {
                    const notificationsCheckbox = document.getElementById('enable-notifications');
                    if (notificationsCheckbox) {
                        currentSettings.enableNotifications = notificationsCheckbox.checked;
                        console.log('通知設定已更新:', this.checked);
                        // 立即更新UI狀態
                        updateSettingsUI();
                    }
                }
                
                // 模態視窗點擊處理函數
                function handleModalClick(e) {
                    if (e.target === this) {
                        closeModal();
                    }
                }
                
                // 頁面載入完成後初始化
                if (document.readyState === 'loading') {
                    document.addEventListener('DOMContentLoaded', function() {
                        console.log('DOM載入完成，開始初始化...');
                        loadSettings();
                    });
                } else {
                    // 如果頁面已經載入完成，直接初始化
                    console.log('頁面已載入完成，直接初始化...');
                    loadSettings();
                }
            </script>
        </body>
        </html>
        """

def main():
    """主函數"""
    try:
        app = QApplication(sys.argv)
        
        # 創建設定視窗
        window = SettingsWindow()
        window.show()
        
        # 啟動應用
        sys.exit(app.exec())
        
    except Exception as e:
        debug_console(f"啟動設定頁面失敗: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
