#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
設定頁面 - oldfish影片下載器
使用PySide6 + HTML
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
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

def debug_console(message):
    """控制台輸出"""
    print(f"[設定] {message}")

class SettingsApi(QObject):
    """設定頁面API類"""
    
    def __init__(self):
        super().__init__()
        self.root_dir = ROOT_DIR
        self.settings_file = os.path.join(self.root_dir, 'main', 'settings.json')
    
    @Slot(result=dict)
    def load_settings(self):
        """載入設定"""
        try:
            debug_console("載入設定中...")
            
            default_settings = {
                'enableNotifications': True,
                'downloadDir': 'downloads'
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
                'enableNotifications': True,
                'downloadDir': 'downloads'
            }
    
    @Slot(dict)
    def save_settings(self, settings):
        """儲存設定"""
        try:
            debug_console(f"收到儲存請求: {settings}")
            debug_console(f"設定檔案路徑: {self.settings_file}")
            
            
            # 確保目錄存在
            settings_dir = os.path.dirname(self.settings_file)
            os.makedirs(settings_dir, exist_ok=True)
            debug_console(f"設定目錄: {settings_dir}")
            
            # 寫入檔案
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            
            debug_console("設定儲存成功")
            debug_console(f"檔案內容已寫入: {self.settings_file}")
            
            # 驗證檔案是否真的被寫入
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    saved_content = f.read()
                debug_console(f"檔案內容驗證: {saved_content[:200]}...")
            else:
                debug_console("錯誤：檔案未被創建")
                
        except Exception as e:
            debug_console(f"儲存設定失敗: {e}")
            import traceback
            debug_console(f"錯誤詳情: {traceback.format_exc()}")
            raise
    
    @Slot(result=dict)
    def reset_to_defaults(self):
        """重設為預設值"""
        try:
            debug_console("重設為預設值")
            default_settings = {
                'enableNotifications': True,
                'downloadDir': 'downloads'
            }
            debug_console(f"預設設定: {default_settings}")
            return default_settings
        except Exception as e:
            debug_console(f"重設為預設值失敗: {e}")
            return {
                'enableNotifications': True,
                'downloadDir': 'downloads'
            }



    def _try_windows_toast_api(self, title, message):
        """嘗試使用Windows Toast API"""
        try:
            import subprocess
            
            ps_script = f"""
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            
            $template = @"
            <toast>
                <visual>
                    <binding template="ToastGeneric">
                        <text>{title}</text>
                        <text>{message}</text>
                    </binding>
                </visual>
                <audio src="ms-winsoundevent:Notification.Default"/>
            </toast>
"@
            
            $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
            $xml.LoadXml($template)
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            $toast.ExpirationTime = [DateTimeOffset]::Now.AddMinutes(1)
            $toast.Tag = "OldFishDownloader"
            $toast.Group = "Test"
            
            $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("OldFish Video Downloader")
            $notifier.Show($toast)
            """
            
            result = subprocess.run([
                'powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_script
            ], capture_output=True, timeout=10)
            
            return result.returncode == 0
                
        except Exception as e:
            debug_console(f"Windows Toast API異常: {e}")
            return False

    def _try_plyer_notification(self, title, message):
        """嘗試使用plyer通知"""
        try:
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                timeout=5
            )
            return True
        except Exception as e:
            debug_console(f"plyer通知失敗: {e}")
            return False

    def _try_win10toast(self, title, message):
        """嘗試使用win10toast"""
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            result = toaster.show_toast(
                title, 
                message, 
                duration=5,
                threaded=False
            )
            return result
        except Exception as e:
            debug_console(f"win10toast異常: {e}")
            return False

    def _try_messagebox_fallback(self, title, message):
        """回退到MessageBox"""
        try:
            import subprocess
            
            ps_script = f"""
            Add-Type -AssemblyName System.Windows.Forms
            [System.Windows.Forms.MessageBox]::Show('{message}', '{title}', 'OK', 'Information')
            """
            
            result = subprocess.run([
                'powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_script
            ], capture_output=True, timeout=10)
            
            return result.returncode == 0
                
        except Exception as e:
            debug_console(f"MessageBox通知異常: {e}")
            return False

