# Video Speed Pro (视频快速调速器)

一款基于 Python 和 PySide6 开发的 Windows 桌面视频调速工具。

### 功能特点
- **现代 UI**: 提供纯白/纯黑双色主题切换。
- **自动预览**: 拖入视频即刻自动播放预览效果。
- **批量处理**: 支持同时调速多个视频。
- **高精度进度**: 实时显示转换百分比。
- **范围调节**: 支持 0.5x - 2.0x 调速。

### 运行环境
1. 安装 Python 3.8+
2. 安装依赖: `pip install -r requirements.txt`
3. **关键**: 将 `ffmpeg.exe` 和 `ffprobe.exe` 放入根目录。

### 打包
使用 PyInstaller 封装为 EXE 即可离线运行。
