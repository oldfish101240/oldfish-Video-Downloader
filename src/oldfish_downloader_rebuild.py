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

def download_file(url, output_path, progress_callback, cancel_callback):
    try:
        response = requests.get(url, stream=True, timeout=10)
        total_size = int(response.headers.get('content-length', 0))
        bytes_received = 0
        start_time = None  # 初始化開始時間
        for chunk in response.iter_content(chunk_size=1024):
            if cancel_callback():
                return
            if start_time is None:
                start_time = time.time()  # 設定開始時間
            file.write(chunk)
            bytes_received += len(chunk)
            elapsed_time = time.time() - start_time  # 計算已經過的時間
            speed = bytes_received / elapsed_time if elapsed_time > 0 else 0  # 計算平均速度
            progress_callback(bytes_received, total_size, speed)
    except Exception as e:
        raise e

class Installer(QWidget):
    # 新增信號，用於通知安裝完成
    installation_finished = pyqtSignal()

    # 新增信號，用於更新進度條和速度
    progress_updated = pyqtSignal(int, float, float)  # percent, bytes_received, speed

    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon("assets/icon.ico"))  # 設定視窗圖示
        self.cancel_flag = False  # 初始化取消標誌
        self.timer = QTimer(self)  # 初始化 QTimer
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)  # 設定視窗置頂
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint)  # 禁用關閉按鈕
        self.initUI()

        # 連接信號到槽
        self.progress_updated.connect(self._update_progress_ui)

    def initUI(self):
        self.setWindowTitle('安裝資訊')
        self.setFixedSize(400, 140)  # 調整視窗高度
        layout = QVBoxLayout()

        winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)

        reply = QMessageBox.question(self, '安裝資訊', 'FFmpeg 是影片下載器必要的元件。\n是否要下載並安裝？', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            # 定義跟目錄為主程式所在的資料夾
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            self.ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            self.ffmpeg_zip = os.path.join(self.base_dir, "ffmpeg.zip")  # 壓縮檔下載到跟目錄
            self.ffmpeg_extract_dir = os.path.join(self.base_dir, "ffmpeg-7.1.1-essentials_build")  # 解壓縮目錄
            self.progress_label = QLabel("安裝中...")
            layout.addWidget(self.progress_label)

            # 速度與已安裝/總大小的佈局
            info_layout = QHBoxLayout()
            self.speed_label = QLabel("")
            info_layout.addWidget(self.speed_label)
            info_layout.addStretch()
            self.size_label = QLabel("0.00 MB / 0.00 MB")  # 只顯示數字
            info_layout.addWidget(info_layout)
            layout.addLayout(info_layout)

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
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.future = self.executor.submit(
            download_file,
            self.ffmpeg_url,
            self.ffmpeg_zip,
            self.update_progress,
            lambda: self.cancel_flag
        )
        self.install_ffmpeg(self.future)

    def update_progress(self, bytes_received, total_size, speed):
        percent = int(bytes_received * 100 / total_size)
        # 發射信號，將進度更新傳遞到主執行緒
        self.progress_updated.emit(percent, bytes_received, speed)

    def _update_progress_ui(self, percent, bytes_received, speed):
        self.progress_bar.setValue(percent)  # 更新進度條
        self.size_label.setText(f"{bytes_received / (1024 * 1024):.2f} MB / {self.progress_bar.maximum()} MB")  # 更新檔案進度
        if speed > 1024 * 1024:
            self.speed_label.setText(f"速度：{speed / (1024 * 1024):.2f} MB/s")  # 顯示速度
        elif speed > 1024:
            self.speed_label.setText(f"速度：{speed / 1024:.2f} KB/s")
        else:
            self.speed_label.setText(f"速度：{speed:.2f} B/s")

    def install_ffmpeg(self, future):
        self.future = future  # 將 future 儲存為類別屬性
        self.start_timer()  # 啟動定時器

    def start_timer(self):
        self.timer.timeout.connect(self.check_future)
        self.timer.start(100)  # 每100毫秒檢查一次

    def check_future(self):
        if self.future.done():
            self.timer.stop()
            try:
                result = self.future.result()
                if result is None and not self.cancel_flag:
                    # 解壓縮到跟目錄
                    with zipfile.ZipFile(self.ffmpeg_zip, 'r') as zip_ref:
                        zip_ref.extractall(self.ffmpeg_extract_dir)
                    os.remove(self.ffmpeg_zip)
                    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
                    print("FFmpeg 安裝完成")  # 除錯訊息

                    self.installation_finished.emit()
                    self.close()

                    # 顯示安裝完成的彈窗
                    QMessageBox.information(self, '安裝完成', 'FFmpeg 安裝完成，請重新啟動此程式。', QMessageBox.StandardButton.Ok).setWindowFlags(
                        Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog)  # 設定警告視窗置頂
                    sys.exit()
                else:
                    if self.cancel_flag:
                        self.cleanup_partial_download()  # 刪除部分下載的文件
                        sys.exit()
            except Exception as e:
                QMessageBox.critical(self, '錯誤', f'FFmpeg 安裝失敗：{e}', QMessageBox.StandardButton.Ok).setWindowFlags(
                    Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog)  # 設定警告視窗置頂
                self.installation_finished.emit()  # 確保在發生錯誤時也發出信號
                self.close()

    def cancel_download(self):
        self.cancel_flag = True
        self.executor.shutdown(wait=True)
        self.cleanup_partial_download()  # 刪除部分下載的文件
        sys.exit()

    def cleanup_partial_download(self):
        # 刪除部分下載的文件
        try:
            if os.path.exists(self.ffmpeg_zip):
                os.remove(self.ffmpeg_zip)
            if os.path.exists(self.ffmpeg_zip + ".part"):
                os.remove(self.ffmpeg_zip + ".part")
            print("已刪除部分下載的文件。")
        except Exception as e:
            print(f"刪除部分下載的文件失敗：{e}")


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
            error_message = "找不到影片，請檢查是否輸入正確的網址"  # 修改錯誤訊息
            self.error_occurred.emit(error_message)


class VideoDownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("oldfish 影片下載器")
        self.setFixedSize(400, 100)  # 調整視窗高度

        # 動態獲取圖示路徑
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "assets", "icon.ico")
        settings_icon_path = os.path.join(base_dir, "assets", "settings_icon.png")
        folder_icon_path = os.path.join(base_dir, "assets", "folder_icon.png")  # 資料夾圖案

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
        # 從設定檔中加載下載路徑，若不存在則使用預設值
        settings_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.txt")
        if os.path.exists(settings_file):
            with open(settings_file, "r") as f:
                for line in f:
                    if line.startswith("download_path="):
                        return line.split("=", 1)[1].strip()
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")

    def show_video_info(self):
        url = self.url_entry.text()
        if not url:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("警告")
            msg_box.setText("請輸入影片網址！")
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)  # 設定視窗置頂
            msg_box.exec()
            return

        if "youtube.com/watch" not in url and "youtu.be/" not in url:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("警告")
            msg_box.setText("請輸入有效的 YouTube 影片網址！")
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)  # 設定視窗置頂
            msg_box.exec()
            return

        # 開啟影片資訊視窗
        self.video_info_window = VideoInfoDialog(url, parent=self, download_path=self.default_download_path)
        self.video_info_window.append_resolution = self.append_resolution  # 傳遞是否加上解析度的設定
        self.video_info_window.show()

    def open_downloads_folder(self):
        # 使用自訂下載路徑
        base_dir = os.path.dirname(os.path.abspath(__file__))
        settings_file = os.path.join(base_dir, "settings.txt")

        if os.path.exists(settings_file):
            with open(settings_file, "r") as f:
                for line in f:
                    if line.startswith("download_path="):
                        downloads_dir = line.split("=", 1)[1].strip()
                        break
        else:
            downloads_dir = os.path.join(base_dir, "downloads")

        if not os.path.exists(downloads_dir):
            os.makedirs(downloads_dir)
        os.startfile(downloads_dir)

    def open_settings(self):
        settings_dialog = SettingsDialog(self)
        if settings_dialog.exec():
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

    def hook(self, d):
        """處理下載進度更新的回調函數"""
        if d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes", d.get("total_bytes_estimate", 1))
            percent = int(downloaded / total * 100) if total > 0 else 0
            self.progress.emit(percent)  # 發送進度百分比
            self.status.emit(f"下載進度: {percent}%")  # 發送進度文字
        elif d["status"] == "finished":
            self.status.emit("下載完成，正在處理檔案...")

    def run(self):
        try:
            with YoutubeDL(self.ydl_opts) as ydl:
                ydl.add_default_info_extractors()
                ydl.params['logger'] = self  # 使用自訂 logger
                ydl.download([self.url])
        except Exception as e:
            logging.error(f"下載失敗：{e}")

    def debug(self, msg):
        # 檢查是否包含「has already been downloaded」
        if "has already been downloaded" in msg:
            self.already_downloaded.emit()

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


