import sys
import os
import shutil
import zipfile
import requests
import PyQt6.QtWidgets 
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel,
    QPushButton, QVBoxLayout, QProgressBar,
    QMessageBox, QHBoxLayout, QLineEdit, QComboBox,
    QMenuBar, QMenu
)
from PyQt6.QtCore import QSize, Qt, QThread, pyqtSignal, QTimer, QMetaObject
import winsound
import concurrent.futures
import time
import yt_dlp
from PyQt6.QtGui import QIcon, QAction, QPalette
import json
import subprocess
import webbrowser
import platform  # 新增匯入 platform 模組

base_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
ffmpeg_path = os.path.join(base_path, "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
ffmpeg_installed = ffmpeg_path is not None and os.path.exists(ffmpeg_path)
print(f"FFmpeg installed: {ffmpeg_installed}")  # 除錯訊息

def download_file(url, filename, progress_callback, cancel_flag):
    try:
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        bytes_received = 0
        start_time = time.time()
        last_bytes_received = 0
        with open(filename + ".part", 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if cancel_flag():
                    break
                f.write(chunk)
                bytes_received += len(chunk)
                elapsed_time = time.time() - start_time
                if elapsed_time > 0.5:
                    speed = (bytes_received - last_bytes_received) / elapsed_time
                    progress_callback(bytes_received, total_size, speed)
                    start_time = time.time()
                    last_bytes_received = bytes_received
        if not cancel_flag():
            os.rename(filename + ".part", filename)
    except Exception as e:
        print(f"下載失敗：{e}")
        

class Installer(QWidget):
    installation_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon("icon.ico"))  # 設定視窗圖示
        self.cancel_flag = False  # 初始化取消標誌
        self.timer = QTimer(self)  # 初始化 QTimer
        self.initUI()

    def initUI(self):
        self.setWindowTitle('安裝資訊')
        self.setFixedSize(400, 200)  # 設置視窗的固定大小
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
                        zip_ref.extractall()
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

class DownloadThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)

    def __init__(self, url, resolution, file_format, status_label):
        super().__init__()
        self.url = url
        self.resolution = resolution
        self.file_format = file_format.lower()
        self.status_label = status_label

    def run(self):
        self.status.emit("下載正在進行，請稍後")
        os.makedirs("downloads", exist_ok=True)
        
        # 動態生成檔案名稱，包含解析度
        output_path = f"downloads/%(title)s_{self.resolution}.%(ext)s"
        
        base_path = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
        ffmpeg_path = os.path.join(base_path, "ffmpeg-7.1.1-essentials_build", "bin", "ffmpeg.exe")
        if not ffmpeg_path or not os.path.exists(ffmpeg_path):
            self.status.emit("錯誤: 找不到 FFmpeg，\n         請檢查下載是否成功")
            return
        
        ydl_opts = {
            "outtmpl": output_path,
            "progress_hooks": [self.hook],
            "ffmpeg_location": os.path.dirname(ffmpeg_path)
        }

        # 動態生成格式選項
        if self.file_format == "mp4":
            resolution_height = self.resolution[:-1]  # 移除 'p'，僅保留數字
            ydl_opts["format"] = f"bestvideo[height={resolution_height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height={resolution_height}]/best"
        elif self.file_format == "mp3":
            ydl_opts["format"] = "bestaudio[ext=m4a]/bestaudio"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        elif self.file_format in ["wmv", "avi", "mkv", "flv", "webm"]:
            resolution_height = self.resolution[:-1]
            ydl_opts["format"] = f"bestvideo[height={resolution_height}]+bestaudio/best"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": self.file_format
            }]
            self.status.emit("正在轉檔(可能需要數分鐘)...")  # 顯示轉檔提示
        else:
            self.status.emit(f"錯誤：不支援的格式 {self.file_format}")
            return

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # 提取影片資訊
                info = ydl.extract_info(self.url, download=False)
                available_formats = [
                    f"{fmt['ext']} - {fmt.get('height', 'N/A')}p"
                    for fmt in info.get('formats', [])
                ]
                selected_format = f"{self.file_format} - {self.resolution}"
                if selected_format not in available_formats:
                    self.status.emit(f"錯誤：所選格式 {selected_format} 不可用，請選擇其他格式")
                    self.list_available_formats()
                    return

                file_name = ydl.prepare_filename(info)  # 生成目標檔案名稱
                if os.path.exists(file_name):
                    self.status.emit("錯誤：已下載過選擇的影片")
                    return

                # 開始下載
                ydl.download([self.url])
            self.progress.emit(100)
            self.status.emit("下載完畢")
        except yt_dlp.utils.DownloadError as e:
            error_message = str(e)
            if "Requested format is not available" in error_message:
                self.status.emit("錯誤：此影片未提供所選擇的格式，正在列出可用格式...")
                self.list_available_formats()
            else:
                self.status.emit(f"下載失敗: {error_message}")
        except Exception as e:
            self.status.emit(f"下載失敗: {e}")

    def list_available_formats(self):
        try:
            with yt_dlp.YoutubeDL() as ydl:
                info = ydl.extract_info(self.url, download=False)
                formats = info.get("formats", [])
                format_list = "\n".join(
                    [f"{fmt['format_id']}: {fmt['ext']} - {fmt.get('height', 'N/A')}p" for fmt in formats]
                )
                # 使用彈出視窗顯示可用格式
                self.show_formats_popup(format_list)
        except Exception as e:
            self.status.emit(f"無法列出可用格式: {e}")

    def show_formats_popup(self, format_list):
        """顯示可用格式的彈出視窗"""
        msg_box = QMessageBox()
        msg_box.setWindowTitle("可用格式")
        msg_box.setText("以下是此影片的可用格式：")
        msg_box.setDetailedText(format_list)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()

    def hook(self, d):
        """處理下載進度更新的回調函數"""
        if d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes", d.get("total_bytes_estimate", 1))
            percent = int(downloaded / total * 100) if total > 0 else 0
            self.progress.emit(percent)
            self.status.emit(f"下載進度: {percent}%")
        elif d["status"] == "finished":
            self.status.emit("下載完成，正在處理檔案...")

