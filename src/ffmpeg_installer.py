import sys
import os
import shutil
import zipfile
import requests
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel,
    QPushButton, QVBoxLayout, QProgressBar,
    QMessageBox, QHBoxLayout
)
from PyQt6.QtCore import QSize
import winsound
import concurrent.futures
import time

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
    def __init__(self):
        super().__init__()
        self.initUI()
        self.cancel_flag = False

    def initUI(self):
        self.setWindowTitle('安裝資訊')
        self.setFixedSize(QSize(400, 200))
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
        self.future.add_done_callback(self.install_ffmpeg)

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
        try:
            result = future.result()
            if result is None and not self.cancel_flag:
                with zipfile.ZipFile(self.ffmpeg_zip, 'r') as zip_ref:
                    zip_ref.extractall()
                os.remove(self.ffmpeg_zip)
                self.copy_downloader()
                winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS)
                self.close()
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

    def copy_downloader(self):
        try:
            shutil.copy("your_downloader.exe", os.getcwd())
        except Exception as e:
            QMessageBox.critical(self, '錯誤', f'複製主程式失敗：{e}')

    def cancel_download(self):
        self.cancel_flag = True
        self.executor.shutdown(wait=True)
        try:
            if os.path.exists(self.ffmpeg_zip + ".part"):
                os.remove(self.ffmpeg_zip + ".part")
        except Exception as e:
            print(f"刪除暫存檔案失敗：{e}")
        sys.exit()

def main():
    app = QApplication(sys.argv)
    installer = Installer()
    installer.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()