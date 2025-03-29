from PyQt6.QtWidgets import QApplication, QMainWindow, QLineEdit, QPushButton, QMessageBox, QVBoxLayout, QWidget, QHBoxLayout, QLabel, QDialog, QProgressBar, QComboBox, QTabWidget, QFormLayout, QCheckBox, QSpinBox
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

# 設定日誌
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

def download_file(url, output_path, progress_callback, cancel_callback):
    try:
        response = requests.get(url, stream=True, timeout=10)
        total_size = int(response.headers.get('content-length', 0))
        bytes_received = 0
        with open(output_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=1024):
                if cancel_callback():
                    return
                file.write(chunk)
                bytes_received += len(chunk)
                speed = len(chunk) / 0.1  # 假設每次迭代花費 0.1 秒
                progress_callback(bytes_received, total_size, speed)
    except Exception as e:
        raise e

class Installer(QWidget):
    installation_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon("assets/icon.ico"))  # 設定視窗圖示
        self.cancel_flag = False  # 初始化取消標誌
        self.timer = QTimer(self)  # 初始化 QTimer
        self.initUI()

    def initUI(self):
        self.setWindowTitle('安裝資訊')
        self.setFixedSize(400, 200)  # 禁止調整大小
        layout = QVBoxLayout()

        winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)

        reply = QMessageBox.question(self, '安裝資訊', 'FFmpeg 是影片下載器必要的元件。\n是否要下載並安裝？', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            self.ffmpeg_zip = "ffmpeg.zip"
            self.progress_label = QLabel("安裝中...")
            layout.addWidget(self.progress_label)
            self.speed_label = QLabel("")
            layout.addWidget(self.speed_label)
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
        self.progress_bar.setValue(percent)
        if speed > 1024 * 1024:
            self.speed_label.setText(f"速度：{speed / (1024 * 1024):.2f} MB/s")
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
                    with zipfile.ZipFile(self.ffmpeg_zip, 'r') as zip_ref:
                        zip_ref.extractall("ffmpeg-7.1.1-essentials_build")
                    os.remove(self.ffmpeg_zip)
                    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
                    print("FFmpeg 安裝完成")  # 除錯訊息

                    self.installation_finished.emit()
                    self.close()

                    # 顯示安裝完成的彈窗
                    QMessageBox.information(self, '安裝完成', 'FFmpeg 安裝完成，請重新啟動此程式。', QMessageBox.StandardButton.Ok)
                    sys.exit()
                else:
                    if self.cancel_flag:
                        try:
                            if os.path.exists(self.ffmpeg_zip + ".part"):
                                os.remove(self.ffmpeg_zip + ".part")
                        except Exception as e:
                            print(f"刪除暫存檔案失敗：{e}")
                        sys.exit()
            except Exception as e:
                QMessageBox.critical(self, '錯誤', f'FFmpeg 安裝失敗：{e}')
                self.installation_finished.emit()  # 確保在發生錯誤時也發出信號
                self.close()

    def cancel_download(self):
        self.cancel_flag = True
        self.executor.shutdown(wait=True)
        try:
            if os.path.exists(self.ffmpeg_zip + ".part"):
                os.remove(self.ffmpeg_zip + ".part")
        except Exception as e:
            print(f"刪除暫存檔案失敗：{e}")
        sys.exit()


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

    def show_video_info(self):
        url = self.url_entry.text()
        if not url:
            QMessageBox.warning(self, "警告", "請輸入影片網址！")
            return

        if "youtube.com/watch" not in url and "youtu.be/" not in url:
            QMessageBox.warning(self, "警告", "請輸入有效的 YouTube 影片網址！")
            return

        try:
            logging.debug(f"正在嘗試獲取影片資訊，URL: {url}")
            with YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', '未知標題')
                thumbnail_url = info.get('thumbnail', '')

            logging.debug(f"影片標題: {title}, 縮圖 URL: {thumbnail_url}")

            # 開啟影片資訊視窗
            self.video_info_window = VideoInfoDialog(title, thumbnail_url, url, parent=self)
            self.video_info_window.show()  # 改為非模態顯示

        except Exception as e:
            logging.error(f"無法獲取影片資訊: {e}")
            QMessageBox.critical(self, "錯誤", f"無法獲取影片資訊：{str(e)}")

    def start_download(self, url, ydl_opts):
        pass  # 移除原進度視窗邏輯

    def open_downloads_folder(self):
        # 開啟與主程式相同目錄下的 downloads 資料夾
        downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
        if not os.path.exists(downloads_dir):
            os.makedirs(downloads_dir)
        os.startfile(downloads_dir)

    def open_settings(self):
        settings_dialog = SettingsDialog(self)
        settings_dialog.exec()

    def select_all_text(self, event):
        self.url_entry.selectAll()


class DownloadThread(QThread):
    def __init__(self, url, ydl_opts, parent=None):
        super().__init__(parent)
        self.url = url
        self.ydl_opts = ydl_opts

    def run(self):
        try:
            with YoutubeDL(self.ydl_opts) as ydl:
                ydl.download([self.url])
        except Exception as e:
            logging.error(f"下載失敗：{e}")


class VideoInfoDialog(QDialog):
    def __init__(self, title, thumbnail_url, url, parent=None):
        super().__init__(parent)
        self.setWindowTitle("影片資訊")
        self.setFixedSize(400, 300)  # 調整視窗高度以容納進度條與狀態標籤
        self.url = url
        self.parent = parent

        # 主佈局
        main_layout = QVBoxLayout()

        # 縮圖與標題
        thumbnail_layout = QHBoxLayout()
        thumbnail_label = QLabel()
        try:
            if thumbnail_url:
                response = requests.get(thumbnail_url, timeout=10)
                response.raise_for_status()
                pixmap = QPixmap()
                pixmap.loadFromData(BytesIO(response.content).read())
                scaled_pixmap = pixmap.scaled(120, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                thumbnail_label.setPixmap(scaled_pixmap)
            else:
                thumbnail_label.setText("無法載入縮圖")
                thumbnail_label.setStyleSheet("color: red; font-size: 12px;")
        except Exception as e:
            logging.error(f"無法載入縮圖: {e}")
            thumbnail_label.setText("無法載入縮圖")
            thumbnail_label.setStyleSheet("color: red; font-size: 12px;")
        thumbnail_layout.addWidget(thumbnail_label)

        title_label = QLabel(f"標題：{title}")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        thumbnail_layout.addWidget(title_label)
        main_layout.addLayout(thumbnail_layout)

        # 解析度與副檔名選擇
        self.resolution_dropdown = QComboBox()
        self.resolution_dropdown.addItems(["1080p", "720p", "480p", "360p"])
        self.extension_dropdown = QComboBox()
        self.extension_dropdown.addItems(["MP4", "MP3"])
        self.extension_dropdown.currentTextChanged.connect(self.toggle_resolution_dropdown)

        form_layout = QFormLayout()
        form_layout.addRow("選擇解析度：", self.resolution_dropdown)
        form_layout.addRow("選擇副檔名：", self.extension_dropdown)
        main_layout.addLayout(form_layout)

        # 狀態標籤
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.hide()  # 初始隱藏
        main_layout.addWidget(self.status_label)

        # 進度條
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
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
        self.progress_bar.hide()  # 初始隱藏
        main_layout.addWidget(self.progress_bar)

        # 下載按鈕
        self.download_button = QPushButton("開始下載")
        self.download_button.clicked.connect(self.download_video)
        main_layout.addWidget(self.download_button)

        self.setLayout(main_layout)

    def toggle_resolution_dropdown(self, extension):
        # 當選擇 MP3 時禁用解析度選單，否則啟用
        self.resolution_dropdown.setEnabled(extension != "MP3")

    def download_video(self):
        try:
            ffmpeg_path = os.path.join("ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
            if not os.path.exists(ffmpeg_path):
                raise FileNotFoundError(f"FFmpeg 未找到，請檢查路徑：{ffmpeg_path}")

            downloads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
            if not os.path.exists(downloads_dir):
                os.makedirs(downloads_dir)

            # 根據選擇的解析度和副檔名設置下載選項
            selected_resolution = self.resolution_dropdown.currentText()
            selected_extension = self.extension_dropdown.currentText()
            ydl_opts = {
                'outtmpl': os.path.join(downloads_dir, f'%(title)s_{selected_resolution}.%(ext)s'),
                'ffmpeg_location': ffmpeg_path,
                'format': self.get_format_code(selected_resolution, selected_extension),
                'n_threads': 4  # 啟用多線程加速
            }

            # 禁用所有按鈕並顯示進度條與狀態標籤
            self.download_button.setEnabled(False)
            self.resolution_dropdown.setEnabled(False)
            self.extension_dropdown.setEnabled(False)
            self.progress_bar.show()
            self.status_label.show()
            self.status_label.setText("正在準備下載...")

            # 啟動下載執行緒
            self.download_thread = DownloadThread(self.url, ydl_opts)
            self.download_thread.finished.connect(self.on_download_finished)
            self.download_thread.start()
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"下載失敗：{str(e)}")

    def on_download_finished(self):
        self.status_label.setText("下載完成！")
        self.progress_bar.setValue(100)

        # 彈出下載完成訊息框
        self.show_completion_message()

    def show_completion_message(self):
        QMessageBox.information(
            self,
            "下載完成",
            "下載已完成！",
            QMessageBox.StandardButton.Ok
        )
        self.close_all()

    def close_all(self):
        self.close()
        if self.parent:
            self.parent.show()

    def get_format_code(self, resolution, extension):
        # 根據選擇的解析度和副檔名返回對應的 yt-dlp 格式代碼
        if extension == "MP3":
            return "bestaudio/best"
        format_map = {
            "1080p": "bestvideo[height<=1080]+bestaudio/best",
            "720p": "bestvideo[height<=720]+bestaudio/best",
            "480p": "bestvideo[height<=480]+bestaudio/best",
            "360p": "bestvideo[height<=360]+bestaudio/best"
        }
        return format_map.get(resolution, "best")


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setFixedSize(300, 200)  # 設定頁面大小

        # 主佈局
        layout = QVBoxLayout()

        # 標籤頁
        tabs = QTabWidget()
        general_tab = QWidget()
        advanced_tab = QWidget()

        # 一般設定
        general_layout = QFormLayout()
        self.auto_update_checkbox = QCheckBox("自動檢查更新")
        general_layout.addRow("自動更新：", self.auto_update_checkbox)
        self.download_threads_spinbox = QSpinBox()
        self.download_threads_spinbox.setRange(1, 10)
        self.download_threads_spinbox.setValue(4)
        general_layout.addRow("下載執行緒數量：", self.download_threads_spinbox)
        general_tab.setLayout(general_layout)

        # 高級設定
        advanced_layout = QVBoxLayout()
        self.enable_logging_checkbox = QCheckBox("啟用日誌")
        advanced_layout.addWidget(self.enable_logging_checkbox)
        advanced_tab.setLayout(advanced_layout)

        # 添加標籤頁
        tabs.addTab(general_tab, "一般")
        tabs.addTab(advanced_tab, "高級")
        layout.addWidget(tabs)

        # 確定與取消按鈕
        button_layout = QHBoxLayout()
        save_button = QPushButton("儲存")
        save_button.clicked.connect(self.save_settings)
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def save_settings(self):
        # 儲存設定的邏輯
        auto_update = self.auto_update_checkbox.isChecked()
        download_threads = self.download_threads_spinbox.value()
        enable_logging = self.enable_logging_checkbox.isChecked()

        # 這裡可以將設定儲存到檔案或應用到程式
        print(f"自動更新: {auto_update}, 下載執行緒: {download_threads}, 啟用日誌: {enable_logging}")
        self.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 檢查 FFmpeg 是否已安裝
    ffmpeg_path = os.path.join("ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
    if not os.path.exists(ffmpeg_path):
        installer = Installer()
        installer.installation_finished.connect(lambda: print("安裝完成"))
        installer.show()
    else:
        # 確保 FFmpeg 路徑被添加到環境變數
        os.environ["PATH"] += os.pathsep + os.path.abspath(os.path.dirname(ffmpeg_path))
        window = VideoDownloaderApp()
        window.show()

    sys.exit(app.exec())
