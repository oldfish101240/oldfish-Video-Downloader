import sys
import os
import configparser
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QLineEdit, QVBoxLayout, QSizePolicy, QHBoxLayout, QGridLayout, QMessageBox, QStackedWidget, QFrame, QDialog, QComboBox
from PySide6.QtGui import QPixmap, QIcon, QPalette, QColor
from PySide6.QtCore import Qt, QSize, QThread
from PySide6.QtCore import Signal
import yt_dlp
from urllib.parse import urlparse
import requests
from io import BytesIO


class AnsiCodes:
    OKBLUE = '\033[94m'
    FAIL = '\033[91m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'
    DEBUG = '\033[36m'


def info_console(message):
    print(f"{AnsiCodes.OKBLUE}[INFO]{AnsiCodes.ENDC} {message}")


def error_console(message):
    print(f"{AnsiCodes.FAIL}{AnsiCodes.BOLD}[ERROR]{AnsiCodes.ENDC} {message}")


def debug_console(message):
    print(f"{AnsiCodes.DEBUG}[DEBUG]{AnsiCodes.ENDC} {message}")


script_dir = os.path.dirname(__file__)
debug_console(f"腳本所在的目錄：{script_dir}")
assets_dir = f"{script_dir}/assets"
debug_console(f"資源所在的目錄：{assets_dir}")


def check_settings_file(filename=f'{script_dir}/settings.ini'):
    """檢查指定檔案是否存在於目前工作目錄。"""
    if os.path.exists(filename):
        info_console(f"偵測到設定檔 '{filename}' 已存在")
        return True  # 檔案存在，回傳 True
    else:
        error_console(f"偵測到設定檔 '{filename}' 不存在")
        return False  # 檔案不存在，回傳 False


def create_settings_file(filename=f'{script_dir}/settings.ini'):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            pass  # 創建一個空檔案，不寫入任何內容
        info_console(f"已創建新的設定檔 '{filename}'。")
        return True
    except IOError as e:
        error_console(f"無法創建設定檔 '{filename}'：{e}")
        return False


def message_box(parent, title, text, icon=QMessageBox.Icon.Information, close_parent=False):
    msg_box = QMessageBox(parent)
    msg_box.setWindowIcon(QIcon(f"{assets_dir}/icon.png"))  # 使用 icon.ico
    msg_box.setWindowTitle(title)
    msg_box.setText(f"<font color='white'>{text}</font>")
    msg_box.setIcon(icon)
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    for button in msg_box.buttons():
        if msg_box.standardButton(button) == QMessageBox.Ok:
            button.setStyleSheet("color: white;")
            break
    msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)  # 設定視窗置頂
    if msg_box.exec() == QMessageBox.StandardButton.Ok and close_parent:
        parent.close()  # 按下 OK 時關閉父視窗（僅當 close_parent 為 True 時）


