from PyQt6.QtWidgets import QApplication, QMainWindow, QLineEdit, QPushButton, QMessageBox, QVBoxLayout, QWidget, QHBoxLayout, QLabel, QDialog, QProgressBar, QComboBox, QTabWidget, QFormLayout, QCheckBox, QSpinBox, QSpacerItem, QSizePolicy
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
import sys
import os
import requests
from io import BytesIO
import logging
from yt_dlp import YoutubeDL
import zipfile
import concurrent.futures
import winsound
import time

# 設定日誌
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

def get_assets_dir():
    """取得 assets 資料夾的路徑，支援 exe 環境"""
    if getattr(sys, 'frozen', False):  # 判斷是否為打包後的 .exe
        return os.path.join(os.path.dirname(sys.executable), "assets")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

def show_message_box(parent, title, text, icon=QMessageBox.Icon.Information, close_parent=False):
    """通用的訊息框，套用 icon.ico，並根據參數決定是否關閉父視窗"""
    assets_dir = get_assets_dir()  # 使用通用方法取得 assets 資料夾路徑
    msg_box = QMessageBox(parent)
    msg_box.setWindowIcon(QIcon(os.path.join(assets_dir, "icon.ico")))  # 使用 icon.ico
    msg_box.setWindowTitle(title)
    msg_box.setText(text)
    msg_box.setIcon(icon)
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)  # 設定視窗置頂
    if msg_box.exec() == QMessageBox.StandardButton.Ok and close_parent:
        parent.close()  # 按下 OK 時關閉父視窗（僅當 close_parent 為 True 時）

class DownloadWorker(QThread):
    progress_updated = pyqtSignal(int, float, float)  # percent, bytes_received, speed
    download_finished = pyqtSignal()
    download_failed = pyqtSignal(str)

    def __init__(self, url, output_path, cancel_callback):
        super().__init__()
        self.url = url
        self.output_path = output_path
        self.cancel_callback = cancel_callback
        self.last_update_time = 0  # 用於控制更新頻率

    def run(self):
        max_retries = 3  # 最大重試次數
        retry_count = 0

        while retry_count < max_retries:
            try:
                response = requests.get(self.url, stream=True, timeout=10)
                total_size = int(response.headers.get('content-length', 0))
                bytes_received = 0
                start_time = time.time()

                with open(self.output_path, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=1024):
                        if self.cancel_callback():
                            # 刪除部分下載的檔案
                            file.close()  # 確保檔案已關閉
                            if os.path.exists(self.output_path):
                                os.remove(self.output_path)
                            return
                        file.write(chunk)
                        bytes_received += len(chunk)
                        elapsed_time = time.time() - start_time
                        speed = bytes_received / elapsed_time if elapsed_time > 0 else 0
                        percent = int(bytes_received * 100 / total_size) if total_size > 0 else 0

                        # 每秒更新一次進度
                        current_time = time.time()
                        if current_time - self.last_update_time >= 1:
                            self.progress_updated.emit(percent, bytes_received, speed)
                            self.last_update_time = current_time

                self.download_finished.emit()
                return  # 成功下載後退出
            except requests.exceptions.RequestException as e:
                retry_count += 1
                logging.warning(f"下載失敗，正在重試 ({retry_count}/{max_retries})：{e}")
                time.sleep(2)  # 等待 2 秒後重試

        # 如果達到最大重試次數仍失敗
        if os.path.exists(self.output_path):
            os.remove(self.output_path)
        self.download_failed.emit("下載失敗：伺服器超時或其他錯誤")
        self._notify_user_and_exit()

    def _notify_user_and_exit(self):
        """提醒用戶重新啟動程式，並結束程式"""
        assets_dir = get_assets_dir()
        msg_box = QMessageBox()
        msg_box.setWindowIcon(QIcon(os.path.join(assets_dir, "icon.ico")))  # 使用 icon.ico
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("下載失敗")
        msg_box.setText("伺服器超時或其他錯誤，請重新啟動程式。")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()
        sys.exit()