class VideoInfoDialog(QDialog):
    def __init__(self, url, parent=None, download_path=None):
        super().__init__(parent)
        self.setWindowTitle("影片資訊")
        self.setFixedSize(400, 250)  # 確保視窗大小正確
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)  # 設定視窗置頂
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
        self.resolution_dropdown.addItems(["1080p", "720p", "480p", "360p"])
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
            if thumbnail_url:
                response = requests.get(thumbnail_url, timeout=10)
                response.raise_for_status()
                pixmap = QPixmap()
                pixmap.loadFromData(BytesIO(response.content).read())
                scaled_pixmap = pixmap.scaled(120, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.thumbnail_label.setPixmap(scaled_pixmap)
            else:
                self.thumbnail_label.setText("無法載入縮圖")
        except Exception as e:
            logging.error(f"無法載入縮圖: {e}")
            self.thumbnail_label.setText("無法載入縮圖")

        # 隱藏載入中訊息，啟用解析度與副檔名選擇，顯示下載按鈕
        self.loading_label.hide()
        self.resolution_dropdown.setEnabled(True)
        self.extension_dropdown.setEnabled(True)
        self.download_button.setEnabled(True)

    def format_duration(self, seconds):
        # 格式化片長為 HH:MM:SS
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02}:{minutes:02}:{seconds:02}"
        else:
            return f"{minutes:02}:{seconds:02}"

    def on_load_error(self, error_message):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("錯誤")
        msg_box.setText(error_message)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)  # 設定視窗置頂
        msg_box.exec()
        self.close()

    def toggle_resolution_dropdown(self, extension):
        # 當選擇 MP3 時禁用解析度選單，否則啟用
        self.resolution_dropdown.setEnabled(extension != "MP3")

    def download_video(self):
        # 獲取用戶選擇的解析度和格式
        resolution = self.resolution_dropdown.currentText()
        extension = self.extension_dropdown.currentText().lower()

        # 根據設定決定檔名是否加上解析度
        filename_template = f'%(title)s [{resolution}].%(ext)s' if self.append_resolution else f'%(title)s.%(ext)s'

        # 設定下載選項
        ydl_opts = {
            'format': f'bestvideo[height<={resolution[:-1]}]+bestaudio/best',
            'outtmpl': os.path.join(self.download_path, filename_template),  # 使用正確的下載路徑
            'progress_hooks': [self.update_progress],  # 新增進度更新的 hook
            'postprocessors': [{'key': 'FFmpegVideoConvertor', 'preferedformat': extension}] if extension == 'mp3' else [],
        }

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

    def update_progress(self, d):
        # 更新進度條
        if d['status'] == 'downloading':
            percent_str = d.get('_percent_str', '').strip()
            try:
                # 移除多餘空白並檢查格式
                percent_str = percent_str.replace(' ', '').replace('%', '')  # 移除空白和百分比符號
                if percent_str.replace('.', '', 1).isdigit():  # 確保字串是有效數字
                    percent = float(percent_str)
                    percent = max(0, min(100, percent))  # 確保百分比在有效範圍內
                    self.progress_bar.setValue(int(percent))  # 設定進度條的值
                else:
                    raise ValueError(f"無效的百分比格式：{percent_str}")
            except ValueError as e:
                logging.error(f"無法解析進度百分比：{e}")

    def on_already_downloaded(self):
        # 已下載過的處理
        self.already_downloaded_flag = True  # 設置標誌為 True
        QMessageBox.information(self, "提示", "此影片已下載過！", QMessageBox.StandardButton.Ok)
        self.progress_bar.hide()
        self.status_label.hide()
        self.setFixedHeight(self.original_height)  # 恢復視窗高度

    def on_download_finished(self):
        # 下載完成後的處理
        if self.already_downloaded_flag:  # 若已下載過，直接返回
            return
        self.status_label.setText("下載完成！")
        QMessageBox.information(self, "完成", "影片下載完成！", QMessageBox.StandardButton.Ok)
        self.progress_bar.hide()
        self.status_label.hide()
        self.setFixedHeight(self.original_height)  # 恢復視窗高度為原始值
        self.close()  # 自動關閉影片資訊視窗
        self.parentWidget().setVisible(True)  # 回到主視窗，修正為正確的顯示方法


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setFixedSize(450, 200)  # 調整頁面大小

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
        version_label = QLabel("應用程式版本: 0.3.0")
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

        # 初始化下載路徑
        self.load_settings()

    def select_download_path(self):
        from PyQt6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(self, "選擇下載路徑")
        if path:
            self.set_path_with_ellipsis(path)

    def reset_to_default(self):
        # 重設下載路徑為預設值
        self.set_path_with_ellipsis(self.default_download_path)

    def save_settings(self):
        download_path = self.download_path_entry.toolTip()  # 使用完整路徑
        append_resolution = self.append_resolution_checkbox.isChecked()
        if download_path:
            with open(self.settings_file, "w") as f:
                f.write(f"download_path={download_path}\n")
                f.write(f"append_resolution={append_resolution}\n")  # 儲存設定
            print(f"下載路徑已保存: {download_path}, 加上解析度: {append_resolution}")
        self.accept()

    def load_settings(self):
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r") as f:
                for line in f:
                    if line.startswith("download_path="):
                        self.set_path_with_ellipsis(line.split("=", 1)[1].strip())
                    if line.startswith("append_resolution="):
                        self.append_resolution_checkbox.setChecked(line.split("=", 1)[1].strip() == "True")
        else:
            self.set_path_with_ellipsis(self.default_download_path)

    def set_path_with_ellipsis(self, path):
        # 設定路徑，若過長則省略最尾端部分
        self.download_path_entry.setToolTip(path)  # 儲存完整路徑於 ToolTip
        if len(path) > 40:  # 假設超過 40 字元視為過長
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


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 定義跟目錄為主程式所在的資料夾
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ffmpeg_path = os.path.join(base_dir, "ffmpeg-7.1.1-essentials_build", "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")

    # 檢查 FFmpeg 是否已安裝
    if not os.path.isfile(ffmpeg_path):  # 使用 os.path.isfile 確保檔案存在且為檔案
        print(f"未偵測到 FFmpeg，檢查的路徑為: {ffmpeg_path}")  # 顯示檢查的路徑
        if not os.path.exists(os.path.dirname(ffmpeg_path)):
            print(f"目錄不存在: {os.path.dirname(ffmpeg_path)}")  # 顯示目錄不存在的訊息
        installer = Installer()
        installer.installation_finished.connect(lambda: print("安裝完成"))
        installer.show()
    else:
        print("已偵測到 FFmpeg，路徑為:", os.path.abspath(ffmpeg_path))  # 在終端顯示訊息
        # 確保 FFmpeg 路徑被添加到環境變數
        os.environ["PATH"] += os.pathsep + os.path.abspath(os.path.dirname(ffmpeg_path))
        window = VideoDownloaderApp()
        window.show()

    sys.exit(app.exec())