class main_app(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("oldfish影片下載器")
        self.setFixedSize(900, 500)
        self.setWindowIcon(QIcon(f"{assets_dir}/icon.png"))
        self.setStyleSheet("background-color: #202124;")
        debug_console("視窗已初始化")

        self.central_widget = None
        self.create_ui()

    def create_ui(self):
        main_layout = QHBoxLayout(self)

        # 創建側邊欄 Widget
        self.sidebar = QWidget()
        sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar.setFixedWidth(200)  # 設定固定寬度
        self.sidebar.setStyleSheet("background-color: #333;")
        main_layout.setContentsMargins(0, 0, 0, 0)

        icon_path = os.path.join(os.path.dirname(__file__), "assets")

        button_style = """
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 10px 15px;
                text-align: left;
                color: white;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.20);  /* 20% 透明度的黑色 */
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.2);  /* 20% 透明度的白色 */
            }
            QPushButton:focus {
                outline: none;
            }
        """

        self.home_button = QPushButton("主頁")
        if os.path.exists(os.path.join(icon_path, "home.png")):
            self.home_button.setIcon(QIcon(os.path.join(icon_path, "home.png")))
            self.home_button.setIconSize(QSize(20, 20))
            self.home_button.setStyleSheet("QPushButton { padding-left: 35px; }" + button_style)  # 留出 icon 的空間
        else:
            self.home_button.setStyleSheet(button_style)
        self.home_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))

        self.queue_button = QPushButton("佇列")
        if os.path.exists(os.path.join(icon_path, "quene.png")):
            self.queue_button.setIcon(QIcon(os.path.join(icon_path, "quene.png")))
            self.queue_button.setIconSize(QSize(20, 20))
            self.queue_button.setStyleSheet("QPushButton { padding-left: 35px; }" + button_style)
        else:
            self.queue_button.setStyleSheet(button_style)
        self.queue_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))

        self.settings_button = QPushButton("設定")
        if os.path.exists(os.path.join(icon_path, "settings-sliders.png")):
            self.settings_button.setIcon(QIcon(os.path.join(icon_path, "settings-sliders.png")))
            self.settings_button.setIconSize(QSize(20, 20))
            self.settings_button.setStyleSheet("QPushButton { padding-left: 35px; }" + button_style)
        else:
            self.settings_button.setStyleSheet(button_style)
        self.settings_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))
        
        self.about_button = QPushButton("關於")
        if os.path.exists(os.path.join(icon_path, "about.png")):
            self.about_button.setIcon(QIcon(os.path.join(icon_path, "about.png")))
            self.about_button.setIconSize(QSize(20, 20))
            self.about_button.setStyleSheet("QPushButton { padding-left: 35px; }" + button_style)
        else:
            self.about_button.setStyleSheet(button_style)
        self.about_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(3))

        sidebar_layout.addWidget(self.home_button)
        sidebar_layout.addWidget(self.queue_button)
        sidebar_layout.addStretch(1)  # 在前兩個按鈕和設定按鈕之間添加彈性空間
        sidebar_layout.addWidget(self.settings_button)
        sidebar_layout.addWidget(self.about_button)

        main_layout.addWidget(self.sidebar)

        # 創建中央內容 Widget (使用堆疊佈局)
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget, stretch=3)
        self.setLayout(main_layout)

        # 創建主頁面
        self.home_page = QWidget()
        self.home_page_ui()
        self.stacked_widget.addWidget(self.home_page)

        # 創建佇列頁面
        self.queue_page = QWidget()
        self.queue_page_ui()
        self.stacked_widget.addWidget(self.queue_page)

        # 創建設定頁面
        self.settings_page = QWidget()
        self.settings_page_ui()
        self.stacked_widget.addWidget(self.settings_page)
        
        # 創建關於頁面
        self.about_page = QWidget()
        self.about_page_ui()
        self.stacked_widget.addWidget(self.about_page)

        # 初始顯示主頁面
        self.stacked_widget.setCurrentIndex(0)

    def home_page_ui(self):

        self.image_label = QLabel(self.home_page)
        pixmap = QPixmap(f"{script_dir}/assets/icon_text.png")
        self.image_label.setPixmap(pixmap)
        scale_factor = 0.5
        new_width = int(pixmap.width() * scale_factor)
        new_height = int(pixmap.height() * scale_factor)
        scaled_pixmap = pixmap.scaled(new_width, new_height, Qt.AspectRatioMode.KeepAspectRatio)
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.setGeometry(70 ,130 ,535 , 105)
        
        self.about_slogan = QLabel("一個安全、方便、完全免費的影片下載器", self.home_page)
        self.about_slogan.setStyleSheet("color: gray; font-size: 20px; font-weight: bold;")
        self.about_slogan.setGeometry(165, 250, 360, 20)
        
        
        self.url_input = QLineEdit(self.home_page)
        self.url_input.setPlaceholderText("請輸入影片網址")
        self.url_input.setStyleSheet("background-color: dimgray;")
        self.url_input.setGeometry(160, 300, 300, 30)
        
        
        self.downlaod_button = QPushButton("下載", self.home_page)
        self.downlaod_button.setStyleSheet("background-color: lightgreen; color: black;")
        self.downlaod_button.setGeometry(460, 300, 75, 30)
        self.downlaod_button.clicked.connect(self.start_download)
        
        


    def queue_page_ui(self):
        
        self.queue_title = QLabel("佇列", self.queue_page)
        self.queue_title.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        self.queue_title.setGeometry(10, 10, 50, 30)
        
        self.quene_separator = QWidget(self.queue_page)
        self.quene_separator.setFixedHeight(1)
        self.quene_separator.setStyleSheet("background-color: gray;")
        self.quene_separator.setGeometry(10, 45, 670, 5)

    def settings_page_ui(self):
        
        self.settings_title = QLabel("設定", self.settings_page)
        self.settings_title.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        self.settings_title.setGeometry(10, 10, 50, 30)
        
        self.settings_separator = QWidget(self.settings_page)
        self.settings_separator.setFixedHeight(1)
        self.settings_separator.setStyleSheet("background-color: gray;")
        self.settings_separator.setGeometry(10, 45, 670, 5)
        
        
    def about_page_ui(self):
        
        self.image_label = QLabel(self.about_page)
        pixmap = QPixmap(f"{script_dir}/assets/icon_text.png")
        self.image_label.setPixmap(pixmap)
        scale_factor = 0.5
        new_width = int(pixmap.width() * scale_factor)
        new_height = int(pixmap.height() * scale_factor)
        scaled_pixmap = pixmap.scaled(new_width, new_height, Qt.AspectRatioMode.KeepAspectRatio)
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.setGeometry(70, 100, 535 , 105)
        
        self.about_slogan = QLabel("一個安全、方便、完全免費的影片下載器", self.about_page)
        self.about_slogan.setStyleSheet("color: gray; font-size: 20px; font-weight: bold;")
        self.about_slogan.setGeometry(165, 220, 360, 20)
        
        self.about_label = QLabel("版本：2.0.0-beta1\n作者：老魚oldfish\n發布日期：2025年00月00日\n授權：MIT", self.about_page)
        self.about_label.setStyleSheet("color: white; font-size: 16px;")
        self.about_label.setGeometry(80, 350, 300, 100)
        
        self.github_link = QLabel('<a href="https://github.com/oldfish101240/oldfish-Video-Downloader">前往GitHub頁面</a>', self.about_page)
        self.github_link.setOpenExternalLinks(True)  # 啟用外部連結
        self.github_link.setStyleSheet("font-size: 16px;")
        self.github_link.setGeometry(490, 410, 120, 30)



    def start_download(self):
        video_url = self.url_input.text().strip()  # 獲取網址並移除前後空白

        # 步驟 1: 檢查網址是否為空
        if not video_url:
            self.show_error_message("請輸入影片網址")
            return  # 如果網址為空，直接結束這個方法的執行

        # 步驟 2: 檢查網址是否以 "https://www.youtube.com" 開頭
        if not video_url.startswith("https://www.youtube.com"):
            self.show_warning_message("偵測到您輸入的網址不是YouTube影片的網址，正確的網址應該以此為開頭：https://www.youtube.com。")
            return

        self.video_info_dialog = VideoInfoDialog(self) # 創建空的資訊視窗
        self.video_info_dialog.show()

        self.info_loader_thread = InfoLoader(video_url)
        self.info_loader_thread.finished.connect(self.video_info_dialog.info_loaded.emit) # 載入完成發送信號給對話框
        self.info_loader_thread.error.connect(self.handle_info_load_error)
        self.info_loader_thread.start()
        
    def handle_info_load_error(self, error_message):
        if hasattr(self, 'video_info_dialog') and self.video_info_dialog.isVisible():
            self.video_info_dialog.setWindowTitle("錯誤")
            self.video_info_dialog.loading_label.setText(f"載入錯誤：{error_message}")    
        

    def get_video_info(self, video_url):
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # 僅提取基本資訊
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)  # download=False 表示不下載
                if info:
                    self.show_video_info_dialog(info)
                else:
                    self.show_error_message("無法獲取影片資訊。")
        except Exception as e:
            self.show_error_message(f"獲取影片資訊時發生錯誤：{e}")




    def download_video(self, video_url, download_format='bestvideo+bestaudio/best'):
        ydl_opts = {
            'outtmpl': '%(title)s.%(ext)s',
            'format': download_format, # 使用傳遞的畫質格式
            'progress_hooks': [self.progress_hook],
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            message_box(self, "下載完成", "影片下載完成！", QMessageBox.Icon.Information)
        except yt_dlp.DownloadError as e:
            error_console(f"下載錯誤：{e}")
            message_box(self, "下載錯誤", f"下載影片時發生錯誤：{e}", QMessageBox.Icon.Critical)
     
    def progress_hook(self, d):
        if d['status'] == 'downloading':
            percent = d['_percent_str']
            speed = d['_speed_str']
            eta = d['_eta_str']
            info_console(f"下載進度：{percent}, 速度：{speed}, 剩餘時間：{eta}")
            # 在這裡更新你的 UI 進度條 (如果有的話)
        elif d['status'] == 'finished':
            info_console(f"下載完成：{d['filename']}")     
            
    
    def is_valid_url(self, url):
        """檢查網址是否具有基本的有效格式。"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False

    def is_supported_url(self, url):
        """只檢查網址是否以 https://www.youtube.com 開頭。"""
        return url.startswith("https://www.youtube.com")

    def show_error_message(self, text):
        """顯示錯誤訊息的輔助函數。"""
        message_box(self, "錯誤", text, QMessageBox.Icon.Warning, close_parent=False)

    def show_warning_message(self, text):
        """顯示警告訊息的輔助函數。"""
        message_box(self, "提示", text, QMessageBox.Icon.Information, close_parent=False)
        
            
class InfoLoader(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, video_url):
        super().__init__()
        self.video_url = video_url
        

    def run(self):
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'format': 'bestvideo*+bestaudio/best',
            'listformats': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.video_url, download=False)
                if info:
                    formats = info.get('formats', [])
                    resolutions_dict = {}
                    for f in formats:
                        if f.get('vbr') and f.get('width') and f.get('height'):
                            width = f['width']
                            height = f['height']
                            resolution_str = f"{width}x{height}"
                            aspect_ratio = width / height

                            display_resolution = resolution_str
                            if abs(aspect_ratio - (16 / 9)) < 0.01 or abs(aspect_ratio - (9 / 16)) < 0.01:
                                display_resolution = f"{height}p"
                            elif abs(aspect_ratio - (4 / 3)) < 0.01 or abs(aspect_ratio - (3 / 4)) < 0.01:
                                display_resolution = f"{height}p (4:3)"

                            if display_resolution not in resolutions_dict:
                                resolutions_dict[display_resolution] = resolution_str

                    info['display_resolutions'] = sorted(list(resolutions_dict.keys()), reverse=True)
                    info['original_resolutions'] = resolutions_dict
                    self.finished.emit(info)
                else:
                    self.error.emit("無法獲取影片資訊。")
        except Exception as e:
            self.error.emit(f"獲取影片資訊時發生錯誤：{e}")
    
            