class Installer(QWidget):
    # 新增信號，用於通知安裝完成
    installation_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        # 初始化 base_dir，確保在 exe 和非 exe 環境中都能正確取得主程式目錄
        if getattr(sys, 'frozen', False):  # 判斷是否為打包後的 .exe
            self.base_dir = os.path.dirname(sys.executable)  # .exe 檔案所在目錄
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))  # 原始腳本所在目錄

        self.assets_dir = get_assets_dir()  # 使用通用方法取得 assets 資料夾路徑
        self.setWindowIcon(QIcon(os.path.join(self.assets_dir, "icon.ico")))  # 套用 icon.ico
        self.cancel_flag = False  # 初始化取消標誌
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)  # 設定視窗置頂
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)  # 禁用關閉按鈕
        self.initUI()

    def initUI(self):
        self.setWindowTitle('安裝資訊')
        self.setFixedSize(400, 140)  # 調整視窗高度
        layout = QVBoxLayout()

        winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)

        reply = QMessageBox(self)
        reply.setWindowIcon(QIcon(os.path.join(self.assets_dir, "icon.ico")))  # 使用 icon.ico
        reply.setWindowTitle('安裝資訊')
        reply.setText('FFmpeg 是影片下載器必要的元件。\n是否要下載並安裝？')
        reply.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        reply.setIcon(QMessageBox.Icon.Question)
        reply.setWindowFlags(reply.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)  # 設定視窗置頂
        user_reply = reply.exec()

        if (user_reply == QMessageBox.StandardButton.Yes):
            # 定義跟目錄為主程式所在的資料夾
            self.ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            self.ffmpeg_zip = os.path.join(self.base_dir, "ffmpeg.zip")  # 壓縮檔下載到基底目錄
            self.ffmpeg_extract_dir = os.path.join(self.base_dir, "ffmpeg-7.1.1-essentials_build")  # 解壓縮目錄
            print(f"FFmpeg 壓縮檔將下載到：{self.ffmpeg_zip}")
            print(f"FFmpeg 將解壓縮到：{self.ffmpeg_extract_dir}")
            self.progress_label = QLabel("安裝中...")
            layout.addWidget(self.progress_label)

            # 速度與已安裝/總大小的佈局
            info_layout = QHBoxLayout()
            self.speed_label = QLabel("")
            info_layout.addWidget(self.speed_label)
            info_layout.addStretch()
            self.size_label = QLabel("0.00 MB / 0.00 MB")  # 只顯示數字
            info_layout.addWidget(self.size_label)  # 修正此行，添加正確的 widget
            layout.addLayout(info_layout)  # 添加 info_layout 到主佈局

            self.progress_bar = QProgressBar()
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #777;
                    border-radius: 5px;
                    text-align: center;
                }

                QProgressBar::chunk {
                    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                        stop: 0 #8FBC8F, stop: 1 #2E8B57);
                    border-radius: 3px;
                    margin: 2px;
                }
            """)
            layout.addWidget(self.progress_bar)

            button_layout = QHBoxLayout()
            button_layout.addStretch()
            self.cancel_button = QPushButton("取消")
            self.cancel_button.clicked.connect(self.cancel_download)
            button_layout.addWidget(self.cancel_button)
            layout.addLayout(button_layout)

            self.start_download()
        else:
            sys.exit()

        self.setLayout(layout)

    def start_download(self):
        # 獲取 FFmpeg 壓縮檔的大小
        try:
            response = requests.head(self.ffmpeg_url, timeout=10, allow_redirects=True)
            response.raise_for_status()  # 檢查 HTTP 狀態碼
            content_length = response.headers.get('content-length')
            if (content_length is None):
                raise ValueError("無法獲取檔案大小")
            self.ffmpeg_zip_size = int(content_length)  # 確保總大小正確顯示
            self.size_label.setText(f"0.00 MB / {self.ffmpeg_zip_size / (1024 * 1024):.2f} MB")  # 初始化總大小
        except requests.exceptions.RequestException as e:
            show_message_box(self, '錯誤', f'連線錯誤：{e}', QMessageBox.Icon.Critical)
            self.close()
            return
        except ValueError as e:
            show_message_box(self, '錯誤', f'無法獲取檔案大小：{e}', QMessageBox.Icon.Critical)
            self.close()
            return

        # 啟動下載執行緒
        self.download_worker = DownloadWorker(
            self.ffmpeg_url,
            self.ffmpeg_zip,
            lambda: self.cancel_flag
        )
        self.download_worker.progress_updated.connect(self._update_progress_ui)
        self.download_worker.download_finished.connect(self.on_download_finished)
        self.download_worker.download_failed.connect(self.on_download_failed)
        self.download_worker.start()

    def _update_progress_ui(self, percent, bytes_received, speed):
        # 修正格式化錯誤
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{percent}%")  # 顯示百分比文字
        # 更新已下載大小與總大小
        self.size_label.setText(f"{bytes_received / (1024 * 1024):.2f} MB / {self.ffmpeg_zip_size / (1024 * 1024):.2f} MB")
        # 更新下載速度
        if speed > 1024 * 1024:
            self.speed_label.setText(f"速度：{speed / (1024 * 1024):.2f} MB/s")
        elif speed > 1024:
            self.speed_label.setText(f"速度：{speed / 1024:.2f} KB/s")
        else:
            self.speed_label.setText(f"速度：{speed:.2f} B/s")

    def on_download_finished(self):
        # 解壓縮並完成安裝
        try:
            with zipfile.ZipFile(self.ffmpeg_zip, 'r') as zip_ref:
                zip_ref.extractall(self.ffmpeg_extract_dir)
            os.remove(self.ffmpeg_zip)
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
            show_message_box(self, '安裝完成', 'FFmpeg 安裝完成，請重新啟動此程式。', QMessageBox.Icon.Information)
            self.installation_finished.emit()
            self.close()
        except Exception as e:
            show_message_box(self, '錯誤', f'解壓縮失敗：{e}', QMessageBox.Icon.Critical)

    def on_download_failed(self, error_message):
        show_message_box(self, '錯誤', f'下載失敗：{error_message}', QMessageBox.Icon.Critical)
        self.cleanup_partial_download()

    def cancel_download(self):
        self.cancel_flag = True
        self.cleanup_partial_download()
        sys.exit()

    def cleanup_partial_download(self):
        # 刪除部分下載的文件
        try:
            if (os.path.exists(self.ffmpeg_zip)):
                time.sleep(1)
                os.remove(self.ffmpeg_zip)
        except Exception as e:
            pass


class VideoInfoLoaderThread(QThread):
    video_info_loaded = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            with YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(self.url, download=False)
                self.video_info_loaded.emit(info)
        except Exception as e:
            error_message = "找不到影片，請檢查是否輸入正確的網址"
            self.error_occurred.emit(error_message)


class VideoDownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.assets_dir = get_assets_dir()  # 使用通用方法取得 assets 資料夾路徑
        self.setWindowTitle("oldfish 影片下載器")
        self.setWindowIcon(QIcon(os.path.join(self.assets_dir, "icon.ico")))  # 套用 icon.ico
        self.setFixedSize(400, 100)  # 調整視窗高度
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)  # 取消置頂

        # 動態獲取圖示路徑
        icon_path = os.path.join(self.assets_dir, "icon.ico")
        settings_icon_path = os.path.join(self.assets_dir, "settings_icon.png")
        folder_icon_path = os.path.join(self.assets_dir, "folder_icon.png")  # 資料夾圖案

        # 設定視窗圖示
        self.setWindowIcon(QIcon(icon_path))

        self.default_download_path = self.load_default_download_path()  # 初始化下載路徑
        self.append_resolution = False  # 初始化是否加上解析度的設定

        # 主視窗佈局
        main_layout = QVBoxLayout()

        # 左上角的下載資料夾按鈕
        top_layout = QHBoxLayout()
        self.open_folder_button = QPushButton("開啟下載資料夾")
        self.open_folder_button.setIcon(QIcon(folder_icon_path))  # 使用資料夾圖案
        self.open_folder_button.setFixedSize(150, 30)  # 調整按鈕大小
        self.open_folder_button.setStyleSheet("text-align: left; padding-left: 8px;")  # 圖片與文字對齊
        self.open_folder_button.clicked.connect(self.open_downloads_folder)
        top_layout.addWidget(self.open_folder_button)

        # 右上角的設定按鈕
        self.settings_button = QPushButton()
        self.settings_button.setIcon(QIcon(settings_icon_path))  # 使用 PNG 圖示
        self.settings_button.setFixedSize(30, 30)  # 設定按鈕大小
        self.settings_button.clicked.connect(self.open_settings)
        top_layout.addStretch()
        top_layout.addWidget(self.settings_button)
        main_layout.addLayout(top_layout)

        # 網址列與下載按鈕
        url_layout = QHBoxLayout()
        self.url_entry = QLineEdit()
        self.url_entry.setPlaceholderText("輸入影片網址...")  # 設定預設提示文字
        self.url_entry.mousePressEvent = self.select_all_text  # 新增點擊事件
        url_layout.addWidget(self.url_entry)

        self.download_button = QPushButton("下載")
        self.download_button.setFixedSize(80, 30)  # 縮短按鈕
        self.download_button.clicked.connect(self.show_video_info)
        url_layout.addWidget(self.download_button)
        main_layout.addLayout(url_layout)

        # 設定中心 Widget
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def load_default_download_path(self):
        """從設定檔中加載下載路徑，若不存在則使用預設值"""
        if getattr(sys, 'frozen', False):  # 判斷是否為打包後的 .exe
            base_dir = os.path.dirname(sys.executable)  # .exe 檔案所在目錄
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))  # 原始腳本所在目錄

        settings_file = os.path.join(base_dir, "settings.txt")  # 確保路徑正確
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:  # 使用 UTF-8 編碼讀取
                    for line in f:
                        if line.startswith("download_path="):
                            download_path = line.split("=", 1)[1].strip()
                            if os.path.exists(download_path):  # 確保路徑有效
                                return download_path
                            else:
                                logging.warning(f"設定檔中的下載路徑無效：{download_path}，將使用預設路徑。")
            except UnicodeDecodeError as e:
                logging.error(f"讀取設定檔時發生編碼錯誤：{e}")
                show_message_box(self, "錯誤", "讀取設定檔失敗，請檢查檔案編碼是否為 UTF-8。", QMessageBox.Icon.Critical)
        return os.path.join(base_dir, "downloads")  # 預設下載路徑

    def show_video_info(self):
        url = self.url_entry.text()
        if not url:
            show_message_box(self, "警告", "請輸入影片網址！", QMessageBox.Icon.Warning, close_parent=False)
            return

        if "youtube.com/watch" not in url and "youtu.be/" not in url and "youtube.com/shorts" not in url:
            show_message_box(self, "警告", "請輸入有效的 YouTube 影片網址或 Shorts 網址！", QMessageBox.Icon.Warning, close_parent=False)
            return

        # 開啟影片資訊視窗
        self.video_info_window = VideoInfoDialog(url, parent=self, download_path=self.default_download_path)
        self.video_info_window.append_resolution = self.append_resolution  # 傳遞是否加上解析度的設定
        self.video_info_window.show()

    def open_downloads_folder(self):
        """開啟下載資料夾"""
        downloads_dir = self.default_download_path

        if not os.path.exists(downloads_dir):
            os.makedirs(downloads_dir)
        os.startfile(downloads_dir)

    def open_settings(self):
        settings_dialog = SettingsDialog(self)
        if (settings_dialog.exec()):
            # 更新設定
            self.default_download_path = settings_dialog.download_path_entry.toolTip()
            self.append_resolution = settings_dialog.append_resolution_checkbox.isChecked()

    def select_all_text(self, event):
        self.url_entry.selectAll()


class DownloadThread(QThread):
    progress = pyqtSignal(int)  # 發送進度百分比
    status = pyqtSignal(str)    # 發送狀態訊息
    already_downloaded = pyqtSignal()  # 新增信號，用於通知已下載過

    def __init__(self, url, ydl_opts, parent=None):
        super().__init__(parent)
        self.url = url
        self.ydl_opts = ydl_opts

    def run(self):
        try:
            print(f"開始下載：{self.url}")  # 除錯訊息
            with YoutubeDL(self.ydl_opts) as ydl:
                ydl.add_default_info_extractors()
                ydl.params['logger'] = self  # 使用自訂 logger
                ydl.download([self.url])
            print(f"下載完成：{self.url}")  # 除錯訊息
        except Exception as e:
            logging.error(f"下載失敗：{e}")

    def debug(self, msg):
        # 檢查是否包含「has already been downloaded」
        if ("has already been downloaded" in msg):
            self.already_downloaded.emit()

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


class VideoInfoDialog(QDialog):
    def __init__(self, url, parent=None, download_path=None):
        super().__init__(parent)
        self.assets_dir = get_assets_dir()  # 使用通用方法取得 assets 資料夾路徑
        self.setWindowIcon(QIcon(os.path.join(self.assets_dir, "icon.ico")))  # 使用 icon.ico
        self.setWindowTitle("影片資訊")
        self.setFixedSize(400, 250)  # 確保視窗大小正確
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)  # 取消置頂
        self.url = url
        self.parent = parent
        self.download_path = download_path  # 儲存下載路徑
        self.original_height = 200  # 儲存原始高度
        self.expanded_height = 250  # 設定下載時的高度
        self.already_downloaded_flag = False  # 新增標誌，用於判斷是否已下載過
        self.append_resolution = False  # 新增屬性，控制是否在檔名後加上解析度

        # 初始化主佈局
        self.main_layout = QVBoxLayout()  # 修正未定義 main_layout 的問題

        # 縮圖與資訊佈局
        self.info_layout = QHBoxLayout()

        # 縮圖
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(120, 90)  # 固定縮圖大小
        self.info_layout.addWidget(self.thumbnail_label)

        # 資訊區域
        self.info_label = QLabel()
        self.info_label.setStyleSheet("font-size: 14px;")
        self.info_label.setWordWrap(True)  # 啟用換行
        self.info_layout.addWidget(self.info_label)

        self.main_layout.addLayout(self.info_layout)

        # 載入中訊息
        self.loading_label = QLabel("正在載入...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.loading_label)

        # 解析度與副檔名選擇
        self.resolution_dropdown = QComboBox()
        self.resolution_dropdown.setEnabled(False)  # 載入完成前禁用
        self.extension_dropdown = QComboBox()
        self.extension_dropdown.addItems(["MP4", "MP3"])
        self.extension_dropdown.setEnabled(False)  # 載入完成前禁用
        self.extension_dropdown.currentTextChanged.connect(self.toggle_resolution_dropdown)

        self.form_layout = QFormLayout()
        self.form_layout.addRow("選擇解析度：", self.resolution_dropdown)
        self.form_layout.addRow("選擇檔案格式：", self.extension_dropdown)
        self.main_layout.addLayout(self.form_layout)

        # 狀態標籤與進度條
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.hide()
        self.main_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)  # 確保進度條範圍為 0 到 100
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #777;
                border-radius: 5px;
                text-align: center;
            }

            QProgressBar::chunk {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #8FBC8F, stop: 1 #2E8B57);
                border-radius: 3px;
                margin: 2px;
            }
        """)
        self.progress_bar.hide()
        self.main_layout.addWidget(self.progress_bar)

        # 下載按鈕
        self.download_button = QPushButton("開始下載")
        self.download_button.setEnabled(False)  # 載入完成前禁用
        self.download_button.clicked.connect(self.download_video)
        self.main_layout.addWidget(self.download_button)

        self.setLayout(self.main_layout)  # 設定主佈局

        # 啟動執行緒載入影片資料
        self.loader_thread = VideoInfoLoaderThread(self.url, self)
        self.loader_thread.video_info_loaded.connect(self.update_video_info)
        self.loader_thread.error_occurred.connect(self.on_load_error)
        self.loader_thread.start()

        self.download_thread = None  # 初始化下載執行緒

    def update_video_info(self, info):
        # 更新影片資訊
        title = info.get('title', '未知標題')
        thumbnail_url = info.get('thumbnail', '')
        uploader = info.get('uploader', '未知頻道')
        duration = info.get('duration', 0)

        # 格式化資訊內容
        formatted_duration = self.format_duration(duration)
        self.info_label.setText(
            f"<b style='font-size: 16px;'>{title}</b><br>"
            f"<span style='font-size: 12px; color: gray;'>{uploader}</span><br>"
            f"<span style='font-size: 12px; color: gray;'>{formatted_duration}</span>"
        )

        # 設定縮圖
        try:
            if (thumbnail_url):
                response = requests.get(thumbnail_url, timeout=10)
                response.raise_for_status()
                pixmap = QPixmap()
                pixmap.loadFromData(BytesIO(response.content).read())
                scaled_pixmap = pixmap.scaled(120, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.thumbnail_label.setPixmap(scaled_pixmap)
            else:
                self.thumbnail_label.setText("無法載入縮圖")
        except Exception as e:
            self.thumbnail_label.setText("無法載入縮圖")

        # 動態更新解析度選單
        available_resolutions = self.get_available_resolutions(info)
        self.resolution_dropdown.clear()
        self.resolution_dropdown.addItems(available_resolutions)
        self.resolution_dropdown.setCurrentText("1080p" if "1080p" in available_resolutions else available_resolutions[0])
        self.resolution_dropdown.setEnabled(True)

        # 隱藏載入中訊息，啟用解析度與副檔名選擇，顯示下載按鈕
        self.loading_label.hide()
        self.extension_dropdown.setEnabled(True)
        self.download_button.setEnabled(True)

    def get_available_resolutions(self, info):
        """從影片資訊中提取可用的解析度清單，並映射到常見解析度名稱"""
        formats = info.get('formats', [])
        resolutions = set()
        resolution_map = {
            2160: "2160p (4K)",
            1440: "1440p (2K)",
            1080: "1080p",
            720: "720p",
            480: "480p",
            360: "360p",
            240: "240p",
            144: "144p"
        }

        for fmt in formats:
            if fmt.get('vcodec') != 'none':  # 確保是影片格式
                height = fmt.get('height')
                width = fmt.get('width')
                if height and width:
                    aspect_ratio = round(width / height, 2)  # 計算寬高比
                    # 處理常見寬高比
                    if aspect_ratio in [1.33, 1.34]:  # 4:3
                        resolution_name = resolution_map.get(height, f"{height}p (4:3)")
                    elif aspect_ratio == 1.78:  # 16:9
                        resolution_name = resolution_map.get(height, f"{height}p")
                    elif aspect_ratio in [0.56, 0.56]:  # 9:16
                        resolution_name = resolution_map.get(height, f"{width}p (9:16)")
                    else:
                        resolution_name = f"{width}x{height} (Custom)"
                    resolutions.add(resolution_name)

        return sorted(resolutions, key=lambda x: int(x.split("p")[0].split("x")[0]), reverse=True)  # 按解析度從高到低排序

    def format_duration(self, seconds):
        # 格式化片長為 HH:MM:SS
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if (hours > 0):
            return f"{hours:02}:{minutes:02}:{seconds:02}"
        else:
            return f"{minutes:02}:{seconds:02}"

    def on_load_error(self, error_message):
        show_message_box(self, "錯誤", error_message, QMessageBox.Icon.Warning)
        self.close()

    def toggle_resolution_dropdown(self, extension):
        # 當選擇 MP3 時禁用解析度選單，否則啟用
        self.resolution_dropdown.setEnabled(extension != "MP3")

    def download_video(self):
        # 獲取用戶選擇的解析度和格式
        resolution = self.resolution_dropdown.currentText().split(" ")[0]  # 取得解析度數值部分
        extension = self.extension_dropdown.currentText().lower()

        # 根據設定檔決定檔名格式
        if extension == 'mp3':
            filename_template = f'%(title)s_audio.%(ext)s'  # MP3 格式不加解析度，附加 _audio 後綴
        else:  # MP4 格式
            if self.parent.append_resolution:  # 僅當 append_resolution=True 時加上解析度
                filename_template = f'%(title)s [{resolution}].%(ext)s'
            else:
                filename_template = f'%(title)s.%(ext)s'

        # 動態生成格式選項，確保解析度限制和回退機制
        format_string = self.generate_format_string(resolution, extension)

        # 設定下載選項
        ydl_opts = {
            'format': format_string,
            'outtmpl': os.path.join(self.download_path, filename_template),  # 使用正確的下載路徑
            'progress_hooks': [self.update_progress],  # 新增進度更新的 hook
            'postprocessors': [
                {
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': extension,  # 指定音訊格式
                    'preferredquality': '192',  # 設定音訊品質
                }
            ] if extension == 'mp3' else [],  # 僅在 MP3 格式時使用音訊提取
            'nocheckcertificate': True,  # 避免 SSL 憑證錯誤
            'file_access_denied_retries': 3,  # 處理檔案存取問題
            'no_date': True,  # 避免設定檔案修改日期
            'merge_output_format': extension if extension != 'mp3' else None,  # 確保合併輸出格式正確
            'postprocessor_args': ['-strict', '-2'],  # 確保兼容性
        }

        # 禁用按鈕
        self.download_button.setEnabled(False)
        self.resolution_dropdown.setEnabled(False)
        self.extension_dropdown.setEnabled(False)

        # 顯示進度條並調整視窗高度
        self.status_label.setText("下載中...")
        self.status_label.show()
        self.progress_bar.setValue(0)  # 初始化進度條值
        self.progress_bar.setRange(0, 100)  # 確保進度條範圍為 0 到 100
        self.progress_bar.show()
        self.setFixedHeight(self.expanded_height)  # 調整視窗高度為 300

        # 啟動下載執行緒
        self.already_downloaded_flag = False  # 重置標誌
        self.download_thread = DownloadThread(self.url, ydl_opts, self)
        self.download_thread.already_downloaded.connect(self.on_already_downloaded)  # 連接信號
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.start()

    def generate_format_string(self, resolution, extension):
        """生成格式選項，根據影片比例使用正確的解析度定義方式"""
        aspect_ratio = self.get_aspect_ratio()  # 獲取影片的寬高比
        if aspect_ratio == "9:16":
            # 使用寬度限制解析度
            width = resolution[:-1] if resolution.endswith("p") else resolution
            base_format = f'bestvideo[width<={width}][ext=mp4]+bestaudio[ext=m4a]/best[width<={width}][ext=mp4]'
            fallback_format = f'/bestvideo[width<={width}]+bestaudio/best[width<={width}]'
        elif aspect_ratio in ["16:9", "4:3"]:
            # 使用高度限制解析度
            height = resolution[:-1] if resolution.endswith("p") else resolution
            base_format = f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}][ext=mp4]'
            fallback_format = f'/bestvideo[height<={height}]+bestaudio/best[height<={height}]'
        else:
            # 自訂寬高比處理
            base_format, fallback_format = self.handle_custom_aspect_ratio(resolution)
        return base_format + fallback_format

    def handle_custom_aspect_ratio(self, resolution):
        """處理自訂寬高比影片的格式選項"""
        if "x" in resolution:
            width, height = resolution.split("x")
            base_format = f'bestvideo[width<={width}][height<={height}][ext=mp4]+bestaudio[ext=m4a]'
            fallback_format = f'/bestvideo[width<={width}][height<={height}]+bestaudio'
        else:
            raise ValueError("無效的解析度格式，請使用 '寬x高' 格式，例如 '256x144'")
        return base_format, fallback_format

    def get_aspect_ratio(self):
        """判斷影片的寬高比"""
        with YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(self.url, download=False)
            formats = info.get('formats', [])
            for fmt in formats:
                if fmt.get('vcodec') != 'none':  # 確保是影片格式
                    width = fmt.get('width')
                    height = fmt.get('height')
                    if width and height:
                        ratio = round(width / height, 2)
                        if ratio in [0.56, 0.57]:  # 9:16
                            return "9:16"
                        elif ratio in [1.77, 1.78]:  # 16:9
                            return "16:9"
                        elif ratio in [1.33, 1.34]:  # 4:3
                            return "4:3"
                        else:
                            return "custom"  # 自訂寬高比
        return "16:9"  # 預設為 16:9

    def update_progress(self, d):
        # 下載過程中不更新進度條
        pass

    def on_already_downloaded(self):
        # 已下載過的處理
        self.already_downloaded_flag = True  # 設置標誌為 True
        if self.extension_dropdown.currentText().lower() == 'mp3':
            show_message_box(self, "提示", "此音訊已下載過！", QMessageBox.Icon.Information)
        else:
            show_message_box(self, "提示", "此影片已下載過！", QMessageBox.Icon.Information)
            
        self.progress_bar.hide()
        self.status_label.hide()
        self.setFixedHeight(self.original_height)  # 恢復視窗高度為原始值
        self.close()  # 自動關閉影片資訊視窗
        self.parentWidget().setVisible(True)  # 回到主視窗

    def on_download_finished(self):
        # 下載完成後的處理
        if self.already_downloaded_flag:  # 若已下載過，直接返回
            return
        self.progress_bar.setValue(100)  # 下載完成後設定為 100%
        if self.extension_dropdown.currentText().lower() == 'mp3':
            show_message_box(self, "完成", "音訊下載完成！", QMessageBox.Icon.Information)
        else:
            show_message_box(self, "完成", "影片下載完成！", QMessageBox.Icon.Information)
            
        self.progress_bar.hide()
        self.status_label.hide()
        self.setFixedHeight(self.original_height)  # 恢復視窗高度為原始值
        self.close()  # 自動關閉影片資訊視窗
        self.parentWidget().setVisible(True)  # 回到主視窗

        # 啟用按鈕
        self.download_button.setEnabled(True)
        self.resolution_dropdown.setEnabled(True)
        self.extension_dropdown.setEnabled(True)


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.assets_dir = get_assets_dir()  # 使用通用方法取得 assets 資料夾路徑
        self.setWindowIcon(QIcon(os.path.join(self.assets_dir, "icon.ico")))  # 使用 icon.ico
        self.setWindowTitle("設定")
        self.setFixedSize(450, 200)  # 調整頁面大小
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowStaysOnTopHint)  # 取消置頂

        # 主程式目錄
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.settings_file = os.path.join(self.base_dir, "settings.txt")
        self.default_download_path = os.path.join(self.base_dir, "downloads")  # 預設下載路徑

        # 主佈局
        layout = QVBoxLayout()

        # 標籤頁
        tabs = QTabWidget()
        general_tab = QWidget()
        about_tab = QWidget()

        # 一般標籤頁
        general_layout = QVBoxLayout()

        # 新增下載路徑選擇
        download_path_layout = QHBoxLayout()
        self.download_path_label = QLabel("下載路徑：")
        self.download_path_entry = QLineEdit()
        self.download_path_entry.setPlaceholderText("選擇下載路徑...")
        self.download_path_entry.setReadOnly(True)  # 設為唯讀，防止直接編輯
        self.download_path_entry.mousePressEvent = self.show_full_path  # 點擊時顯示完整路徑並全選
        self.download_path_button = QPushButton("瀏覽")
        self.download_path_button.clicked.connect(self.select_download_path)
        download_path_layout.addWidget(self.download_path_label)
        download_path_layout.addWidget(self.download_path_entry)
        download_path_layout.addWidget(self.download_path_button)
        general_layout.addLayout(download_path_layout)

        # 新增「在檔名後方加上解析度」選項
        self.append_resolution_checkbox = QCheckBox("在檔名後方加上解析度")
        self.append_resolution_checkbox.setChecked(False)  # 預設不開啟
        general_layout.addWidget(self.append_resolution_checkbox)

        general_tab.setLayout(general_layout)

        # 關於標籤頁
        about_layout = QVBoxLayout()
        title_label = QLabel("oldfish Video Downloader")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")  # 放大字體
        version_label = QLabel("應用程式版本: 1.0.0")
        author_label = QLabel("作者: 老魚oldfish")
        link_label = QLabel('<a href="https://github.com/oldfish101240/oldfish-Video-Downloader">前往GitHub頁面</a>')
        link_label.setOpenExternalLinks(True)  # 啟用外部連結
        latest_version_label = QLabel('<a href="https://github.com/oldfish101240/oldfish-Video-Downloader/releases/latest">檢查最新版本</a>')
        latest_version_label.setOpenExternalLinks(True)  # 啟用外部連結

        about_layout.addWidget(title_label)
        about_layout.addWidget(version_label)
        about_layout.addWidget(author_label)
        about_layout.addWidget(link_label)
        about_layout.addWidget(latest_version_label)
        about_tab.setLayout(about_layout)

        # 添加標籤頁
        tabs.addTab(general_tab, "一般")
        tabs.addTab(about_tab, "關於")
        layout.addWidget(tabs)

        # 確定、取消與重設按鈕
        button_layout = QHBoxLayout()
        reset_button = QPushButton("重設為預設")
        reset_button.setFixedSize(100, 30)  # 調整按鈕大小
        reset_button.clicked.connect(self.reset_to_default)
        button_layout.addWidget(reset_button)
        button_layout.addStretch()  # 將其他按鈕推到右側
        save_button = QPushButton("儲存")
        save_button.setFixedSize(60, 30)  # 縮短按鈕
        save_button.clicked.connect(self.save_settings)
        cancel_button = QPushButton("取消")
        cancel_button.setFixedSize(60, 30)  # 縮短按鈕
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        self.original_settings = {}  # 儲存初始設定
        self.load_settings()  # 初始化設定
        self.save_original_settings()  # 儲存初始設定值

    def select_download_path(self):
        from PyQt6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(self, "選擇下載路徑")
        if (path):
            self.set_path_with_ellipsis(path)

    def reset_to_default(self):
        # 重設下載路徑為預設值
        self.set_path_with_ellipsis(self.default_download_path)

    def save_settings(self):
        """儲存設定到設定檔"""
        settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.txt")  # 確保路徑正確
        download_path = self.download_path_entry.toolTip()  # 使用完整路徑
        append_resolution = self.append_resolution_checkbox.isChecked()
        if download_path:
            try:
                # 確保目錄存在
                os.makedirs(os.path.dirname(settings_file), exist_ok=True)
                # 強制覆寫設定檔，使用 UTF-8 編碼
                with open(settings_file, "w", encoding="utf-8") as f:
                    f.write(f"download_path={download_path}\n")
                    f.write(f"append_resolution={append_resolution}\n")  # 儲存設定
                print("設定已成功儲存！")  # 在終端顯示成功訊息
                self.save_original_settings()  # 更新初始設定值
            except Exception as e:
                logging.error(f"儲存設定失敗：{e}")  # 在終端記錄錯誤
                show_message_box(self, "錯誤", f"無法儲存設定：{e}", QMessageBox.Icon.Critical)
        else:
            QMessageBox.warning(self, "警告", "下載路徑無效，請重新選擇！")  # 顯示警告訊息
        self.accept()

    def load_settings(self):
        """從設定檔中載入設定"""
        settings_file = os.path.join(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__)), "settings.txt")
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:  # 使用 UTF-8 編碼讀取
                    for line in f:
                        if line.startswith("download_path="):
                            self.set_path_with_ellipsis(line.split("=", 1)[1].strip())
                        if line.startswith("append_resolution="):
                            self.append_resolution_checkbox.setChecked(line.split("=", 1)[1].strip() == "True")
            except UnicodeDecodeError as e:
                logging.error(f"讀取設定檔時發生編碼錯誤：{e}")
                show_message_box(self, "錯誤", "讀取設定檔失敗，請檢查檔案編碼是否為 UTF-8。", QMessageBox.Icon.Critical)
        else:
            self.set_path_with_ellipsis(self.default_download_path)

    def set_path_with_ellipsis(self, path):
        # 設定路徑，若過長則省略最尾端部分
        self.download_path_entry.setToolTip(path)  # 儲存完整路徑於 ToolTip
        if (len(path) > 40):  # 假設超過 40 字元視為過長
            self.download_path_entry.setText(f"{path[:37]}...")  # 顯示省略的路徑
        else:
            self.download_path_entry.setText(path)

    def show_full_path(self, event):
        # 點擊時顯示完整路徑並全選
        self.download_path_entry.setReadOnly(False)  # 允許編輯
        self.download_path_entry.setText(self.download_path_entry.toolTip())  # 顯示完整路徑
        self.download_path_entry.selectAll()  # 全選文字
        self.download_path_entry.setFocus()  # 聚焦輸入框
        super().mousePressEvent(event)  # 繼續處理其他事件

    def save_original_settings(self):
        """儲存初始設定值以便檢查是否有修改"""
        self.original_settings = {
            "download_path": self.download_path_entry.toolTip(),
            "append_resolution": self.append_resolution_checkbox.isChecked()
        }

    def has_settings_changed(self):
        """檢查設定是否有修改"""
        return (
            self.download_path_entry.toolTip() != self.original_settings["download_path"] or
            self.append_resolution_checkbox.isChecked() != self.original_settings["append_resolution"]
        )

    def reject(self):
        """覆寫取消按鈕行為，檢查是否有未儲存的更改"""
        if self.has_settings_changed():
            reply = QMessageBox.question(
                self,
                "提醒",
                "偵測到設定更改，是否要返回儲存？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            # 修正錯誤：移除對 reply.setWindowIcon 的調用
            if reply == QMessageBox.StandardButton.Yes:
                return  # 停留在設定視窗，讓用戶返回儲存
        super().reject()  # 關閉視窗


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 定義 base_dir 為主程式所在的資料夾（支援打包後的 .exe）
    if getattr(sys, 'frozen', False):  # 判斷是否為打包後的 .exe
        base_dir = os.path.dirname(sys.executable)  # .exe 檔案所在目錄
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))  # 原始腳本所在目錄

    print(f"程式基底目錄 (base_dir)：{base_dir}")

    settings_file = os.path.join(base_dir, "settings.txt")
    ffmpeg_path = os.path.join(base_dir, "ffmpeg-7.1.1-essentials_build", "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")

    # 檢查 settings.txt 是否存在，若不存在則自動生成
    if not os.path.exists(settings_file):
        try:
            with open(settings_file, "w", encoding="utf-8") as f:
                f.write(f"download_path={os.path.join(base_dir, 'downloads')}\n")
                f.write("append_resolution=False\n")
            print("未找到 settings.txt，已自動生成預設設定檔。")
        except Exception as e:
            print(f"無法生成 settings.txt：{e}")
    else:
        print("成功讀取 settings.txt。")

    # 檢查 FFmpeg 是否已安裝
    print(f"正在檢查 FFmpeg 是否存在於路徑：{ffmpeg_path}")
    if not os.path.isfile(ffmpeg_path):  # 使用 os.path.isfile 確保檔案存在且為檔案
        print("FFmpeg 未安裝，將開始安裝。")
        print(f"FFmpeg 將安裝於：{os.path.dirname(ffmpeg_path)}")
        installer = Installer()
        installer.installation_finished.connect(lambda: print("安裝完成"))
        installer.show()
    else:
        print("FFmpeg 已安裝，無需重新安裝。")
        # 確保 FFmpeg 路徑被添加到環境變數
        os.environ["PATH"] += os.pathsep + os.path.abspath(os.path.dirname(ffmpeg_path))
        window = VideoDownloaderApp()
        window.setWindowIcon(QIcon(os.path.join(base_dir, "assets", "icon.ico")))  # 使用 icon.ico
        window.show()

    sys.exit(app.exec())