class OldfishDownloader(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("oldfish 影片下載器")
        self.setGeometry(200, 200, 500, 300)
        self.setFixedSize(500, 300)  # 設置視窗的固定大小
        self.setWindowIcon(QIcon("icon.ico"))  # 設定視窗圖示

        # 設置 status_label，放大字體
        self.status_label = QLabel("", self)
        self.status_label.setStyleSheet("font-size: 30px;")  # 放大字體

        self.init_ui()
        self.init_menu_bar()  # 初始化工具欄

    def update_status_label_color(self):
        # 移除顏色設定，保持系統預設樣式
        pass

    def init_menu_bar(self):
        # 建立工具欄
        menu_bar = QMenuBar(self)
        menu_bar.setNativeMenuBar(False)  # 確保工具欄顯示在視窗內

        # 新增 "幫助" 選單
        help_menu = QMenu("幫助", self)


        # 新增 "傳送到 GitHub 頁面" 選項
        github_action = QAction("開啟 GitHub 頁面", self)
        github_action.triggered.connect(self.open_github_page)
        help_menu.addAction(github_action)

        # 新增 "關於 Downloader" 選項
        about_action = QAction("關於 Downloader", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

        # 將 "幫助" 選單加入工具欄
        menu_bar.addMenu(help_menu)

        # 將工具欄加入主佈局
        layout = self.layout() or QVBoxLayout(self)
        layout.setMenuBar(menu_bar)
        self.setLayout(layout)

    def open_github_page(self):
        # 開啟 GitHub 頁面
        webbrowser.open("https://github.com/oldfish101240/oldfish-Video-Downloader")  # 替換為實際的 GitHub 頁面 URL

    def show_about_dialog(self):
        # 顯示 "關於 Downloader" 的訊息框
        QMessageBox.information(self, "關於 Downloader", "oldfish Video Downloader\n版本：0.2.1\n作者：oldfish")

    def init_ui(self):
        self.url_input = QLineEdit(self)
        self.url_input.setPlaceholderText("請輸入 YouTube 影片網址...")

        # 解析度選單
        self.resolution_select = QComboBox(self)
        self.resolution_select.addItem("請選擇解析度")  # 預設選項
        self.resolution_select.addItems(["240p", "360p", "480p", "720p", "1080p", "2K", "4K"])
        self.resolution_select.setCurrentIndex(0)  # 預設選中「請選擇解析度」
        self.resolution_select.model().item(0).setEnabled(False)  # 禁用「請選擇解析度」

        # 格式選單
        self.format_select = QComboBox(self)
        self.format_select.addItem("請選擇格式")  # 預設選項
        self.format_select.addItems(["MP4", "MP3"])  # 新增 WEBM 格式
        self.format_select.setCurrentIndex(0)  # 預設選中「請選擇格式」
        self.format_select.model().item(0).setEnabled(False)  # 禁用「請選擇格式」

        self.download_button = QPushButton("下載", self)
        self.download_button.clicked.connect(self.start_download)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)

        # 設置進度條樣式
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
        
        self.open_folder_button = QPushButton("開啟下載資料夾", self)
        self.open_folder_button.clicked.connect(self.open_download_folder)

        layout = QVBoxLayout()
        url_layout = QHBoxLayout()
        controls_layout = QHBoxLayout()

        url_layout.addWidget(self.url_input)
        controls_layout.addWidget(self.resolution_select)
        controls_layout.addWidget(self.format_select)
        controls_layout.addWidget(self.download_button)

        layout.addWidget(self.status_label)
        layout.addLayout(url_layout)
        layout.addLayout(controls_layout)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.open_folder_button)

        self.setLayout(layout)

    def start_download(self):
        # 清空進度條
        self.progress_bar.setValue(0)

        url = self.url_input.text().strip()
        resolution = self.resolution_select.currentText()
        file_format = self.format_select.currentText()

        # 驗證輸入
        if not url.startswith("http"):
            self.status_label.setText("請輸入有效的 YouTube 影片網址")
            return
        if resolution == "請選擇解析度":
            self.status_label.setText("請選擇解析度")
            return
        if file_format == "請選擇格式":
            self.status_label.setText("請選擇格式")
            return

        self.download_thread = DownloadThread(url, resolution, file_format, self.status_label)
        self.download_thread.progress.connect(self.progress_bar.setValue)
        self.download_thread.status.connect(self.status_label.setText)
        self.download_thread.start()
    
    def open_download_folder(self):
        downloads_path = os.path.abspath("downloads")
        if not os.path.isdir(downloads_path):  # 確保是有效的資料夾
            QMessageBox.warning(self, "提示", "系統找不到下載資料夾，請先下載影片後再試。")
            return
        try:
            os.startfile(downloads_path)
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"無法開啟資料夾：{e}")
            return

if __name__ == "__main__":
    try:
        # 確保工作目錄為程式所在目錄
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        print(f"當前工作目錄: {os.getcwd()}")  # 打印當前工作目錄

        # 檢查並建立 downloads 資料夾
        downloads_path = os.path.join(script_dir, "downloads")
        if not os.path.isdir(downloads_path):
            print(f"資料夾 {downloads_path} 不存在，正在建立...")
            os.makedirs(downloads_path, exist_ok=True)
        else:
            print(f"資料夾 {downloads_path} 已存在。")
    except Exception as e:
        print(f"初始化工作目錄或資料夾失敗：{e}")
        sys.exit(1)

    app = QApplication(sys.argv)

    if ffmpeg_installed:
        try:
            window = OldfishDownloader()
            window.show()
        except Exception as e:
            print(f"初始化失敗：{e}")
    else:
        installer = Installer()
        installer.installation_finished.connect(lambda: OldfishDownloader().show())
        installer.installation_finished.connect(installer.close)
        installer.show()
        
    print(f"Python executable: {sys.executable}")
    print(f"Arguments: {sys.argv}")

    sys.exit(app.exec())

