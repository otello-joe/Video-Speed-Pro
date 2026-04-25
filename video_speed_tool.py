import sys
import os
import subprocess
import shutil
import re
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QListWidget, QFileDialog, 
                             QSlider, QLabel, QDoubleSpinBox, QProgressBar, 
                             QMessageBox, QFrame)
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

# 在代码开头添加这个函数
def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)
# --- 极简纯白样式表 ---
PURE_WHITE_STYLE = """
    QMainWindow { background-color: #FFFFFF; }
    QWidget { color: #333333; font-family: "Segoe UI", "Microsoft YaHei"; font-size: 13px; }
    
    /* 左侧视频容器 */
    QFrame#VideoContainer { 
        background-color: #FFFFFF; 
        border: 1px solid #EAEAEA; 
        border-radius: 8px; 
    }

    /* 右侧面板 */
    QFrame#SidePanel { 
        background-color: #FFFFFF; 
        border-left: 1px solid #F0F0F0; 
    }

    /* 任务列表 */
    QListWidget { 
        background-color: #FFFFFF; 
        border: 1px solid #EAEAEA; 
        border-radius: 4px; 
        outline: none; 
    }
    QListWidget::item { 
        padding: 10px; 
        border-bottom: 1px solid #F9F9F9; 
    }
    QListWidget::item:selected { 
        background-color: #F0F7FF; 
        color: #007AFF; 
        font-weight: bold;
    }

    /* 按钮 */
    QPushButton { 
        background-color: #F5F5F7; 
        border: 1px solid #E5E5E7; 
        border-radius: 4px; 
        padding: 8px; 
        font-weight: 500; 
    }
    QPushButton:hover { background-color: #EBEBEF; }
    
    QPushButton#ExportBtn { 
        background-color: #007AFF; 
        color: white; 
        border: none; 
        font-size: 15px; 
    }
    QPushButton#ExportBtn:hover { background-color: #0063CC; }

    /* 进度条 */
    QProgressBar { 
        border: none; 
        background-color: #F0F0F2; 
        height: 6px; 
        border-radius: 3px; 
        text-align: transparent;
    }
    QProgressBar::chunk { background-color: #007AFF; border-radius: 3px; }

    /* 滑动条 */
    QSlider::groove:horizontal { height: 4px; background: #EAEAEA; border-radius: 2px; }
    QSlider::handle:horizontal { 
        background: #007AFF; 
        width: 16px; 
        height: 16px; 
        margin: -6px 0; 
        border-radius: 8px; 
    }
"""

