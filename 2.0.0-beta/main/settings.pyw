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
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(ROOT_DIR)

def debug_console(message):
    """控制台輸出"""
    print(f"[設定] {message}")

class SettingsApi(QObject):
    """設定頁面API類"""
    
    def __init__(self):
        super().__init__()
        self.root_dir = ROOT_DIR
        self.settings_file = os.path.join(self.root_dir, 'settings.json')
    
    @Slot(result=dict)
    def load_settings(self):
        """載入設定"""
        try:
            debug_console("載入設定中...")
            
            default_settings = {
                'downloadPath': 'downloads',  # 使用相對路徑，確保程式可移植性
                'enableNotifications': True
            }
            
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                # 處理下載路徑：如果是相對路徑，轉換為絕對路徑
                if 'downloadPath' in settings:
                    if not os.path.isabs(settings['downloadPath']):
                        settings['downloadPath'] = os.path.join(self.root_dir, settings['downloadPath'])
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
                'downloadPath': 'downloads',  # 使用相對路徑，確保程式可移植性
                'enableNotifications': True
            }
    
    @Slot(dict)
    def save_settings(self, settings):
        """儲存設定"""
        try:
            debug_console(f"收到儲存請求: {settings}")
            debug_console(f"設定檔案路徑: {self.settings_file}")
            
            # 處理下載路徑：如果是絕對路徑且位於程式目錄下，轉換為相對路徑
            if 'downloadPath' in settings:
                download_path = settings['downloadPath']
                debug_console(f"原始下載路徑: {download_path}")
                if os.path.isabs(download_path):
                    try:
                        # 嘗試將絕對路徑轉換為相對於程式目錄的路徑
                        rel_path = os.path.relpath(download_path, self.root_dir)
                        if not rel_path.startswith('..'):
                            settings['downloadPath'] = rel_path
                            debug_console(f"轉換為相對路徑: {rel_path}")
                    except ValueError:
                        # 如果無法轉換為相對路徑，保持絕對路徑
                        debug_console("無法轉換為相對路徑，保持絕對路徑")
                        pass
            
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
                'downloadPath': 'downloads',  # 使用相對路徑，確保程式可移植性
                'enableNotifications': True
            }
            debug_console(f"預設設定: {default_settings}")
            return default_settings
        except Exception as e:
            debug_console(f"重設為預設值失敗: {e}")
            return {
                'downloadPath': 'downloads',  # 使用相對路徑，確保程式可移植性
                'enableNotifications': True
            }

    @Slot(result=str)
    def select_download_path(self):
        """選擇下載路徑"""
        try:
            from PySide6.QtWidgets import QFileDialog
            
            current_path = self.load_settings().get('downloadPath', 'downloads')
            
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

    @Slot(str, str, result=str)
    def test_notification(self, title, message):
        """測試Toast通知功能"""
        try:
            if os.name == 'nt':  # Windows
                # 方法1: 嘗試使用Windows Toast API (最推薦)
                if self._try_windows_toast_api(title, message):
                    return "Windows Toast API通知已發送"
                
                # 方法2: 嘗試使用plyer (跨平台)
                if self._try_plyer_notification(title, message):
                    return "plyer通知已發送"
                
                # 方法3: 嘗試使用win10toast
                if self._try_win10toast(title, message):
                    return "win10toast通知已發送"
                
                # 方法4: 回退到MessageBox
                if self._try_messagebox_fallback(title, message):
                    return "MessageBox通知已發送"
                
                return "所有通知方法都失敗"
            else:
                # Linux/macOS
                try:
                    from plyer import notification
                    notification.notify(
                        title=title,
                        message=message,
                        timeout=5
                    )
                    return "plyer通知已發送"
                except:
                    return "通知功能僅支援Windows系統"
                
        except Exception as e:
            debug_console(f"測試通知失敗: {e}")
            return f"通知發送失敗: {e}"

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
        self.setFixedSize(800, 600)  # 減小視窗大小
        
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
                <h2>下載設定</h2>
                <div class="item">
                    <label class="label">下載目錄</label>
                    <div class="input-group">
                        <div class="path-display" id="download-path-display">正在載入...</div>
                        <button class="btn" onclick="selectDownloadPath()">選擇</button>
                    </div>
                </div>
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
                <button class="btn" onclick="testNotification()">測試通知</button>
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
                    downloadPath: '',
                    enableNotifications: true
                };
                
                function loadSettings() {
                    console.log('開始載入設定...');
                    if (window.qt && window.qt.webChannelTransport) {
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
                        console.error('WebChannel不可用');
                        updateUI();
                    }
                }
                
                function updateUI() {
                    const pathDisplay = document.getElementById('download-path-display');
                    if (pathDisplay) {
                        if (currentSettings.downloadPath && currentSettings.downloadPath !== '') {
                            pathDisplay.textContent = currentSettings.downloadPath;
                        } else {
                            // 如果沒有設定路徑，顯示預設路徑
                            pathDisplay.textContent = '正在載入預設路徑...';
                        }
                    }
                    
                    const notificationCheckbox = document.getElementById('enable-notifications');
                    if (notificationCheckbox) {
                        notificationCheckbox.checked = currentSettings.enableNotifications || true;
                    }
                }
                
                function selectDownloadPath() {
                    if (window.api) {
                        window.api.select_download_path().then(path => {
                            if (path) {
                                currentSettings.downloadPath = path;
                                updateUI();
                            }
                        }).catch(() => showModal('錯誤', '選擇路徑失敗'));
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
                    const pathDisplay = document.getElementById('download-path-display');
                    if (pathDisplay && pathDisplay.textContent !== '正在載入...' && pathDisplay.textContent !== '正在載入預設路徑...') {
                        currentSettings.downloadPath = pathDisplay.textContent;
                    }
                    
                    const notificationCheckbox = document.getElementById('enable-notifications');
                    if (notificationCheckbox) {
                        currentSettings.enableNotifications = notificationCheckbox.checked;
                    }
                }
                
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
                
                function testNotification() {
                    if (window.api) {
                        window.api.test_notification('測試通知', '這是一個測試通知，如果您看到此訊息，表示通知功能正常運作！').then(result => {
                            console.log('測試通知結果:', result);
                            showModal('測試通知', result);
                        }).catch(error => {
                            console.error('測試通知失敗:', error);
                            showModal('測試失敗', '通知測試失敗: ' + error);
                        });
                    } else {
                        showModal('錯誤', 'API未初始化');
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
