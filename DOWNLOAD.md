# 下载与使用

网站入口： https://haihaiaicode.github.io/haihai/

普通用户应下载 GitHub Releases 中的 `MeetingRecorder-Setup.exe`。双击安装后，从开始菜单打开“会议记录工具”，不需要安装 Python，也不需要使用 `run.bat`。

程序启动后，在音频设备列表中选择“系统音频（WASAPI 环回）”，它会捕捉电脑扬声器、视频会议和播放器发出的声音。首次使用 Whisper 可能需要下载模型文件。

开发者才需要查看 `main.py`、`requirements.txt` 和 `run.bat`。GitHub Actions 会在桌面版代码更新后自动构建安装程序。