class ProcessThread(QThread):
    progress_update = Signal(int)
    status_update = Signal(str)
    finished = Signal()

    def __init__(self, files, speed, ffmpeg_path):
        super().__init__()
        self.files = files
        self.speed = speed
        self.ffmpeg_path = ffmpeg_path

    def get_duration(self, file_path):
        try:
            ffprobe_path = self.ffmpeg_path.replace("ffmpeg.exe", "ffprobe.exe")
            cmd = [ffprobe_path, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return float(result.stdout.strip())
        except: return 0

    def run(self):
        v_f, a_f = f"setpts={1/self.speed}*PTS", f"atempo={self.speed}"
        for i, file_path in enumerate(self.files):
            total_dur = self.get_duration(file_path)
            base_name = os.path.basename(file_path)
            self.status_update.emit(f"处理中 ({i+1}/{len(self.files)})")
            
            output_path = os.path.join(os.path.dirname(file_path), f"{os.path.splitext(base_name)[0]}_{self.speed}x{os.path.splitext(base_name)[1]}")
            cmd = [self.ffmpeg_path, '-y', '-i', file_path, '-filter_complex', f"[0:v]{v_f}[v];[0:a]{a_f}[a]",
                   '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23', '-progress', 'pipe:1', output_path]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            while True:
                line = process.stdout.readline()
                if not line: break
                if "out_time_ms=" in line:
                    try:
                        ms = int(line.split('=')[1].strip())
                        if total_dur > 0: self.progress_update.emit(min(int((ms/1000000)/total_dur*100), 100))
                    except: pass
            process.wait()
        self.finished.emit()

class ModernSpeedTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("视频快速调速器 Pro")
        self.resize(1000, 680)
        self.setAcceptDrops(True)
        self.file_list = []

        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.ffmpeg_exe = get_resource_path("ffmpeg.exe")

        self.initUI()
        self.initPlayer()
        self.setStyleSheet(PURE_WHITE_STYLE)

    def initUI(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- 左侧：纯白视频区域 ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # 视频外框，强制背景为白色
        self.video_container = QFrame()
        self.video_container.setObjectName("VideoContainer")
        container_layout = QVBoxLayout(self.video_container)
        container_layout.setContentsMargins(1, 1, 1, 1) # 极细边框
        
        self.video_widget = QVideoWidget()
        # 初始化时播放器也是白的
        self.video_widget.setAttribute(Qt.WA_OpaquePaintEvent, False)
        container_layout.addWidget(self.video_widget)
        
        left_layout.addWidget(self.video_container)
        
        # 底部播放控制
        controls_row = QHBoxLayout()
        self.btn_play = QPushButton("播放 / 暂停")
        self.btn_play.setFixedWidth(150)
        controls_row.addStretch()
        controls_row.addWidget(self.btn_play)
        controls_row.addStretch()
        left_layout.addLayout(controls_row)

        # --- 右侧：紧凑面板 ---
        self.side_panel = QFrame()
        self.side_panel.setObjectName("SidePanel")
        self.side_panel.setFixedWidth(320)
        side_layout = QVBoxLayout(self.side_panel)
        side_layout.setContentsMargins(15, 10, 10, 10)
        side_layout.setSpacing(8)

        side_layout.addWidget(QLabel("任务列表"))
        
        # 列表占据最大空间
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.load_selected_video)
        side_layout.addWidget(self.list_widget, stretch=10)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("添加视频")
        self.btn_clear = QPushButton("清空列表")
        self.btn_add.clicked.connect(self.add_files)
        self.btn_clear.clicked.connect(self.clear_list)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_clear)
        side_layout.addLayout(btn_row)

        side_layout.addSpacing(10)
        side_layout.addWidget(QLabel("倍速设定 (0.5x - 2.0x)"))
        
        speed_layout = QHBoxLayout()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(50, 200)
        self.slider.setValue(100)
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.5, 2.0)
        self.speed_spin.setValue(1.0)
        self.speed_spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.speed_spin.setSuffix(" x")
        self.speed_spin.setAlignment(Qt.AlignCenter)
        self.speed_spin.setFixedWidth(60)
        speed_layout.addWidget(self.slider)
        speed_layout.addWidget(self.speed_spin)
        side_layout.addLayout(speed_layout)

        self.slider.valueChanged.connect(lambda v: self.speed_spin.setValue(v/100))
        self.speed_spin.valueChanged.connect(self.on_speed_changed)

        side_layout.addSpacing(10)
        
        # 底部状态
        status_box = QHBoxLayout()
        self.status_label = QLabel("就绪")
        self.status_percent = QLabel("0%")
        status_box.addWidget(self.status_label)
        status_box.addStretch()
        status_box.addWidget(self.status_percent)
        side_layout.addLayout(status_box)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        side_layout.addWidget(self.progress_bar)

        self.btn_start = QPushButton("导出全部视频")
        self.btn_start.setObjectName("ExportBtn")
        self.btn_start.setFixedHeight(45)
        self.btn_start.clicked.connect(self.start_process)
        side_layout.addWidget(self.btn_start)

        main_layout.addWidget(left_widget, stretch=7)
        main_layout.addWidget(self.side_panel, stretch=3)

    def initPlayer(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.btn_play.clicked.connect(self.toggle_play)

    def on_speed_changed(self, val):
        self.slider.setValue(int(val * 100))
        if self.player.playbackState() != QMediaPlayer.PlaybackState.StoppedState:
            self.player.setPlaybackRate(val)

    def load_selected_video(self, item):
        idx = self.list_widget.row(item)
        self.player.setSource(QUrl.fromLocalFile(self.file_list[idx]))
        self.player.setPlaybackRate(self.speed_spin.value())
        self.player.play()
        self.status_label.setText("正在预览")
        self.status_label.setStyleSheet("color: #007AFF;")

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState: self.player.pause()
        else: self.player.play()

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择视频", "", "Videos (*.mp4 *.avi *.mkv *.mov)")
        if files:
            was_empty = len(self.file_list) == 0
            for f in files:
                if f not in self.file_list:
                    self.file_list.append(f)
                    self.list_widget.addItem(os.path.basename(f))
            if was_empty: self.auto_preview_first()

    def auto_preview_first(self):
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            self.load_selected_video(self.list_widget.item(0))

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls(): e.accept()
        else: e.ignore()

    def dropEvent(self, e: QDropEvent):
        was_empty = len(self.file_list) == 0
        added = False
        for u in e.mimeData().urls():
            f = u.toLocalFile()
            if f.lower().endswith(('.mp4', '.avi', '.mkv', '.mov')):
                if f not in self.file_list:
                    self.file_list.append(f)
                    self.list_widget.addItem(os.path.basename(f))
                    added = True
        if was_empty and added: self.auto_preview_first()

    def clear_list(self):
        self.player.stop()
        self.file_list.clear()
        self.list_widget.clear()
        self.progress_bar.setValue(0)
        self.status_percent.setText("0%")
        self.status_label.setText("列表已清空")

    def start_process(self):
        if not self.file_list: return
        if not os.path.exists(self.ffmpeg_exe):
            QMessageBox.critical(self, "错误", "缺少 ffmpeg.exe!")
            return
        self.player.stop()
        self.btn_start.setEnabled(False)
        self.thread = ProcessThread(self.file_list, self.speed_spin.value(), self.ffmpeg_exe)
        self.thread.progress_update.connect(self.update_progress)
        self.thread.status_update.connect(lambda s: self.status_label.setText(s))
        self.thread.finished.connect(self.on_finished)
        self.thread.start()

    def update_progress(self, val):
        self.progress_bar.setValue(val)
        self.status_percent.setText(f"{val}%")

    def on_finished(self):
        self.btn_start.setEnabled(True)
        self.status_label.setText("✔ 转换完成")
        self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernSpeedTool()
    window.show()
    sys.exit(app.exec())