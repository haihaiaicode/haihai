# 会议记录工具

这是一个可以直接部署到 GitHub Pages 的会议记录网页。网页使用浏览器内置的 Web Speech API，将语音实时转为文字；记录保存在当前浏览器的 `localStorage` 中，不会上传服务器。

## 网页版功能

- 开始、暂停、继续和结束会议记录
- 实时显示中文语音转写
- 自动保存历史记录，支持搜索、查看、删除
- 导出 TXT，导入 JSON 备份
- 手机和电脑浏览器均可使用

建议使用最新版 Google Chrome 或 Microsoft Edge，并允许麦克风权限。Safari 和 Firefox 对连续语音识别的支持不完整。

## 本地打开

双击 `index.html` 通常即可使用。若浏览器禁止本地文件的麦克风权限，可在此目录运行：

```text
python -m http.server 8080
```

然后打开 `http://localhost:8080`。

## 原桌面版

`main.py` 和 `run.bat` 是原来的 Windows + Whisper 离线版本，需要 Python、麦克风和模型文件；它们不会在 GitHub Pages 上运行。

桌面版用于捕捉电脑播放的声音。打开后，在音频设备中选择带有“系统音频（WASAPI 环回）”标记的设备，再点击开始记录。首次运行会下载 Whisper 模型，模型较大，请保持网络连接。

项目的 GitHub Actions 会在更新桌面版代码后自动生成 `MeetingRecorder-Windows.zip`。在仓库的 **Actions → Build Windows desktop app** 中打开最近一次运行，从 **Artifacts** 下载压缩包。后续可以将它附加到 GitHub Releases，作为网站的正式下载文件。

## 发布到 GitHub Pages

仓库设置中的 Pages 选择 `GitHub Actions` 即可。项目自带 `.github/workflows/pages.yml`，推送后会自动部署 `speech-to-text` 目录。