class SettingsWindow(QMainWindow):
    """設定視窗類"""
    
    # 類變數，用於追蹤唯一的設定視窗實例
    _instance = None
    
    def __new__(cls):
        """單例模式：確保只有一個設定視窗實例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # 避免重複初始化
        if hasattr(self, '_initialized'):
            return
        super().__init__()
        self.root_dir = ROOT_DIR
        self._initialized = True
        self.init_ui()
        
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("設定 - oldfish影片下載器")
        self.setFixedSize(500, 350)  # 調小視窗大小
        
        # 設定視窗圖示
        icon_path = os.path.join(ROOT_DIR, 'main', 'assets', 'icon.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # 創建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 創建佈局
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 創建WebEngineView
        self.web_view = QWebEngineView()
        self.web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)  # 禁用右鍵選單
        
        # 優化WebEngine設定
        self.web_view.settings().setAttribute(self.web_view.settings().WebAttribute.JavascriptEnabled, True)
        self.web_view.settings().setAttribute(self.web_view.settings().WebAttribute.LocalContentCanAccessRemoteUrls, False)
        self.web_view.settings().setAttribute(self.web_view.settings().WebAttribute.LocalContentCanAccessFileUrls, True)
        
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
    
    def show_and_focus(self):
        """顯示視窗並設定焦點"""
        self.show()
        self.raise_()  # 將視窗提到最前面
        self.activateWindow()  # 啟用視窗
        debug_console("設定視窗已顯示並設定焦點")
    
    def closeEvent(self, event):
        """視窗關閉事件"""
        debug_console("設定視窗正在關閉")
        # 重置單例實例
        SettingsWindow._instance = None
        event.accept()
    
    def get_html_content(self):
        """獲取HTML內容"""
        return """
        <!DOCTYPE html>
        <html lang="zh-TW">
        <head>
            <meta charset="UTF-8">
            <title>設定</title>
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <style>
                body {
                    font-family: 'Microsoft JhengHei', sans-serif;
                    background: #1a1d23;
                    color: #e5e7eb;
                    margin: 0;
                    padding: 20px;
                }
                .header {
                    background: #2b2e37;
                    padding: 15px;
                    border-radius: 8px;
                    margin-bottom: 20px;
                }
                .header h1 {
                    color: #2ecc71;
                    margin: 0;
                    font-size: 20px;
                }
                .section {
                    background: #2b2e37;
                    padding: 20px;
                    border-radius: 8px;
                    margin-bottom: 15px;
                }
                .section h2 {
                    color: #2ecc71;
                    margin: 0 0 15px 0;
                    font-size: 16px;
                }
                .item {
                    margin-bottom: 15px;
                }
                .label {
                    display: block;
                    margin-bottom: 5px;
                    color: #e5e7eb;
                }
                .input-group {
                    display: flex;
                    gap: 10px;
                    align-items: center;
                }
                .path-display {
                    flex: 1;
                    background: #1a1d23;
                    border: 1px solid #444;
                    padding: 8px;
                    border-radius: 4px;
                    color: #e5e7eb;
                    font-size: 14px;
                }
                .btn {
                    background: #2ecc71;
                    color: #fff;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 14px;
                }
                .btn:hover {
                    background: #27ae60;
                }
                .btn.primary {
                    background: #2ecc71;
                    padding: 10px 20px;
                    font-size: 16px;
                }
                .actions {
                    display: flex;
                    justify-content: space-between;
                    margin-top: 20px;
                    padding-top: 15px;
                    border-top: 1px solid #444;
                }
                .modal {
                    display: none;
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0,0,0,0.8);
                    z-index: 1000;
                }
                .modal-content {
                    background: #2b2e37;
                    margin: 20% auto;
                    padding: 20px;
                    border-radius: 8px;
                    width: 300px;
                    text-align: center;
                }
                .modal h3 {
                    color: #2ecc71;
                    margin: 0 0 10px 0;
                }
                .modal p {
                    margin: 0 0 15px 0;
                }
                input[type="checkbox"] {
                    width: 16px;
                    height: 16px;
                    accent-color: #2ecc71;
                    cursor: pointer;
                }
                .checkbox-label {
                    display: flex;
                    align-items: center;
                    cursor: pointer;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>設定</h1>
            </div>
            
            
            <div class="section">
                <h2>通知設定</h2>
                <div class="item">
                    <label class="checkbox-label">
                        <input type="checkbox" id="enable-notifications">
                        <span style="margin-left: 8px;">啟用下載完成通知</span>
                    </label>
                </div>
            </div>

            
            
            <div class="actions">
                <button class="btn" onclick="resetSettings()">重設</button>
                <button class="btn primary" onclick="saveSettings()">儲存</button>
            </div>
            
            <div id="modal" class="modal">
                <div class="modal-content">
                    <h3 id="modal-title">標題</h3>
                    <p id="modal-message">訊息</p>
                    <button class="btn" onclick="closeModal()">確定</button>
                </div>
            </div>
            
            <script>
                let currentSettings = {
                    enableNotifications: true,
                    downloadDir: 'downloads'
                };
                
                function loadSettings() {
                    console.log('開始載入設定...');
                    
                    // 等待WebChannel準備就緒
                    function initWebChannel() {
                        if (window.qt && window.qt.webChannelTransport) {
                            console.log('WebChannel可用，初始化API...');
                            new QWebChannel(qt.webChannelTransport, function(channel) {
                                window.api = channel.objects.api;
                                console.log('API已初始化:', window.api);
                                window.api.load_settings().then(settings => {
                                    console.log('載入的設定:', settings);
                                    currentSettings = settings;
                                    updateUI();
                                }).catch(error => {
                                    console.error('載入設定失敗:', error);
                                    updateUI();
                                });
                            });
                        } else {
                            console.log('WebChannel尚未準備就緒，等待中...');
                            setTimeout(initWebChannel, 100);
                        }
                    }
                    
                    initWebChannel();
                }
                
                function updateUI() {
                    const notificationCheckbox = document.getElementById('enable-notifications');
                    if (notificationCheckbox) {
                        notificationCheckbox.checked = currentSettings.enableNotifications || true;
                    }
                    const downloadDirInput = document.getElementById('download-dir');
                    if (downloadDirInput) {
                        downloadDirInput.value = currentSettings.downloadDir || 'downloads';
                    }
                }
                
                
                function saveSettings() {
                    // 確保所有設定都是最新的
                    updateCurrentSettings();
                    
                    if (window.api) {
                        window.api.save_settings(currentSettings).then(() => {
                            showModal('成功', '設定已儲存');
                        }).catch((error) => {
                            console.error('儲存設定失敗:', error);
                            showModal('錯誤', '儲存失敗');
                        });
                    } else {
                        showModal('錯誤', 'API未初始化');
                    }
                }
                
                function updateCurrentSettings() {
                    // 更新當前設定，確保所有變更都被保存
                    const notificationCheckbox = document.getElementById('enable-notifications');
                    if (notificationCheckbox) {
                        currentSettings.enableNotifications = notificationCheckbox.checked;
                    }
                    const downloadDirInput = document.getElementById('download-dir');
                    if (downloadDirInput && downloadDirInput.value) {
                        currentSettings.downloadDir = downloadDirInput.value.trim();
                    }
                }

                function waitForBridge(timeoutMs = 8000) {
                    return new Promise((resolve, reject) => {
                        const t0 = Date.now();
                        (function loop(){
                            const bridge = (window.pywebview && window.pywebview.api) ? window.pywebview.api : window.api;
                            if (bridge && typeof bridge.choose_folder === 'function') {
                                return resolve(bridge);
                            }
                            if (Date.now() - t0 > timeoutMs) return reject(new Error('API 尚未準備好'));
                            setTimeout(loop, 100);
                        })();
                    });
                }

                // chooseFolder 已移除（取消自訂下載位置）
                
                function resetSettings() {
                    if (confirm('重設為預設值？')) {
                        if (window.api) {
                            // 使用專門的重設API方法
                            window.api.reset_to_defaults().then(settings => {
                                console.log('重設為預設值:', settings);
                                currentSettings = settings;
                                updateUI();
                                showModal('成功', '已重設為預設值');
                            }).catch(error => {
                                console.error('重設失敗:', error);
                                showModal('錯誤', '重設失敗');
                            });
                        } else {
                            showModal('錯誤', 'API未初始化');
                        }
                    }
                }
                
                
                function showModal(title, message) {
                    document.getElementById('modal-title').textContent = title;
                    document.getElementById('modal-message').textContent = message;
                    document.getElementById('modal').style.display = 'block';
                }
                
                function closeModal() {
                    document.getElementById('modal').style.display = 'none';
                }
                
                
                // 快速初始化
                if (document.readyState === 'loading') {
                    document.addEventListener('DOMContentLoaded', loadSettings);
                } else {
                    loadSettings();
                }
            </script>
        </body>
        </html>
        """

def main():
    """主函數"""
    try:
        # 檢查是否已有QApplication實例
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        window = SettingsWindow()
        window.show()
        
        sys.exit(app.exec())
        
    except Exception as e:
        debug_console(f"啟動設定頁面失敗: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
