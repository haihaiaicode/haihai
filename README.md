# 会议记录工具

一个用于捕捉电脑播放声音并转换为文字的会议记录工具。

## 直接打开网站

**网页入口：** [https://haihaiaicode.github.io/haihai/](https://haihaiaicode.github.io/haihai/)

网页可以查看项目说明，也可以导入、导出浏览器中的会议记录。网页本身只能使用浏览器支持的麦克风语音识别；如果要准确捕捉电脑扬声器、视频会议或播放器发出的声音，请下载 Windows 桌面版。

## Windows 用户怎么用

1. 打开上方网页，点击右上角 **下载 Windows 版**；也可以进入本仓库的 [Actions](https://github.com/haihaiaicode/haihai/actions) 页面下载最新的 `MeetingRecorder-Windows` 构建文件。
2. 解压 `MeetingRecorder-Windows.zip`。
3. 双击 `MeetingRecorder.exe`。
4. 在音频设备列表中选择带有 **系统音频（WASAPI 环回）** 标记的设备。
5. 点击开始记录。会议结束后可以在程序中查看并导出记录。

首次运行 Whisper 模型可能需要下载较大的模型文件，请保持网络连接并耐心等待。

## 项目内容

- `speech-to-text/main.py`：Windows 桌面版，负责捕捉系统声音和 Whisper 转写
- `speech-to-text/run.bat`：使用 Python 启动桌面版的备用方式
- `speech-to-text/index.html`：网页入口
- `.github/workflows/build-windows.yml`：自动构建 Windows 版
- `.github/workflows/pages.yml`：自动部署 GitHub Pages 网站

会议记录默认保存在使用者自己的电脑上，不会自动上传到本项目仓库。
