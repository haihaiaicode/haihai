# 会议记录工具

## Windows 桌面版转写

Windows 版优先选择默认扬声器的 **系统音频 · WASAPI 环回** 设备，直接读取电脑播放的声音；也可在设备列表中选择麦克风。请用 `pip install -r requirements.txt` 安装依赖，然后运行 `python main.py`。首次使用会下载 faster-whisper 模型，已有模型则直接从本地加载。

桌面版默认使用 **均衡（small）** 模型，以降低内存占用。若更重视内存，可在开始前选 **低内存（base）**；若更重视准确率且内存充足，可选 **高精度（medium）**。首次选用一个新模型需要下载一次。模型在程序运行期间保留在内存中，选择其他模型后请重新启动程序，才能彻底释放旧模型占用。

连续发言约每 5 秒提交一段识别，停顿约 0.8 秒也会提交当前段。界面显示的是已完成识别的分段文字；本地 Whisper 在当前实现中不会逐字推送临时结果。识别耗时与电脑性能有关，停止后程序会等最后一段完成再写入 `transcript.txt`、`full_text.txt` 和 `segments.json`。

如果要记录会议里其他人通过扬声器播放的声音，请选择 **系统音频 · WASAPI 环回**；若要记录自己的发言，请选择麦克风。仅选择系统环回不会自动捕获本机麦克风的声音。

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