class VideoInfoDialog(QDialog):
    info_loaded = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        info_console("VideoInfoDialog __init__ 被呼叫")
        info_console("載入影片資訊中...")
        self.setWindowTitle("影片詳細資訊")
        self.setFixedSize(600, 400)
        self.setWindowIcon(QIcon(f"{assets_dir}/icon.png"))
        self.setStyleSheet("background-color: #202124;")
        self.info = None
        self.download_url = None

        self.loading_label = QLabel("載入中，請稍候...", self)
        self.loading_label.setStyleSheet("color: white; font-size: 18px;")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setGeometry(10, 10, 580, 380) # 佔據整個視窗

        self.title_label = QLabel(self)
        self.title_label.setStyleSheet("color: white; font-size: 20px; font-weight: bold;")
        self.title_label.setWordWrap(True)

        self.thumbnail_label = QLabel(self)
        self.thumbnail_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.duration_label = QLabel(self)
        self.duration_label.setStyleSheet("color: white; font-size: 16px;")

        self.confirm_button = QPushButton("確認下載", self)
        self.confirm_button.clicked.connect(self.start_download)
        self.confirm_button.setStyleSheet("background-color: lightgreen; color: black;")

        self.cancel_button = QPushButton("取消", self)
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setStyleSheet("background-color: dimgray; color: white;")
        
        self.resolution_label = QLabel("選擇畫質:", self)
        self.resolution_label.setStyleSheet("color: white;")
        self.resolution_combo = QComboBox(self)
        self.resolution_combo.setStyleSheet("color: white; background-color: gray;")
        

        # 初始時隱藏資訊相關的 widget
        self.title_label.hide()
        self.thumbnail_label.hide()
        self.duration_label.hide()
        self.confirm_button.hide()
        self.cancel_button.hide()
        self.resolution_label.hide()
        self.resolution_combo.hide()

        self.info_loaded.connect(self.update_ui)

    def update_ui(self, info):
        
        self.info = info
        self.download_url = self.info.get('webpage_url')

        title = self.info.get('title', '未知')
        max_title_length = 29
        if len(title) > max_title_length:
            title = title[:max_title_length] + "..."
        self.setWindowTitle("影片詳細資訊")
        self.title_label.setText(title)

        thumbnail_url = self.info.get('thumbnail')
        if (thumbnail_url):
            try:
                response = requests.get(thumbnail_url)
                response.raise_for_status()
                image = QPixmap()
                image.loadFromData(BytesIO(response.content).read())
                scaled_image = image.scaled(QSize(200, 200), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
                self.thumbnail_label.setPixmap(scaled_image)
            except requests.exceptions.RequestException as e:
                error_console(f"無法載入縮略圖：{e}")
                self.thumbnail_label.setText("無法載入縮略圖")
                self.thumbnail_label.setStyleSheet("color: gray; font-size: 24px; font-weight: bold;")
        else:
            self.thumbnail_label.setText("無縮略圖")
            self.thumbnail_label.setStyleSheet("color: gray; font-size: 24px; font-weight: bold;")

        duration = self.info.get('duration')
        duration_str = f"{duration // 60}:{duration % 60}" if duration else "長度：未知"
        self.duration_label.setText(duration_str)
        self.duration_label.setStyleSheet("color: gray; font-size: 16px;")

        # 重新佈局或使用setGeometry顯示 widget
        self.loading_label.hide()
        self.title_label.setGeometry(230, 45, 300, 45)
        self.thumbnail_label.setGeometry(10, 0, 200, 200)
        self.duration_label.setGeometry(230, 95, 300, 20)
        self.confirm_button.setGeometry(470, 360, 120, 30)
        self.cancel_button.setGeometry(360, 360, 110, 30)
        self.resolution_label.setGeometry(10, 210, 100, 30)
        self.resolution_combo.setGeometry(70, 210, 200, 30)
        
        display_resolutions = info.get('display_resolutions', [])
        self.original_resolutions = info.get('original_resolutions', {})
        
        
        info_console("影片資訊載入完成")

        self.title_label.show()
        self.thumbnail_label.show()
        self.duration_label.show()
        self.confirm_button.show()
        self.cancel_button.show()
        
        if display_resolutions:
            self.resolution_label.show()
            self.resolution_combo.clear()
            self.resolution_combo.addItems(display_resolutions)
            self.resolution_combo.show()
        else:
            self.resolution_label.hide()
            self.resolution_combo.hide()

    def start_download(self):
        selected_display_resolution = self.resolution_combo.currentText()
        original_resolution = self.original_resolutions.get(selected_display_resolution)

        download_format = 'bestvideo+bestaudio/best'
        if original_resolution:
            download_format = f'bestvideo[res*={original_resolution}]+bestaudio/best'

        if self.download_url:
            main_window.download_video(self.download_url, download_format=download_format)
            self.accept()
        else:
            message_box(self, "錯誤", "無法獲取下載網址。", QMessageBox.Icon.Critical)




            
            
                   
        
        



if __name__ == '__main__':
    settings_file = f'{script_dir}/settings.ini'

    if check_settings_file():
        info_console("程式將繼續運行")
    else:
        info_console("即將創建新的設定檔")
        if create_settings_file(settings_file):
            info_console("設定檔已成功創建")
        else:
            error_console("無法創建設定檔")

    app = QApplication(sys.argv)
    main_window = main_app()
    main_window.show()
    exit_code = app.exec()  # 應用程式事件迴圈在此開始並等待結束
    debug_console(f"偵測到視窗已關閉，退出代碼：{exit_code}")
    info_console("正在結束程式...")
    # ... 其他結束時需要執行的程式碼 ...
    sys.exit(exit_code)
