# 下载与使用

网站入口： https://haihaiaicode.github.io/haihai/

普通用户应下载 GitHub Releases 中的 `MeetingRecorder-Setup.exe`。这是一个单独的安装程序，不需要解压。双击安装后，从开始菜单打开“会议记录工具”，不需要安装 Python，也不需要使用 `run.bat`。

程序启动后，在音频设备列表中选择“系统音频（WASAPI 环回）”，它会捕捉电脑扬声器、视频会议和播放器发出的声音。首次使用 Whisper 可能需要下载模型文件。

开发者才需要查看 `main.py`、`requirements.txt` 和 `run.bat`。GitHub Actions 会在桌面版代码更新后自动构建安装程序。Actions 页面里的 Artifact 是构建中间产物，正式用户应从 Releases 下载安装程序。

Windows 可能显示“Windows 已保护你的电脑”，这是因为免费项目没有购买代码签名证书，并不代表程序来自不明网站。点击“更多信息”后可以选择“仍要运行”。要完全消除这个提示，需要购买并配置代码签名证书。
