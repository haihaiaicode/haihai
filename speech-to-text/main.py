"""
会议语音转文字工具
- 自动捕获电脑系统音频或麦克风输入
- 使用 Whisper AI 实时转成文字
- 自动保存到 transcripts/ 文件夹
"""

import os
import sys

# ---- 模型下载到 D 盘 + 使用国内镜像（解决网络问题）----
_HF_DIR = r"D:\ai-models\huggingface"
if not os.environ.get("HF_HOME"):
    os.environ["HF_HOME"] = _HF_DIR
    os.environ["HF_HUB_CACHE"] = os.path.join(_HF_DIR, "hub")
    os.makedirs(os.environ["HF_HUB_CACHE"], exist_ok=True)
# 国内 Hugging Face 镜像
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
# 禁用 Xet/CAS 存储（镜像不支持）
os.environ["HF_HUB_ENABLE_HF_XET"] = "0"

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
import time
import json
import random as _random
import math
from datetime import datetime
from collections import deque

import numpy as np
import sounddevice as sd

# ============================================================
# 配置
# ============================================================
SAMPLE_RATE = 16000
CHUNK_DURATION = 120.0          # 连续说话 2 分钟强制分段（避免等太久看不到结果）
SILENCE_THRESHOLD = 0.012       # RMS 能量阈值
SILENCE_TIMEOUT = 0.8           # 静音 0.8s 认为说完一句话（自然断句）
OVERLAP_DURATION = 1.0          # 强制分段时保留 1s 重叠，避免词语被切断
MIN_SEGMENT_DURATION = 0.6      # 最短 0.6s 才识别（过滤噪音碎片）
MODEL_SIZE = "medium"
DEVICE = "cpu"
MAX_TRANSCRIBE_WORKERS = 1
CPU_THREADS = 4

# ============================================================
# 配色方案 —— 深空科技风 (Dark Tech Theme)
# ============================================================
# 背景层次
BG_DEEP      = "#060b14"   # 最深底
BG_MAIN      = "#0a0f1e"   # 主背景
BG_CARD      = "#111827"   # 卡片 / 面板
BG_TEXT      = "#0c111d"   # 文本区
BG_FOOTER    = "#0d1322"   # 底部状态栏
BG_TIMER     = "#111827"   # 计时器背景

# 边框
BORDER       = "#1e293b"   # 通用边框
BORDER_LIGHT = "#283348"   # 悬停 / 亮边框

# 按钮 - 主操作（开始录制）
BTN_PRIMARY       = "#0ea5e9"
BTN_PRIMARY_HOVER = "#38bdf8"
BTN_PRIMARY_ACTIVE = "#0284c7"

# 按钮 - 暂停
BTN_WARN        = "#f59e0b"
BTN_WARN_HOVER  = "#fbbf24"
BTN_WARN_ACTIVE = "#d97706"

# 按钮 - 停止
BTN_DANGER        = "#ef4444"
BTN_DANGER_HOVER  = "#f87171"
BTN_DANGER_ACTIVE = "#dc2626"

# 按钮 - 历史 / 次级
BTN_DARK        = "#334155"
BTN_DARK_HOVER  = "#475569"

# 文字
TEXT_PRIMARY   = "#e2e8f0"
TEXT_SECONDARY = "#94a3b8"
TEXT_MUTED     = "#64748b"

# 强调色
ACCENT        = "#22d3ee"   # 青色点缀
GREEN         = "#10b981"   # 成功状态
RED           = "#ef4444"   # 错误 / 录制中
AMBER         = "#f59e0b"   # 警告
PARTICLE_CLR  = "#38bdf8"   # 粒子颜色

# ============================================================
# 圆角按钮 (Canvas-based) — 带悬停粒子效果
# ============================================================
class RoundedButton(tk.Frame):
    """Canvas 圆角按钮：悬停变色 + 背部光晕 + 粒子"""

    def __init__(self, parent, text="", command=None,
                 bg_color=BTN_PRIMARY, hover_color=BTN_PRIMARY_HOVER,
                 fg_color="#ffffff", font=None,
                 width=140, height=38, radius=10,
                 particle=True, state="normal"):
        try:
            p_bg = parent.cget("bg")
        except Exception:
            p_bg = BG_MAIN

        margin = 24 if particle else 6
        cw = width + margin * 2
        ch = height + margin * 2

        super().__init__(parent, bg=p_bg, highlightthickness=0, bd=0)

        self.canvas = tk.Canvas(self, width=cw, height=ch,
                                bg=p_bg, highlightthickness=0)
        self.canvas.pack()

        self.bg_color = bg_color
        self.hover_color = hover_color
        self.fg_color = fg_color
        self.font = font or ("Microsoft YaHei", 10)
        self.radius = radius
        self._text = text
        self._state = state
        self._cmd = command
        self._hovered = False
        self._particle_enabled = particle
        self._particles = []
        self._anim_job = None
        self._glow_phase = 0.0

        self._bx1 = margin
        self._by1 = margin
        self._bx2 = margin + width
        self._by2 = margin + height

        self._draw_static()
        self._bind_events()

    # ======== 静态层：按钮主体 + 文字（只在状态变化时重绘）========
    def _draw_static(self):
        self.canvas.delete("static")

        if self._state == "disabled":
            fill = "#374151"
            fg  = "#6b7280"
        elif self._hovered:
            fill = self.hover_color
            fg  = self.fg_color
        else:
            fill = self.bg_color
            fg  = self.fg_color

        x1, y1, x2, y2 = self._bx1, self._by1, self._bx2, self._by2
        r = self.radius
        d = 2 * r
        kw = {"fill": fill, "outline": fill, "tags": "static"}
        self.canvas.create_rectangle(x1 + r, y1, x2 - r, y2, **kw)
        self.canvas.create_rectangle(x1, y1 + r, x2, y2 - r, **kw)
        for cx, cy in [(x1, y1), (x2 - d, y1),
                        (x1, y2 - d), (x2 - d, y2 - d)]:
            self.canvas.create_oval(cx, cy, cx + d, cy + d, **kw)

        self.canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2,
                                text=self._text, fill=fg,
                                font=self.font, tags="static")

    # ======== 动态层：光晕 + 粒子（每帧刷新）========
    def _draw_fx(self):
        self.canvas.delete("fx")
        if not self._hovered or not self._particle_enabled:
            return

        # -- 背部光晕（1 层，简洁）--
        x1, y1, x2, y2 = self._bx1, self._by1, self._bx2, self._by2
        r = self.radius
        breathe = 1.0 + math.sin(self._glow_phase) * 0.6
        ex = 8 * breathe
        a = 0.06 * breathe

        glow_r, glow_g, glow_b = 56, 200, 255
        color = f"#{int(glow_r*a):02x}{int(glow_g*a):02x}{int(glow_b*a):02x}"

        gx1, gy1 = x1 - ex, y1 - ex
        gx2, gy2 = x2 + ex, y2 + ex
        gr = r + ex
        gd = 2 * gr
        kw = {"fill": color, "outline": "", "tags": "fx"}
        self.canvas.create_rectangle(gx1 + gr, gy1, gx2 - gr, gy2, **kw)
        self.canvas.create_rectangle(gx1, gy1 + gr, gx2, gy2 - gr, **kw)
        for cx, cy in [(gx1, gy1), (gx2 - gd, gy1),
                        (gx1, gy2 - gd), (gx2 - gd, gy2 - gd)]:
            self.canvas.create_oval(cx, cy, cx + gd, cy + gd, **kw)

        # -- 粒子 --
        for p in self._particles:
            a = max(0.0, min(1.0, p["life"]))
            glow_s = p["size"] * 2.0 * a
            glow_a = a * 0.12
            gr2 = int(56 * glow_a)
            gg = int(200 * glow_a)
            gb = int(255 * glow_a)
            self.canvas.create_oval(
                p["x"] - glow_s, p["y"] - glow_s,
                p["x"] + glow_s, p["y"] + glow_s,
                fill=f"#{gr2:02x}{gg:02x}{gb:02x}",
                outline="", tags="fx",
            )
            core_s = max(0.3, p["size"] * a)
            self.canvas.create_oval(
                p["x"] - core_s, p["y"] - core_s,
                p["x"] + core_s, p["y"] + core_s,
                fill=f"#{int(56*a):02x}{int(200*a):02x}{int(255*a):02x}",
                outline="", tags="fx",
            )

        # 确保 static 层（按钮）始终在 fx 层之上
        self.canvas.tag_raise("static")

    # ======== 事件 ========
    def _bind_events(self):
        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<Button-1>", self._on_click)

    def _on_enter(self, _e):
        if self._state == "disabled":
            return
        self._hovered = True
        self._glow_phase = 0.0
        self._draw_static()
        self._draw_fx()
        if self._particle_enabled:
            self._start_fx_loop()

    def _on_leave(self, _e):
        self._hovered = False
        self._draw_static()
        self._draw_fx()
        self._stop_fx_loop()

    def _on_click(self, _e):
        if self._state == "disabled":
            return
        if self._cmd:
            self._cmd()

    # ======== 动画循环（只刷新 fx 层）========
    def _start_fx_loop(self):
        self._anim_job = self.canvas.after(50, self._fx_tick)

    def _stop_fx_loop(self):
        if self._anim_job is not None:
            self.canvas.after_cancel(self._anim_job)
            self._anim_job = None
        self._particles.clear()

    def _fx_tick(self):
        self._glow_phase += 0.1

        # 生成粒子（从按钮边缘外侧，确保不被按钮遮住）
        x1, y1, x2, y2 = self._bx1, self._by1, self._bx2, self._by2
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        hw = (x2 - x1) / 2
        hh = (y2 - y1) / 2
        for _ in range(_random.randint(2, 4)):
            angle = _random.uniform(0, 2 * math.pi)
            # 从按钮边缘到边缘外 8px 生成，立即可见
            dist = _random.uniform(hw * 0.88, hw + 8)
            x = cx + math.cos(angle) * dist
            y = cy + math.sin(angle) * dist * (hh / max(hw, 1))
            speed = _random.uniform(0.5, 1.1)
            self._particles.append({
                "x": x, "y": y,
                "dx": math.cos(angle) * speed,
                "dy": math.sin(angle) * speed * (hh / max(hw, 1)),
                "life": 1.0,
                "size": _random.uniform(0.4, 0.9),
            })

        # 更新存活粒子
        alive = []
        for p in self._particles:
            p["x"] += p["dx"]
            p["y"] += p["dy"]
            p["life"] -= 0.025
            if p["life"] > 0:
                alive.append(p)
        if len(alive) > 50:
            alive = alive[-35:]
        self._particles = alive

        # 只刷新动态层
        self._draw_fx()

        if self._hovered:
            self._anim_job = self.canvas.after(50, self._fx_tick)
        else:
            self._anim_job = None

    # ======== 外部接口 ========
    def config(self, **kw):
        if "state" in kw:
            self._state = kw["state"]
        if "text" in kw:
            self._text = kw["text"]
        if "bg" in kw:
            self.bg_color = kw["bg"]
        self._draw_static()

    def cget(self, key):
        if key == "state":
            return self._state
        if key == "text":
            return self._text
        return None


# ============================================================
# 音频设备
# ============================================================
def list_input_devices():
    """列出所有可用的音频输入设备（优先系统音频环回设备）"""
    result = []
    try:
        host_apis = sd.query_hostapis()
    except Exception:
        host_apis = []

    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] <= 0:
            continue

        name = dev["name"]
        hostapi_name = host_apis[dev["hostapi"]]["name"] if dev["hostapi"] < len(host_apis) else "Unknown"
        is_wasapi = "WASAPI" in hostapi_name

        # 判断是否为环回设备（可捕获系统音频）
        name_lower = name.lower()
        is_loopback = (
            "loopback" in name_lower
            or "stereo mix" in name_lower
            or "立体声混音" in name       # Windows 中文 Stereo Mix
            or "what u hear" in name_lower
            or "wave out" in name_lower
        )

        # 去掉明确的麦克风设备
        is_mic = (
            "microphone" in name_lower
            or "mic" in name_lower
            or "麦克风" in name
            or "话筒" in name
            or "front panel" in name_lower
            or "rear" in name_lower
            or "line in" in name_lower
        )

        if is_loopback and not is_mic:
            device_type = "【系统音频】"
        elif is_mic:
            device_type = "【麦克风】  "
        elif is_wasapi:
            device_type = "【WASAPI】  "
        else:
            device_type = "【其他】    "

        result.append({
            "index": idx,
            "name": name,
            "hostapi": hostapi_name,
            "is_wasapi": is_wasapi,
            "channels": dev["max_input_channels"],
            "sample_rate": int(dev["default_samplerate"]),
            "is_loopback": is_loopback and not is_mic,
            "is_mic": is_mic,
            "label": f"{device_type} {name}"
        })
    return result


def pick_best_device(devices):
    """自动选择最合适的设备：WASAPI 环回 > 任意环回 > WASAPI 麦克风 > 任意设备"""
    if not devices:
        return None
    # 1) 优先选 WASAPI 环回设备（Windows 上最可靠的系统音频捕获方式）
    for d in devices:
        if d["is_loopback"] and d.get("is_wasapi"):
            return d
    # 2) 其次选任意环回设备
    for d in devices:
        if d["is_loopback"]:
            return d
    # 3) WASAPI 麦克风
    for d in devices:
        if d["is_mic"] and d.get("is_wasapi"):
            return d
    # 4) 兜底：第一个设备
    return devices[0]


# ============================================================
# 语音活动检测 (VAD)
# ============================================================
class VAD:
    """基于 RMS 能量的简单 VAD"""

    def __init__(self, threshold=SILENCE_THRESHOLD, silence_timeout=SILENCE_TIMEOUT):
        self.threshold = threshold
        self.silence_timeout = silence_timeout
        self.silence_frames = 0
        self.silence_frames_limit = 0
        self.is_speaking = False

    def configure(self, sample_rate, frame_size):
        """根据采样率和帧大小计算静音帧数阈值"""
        frame_sec = frame_size / sample_rate
        self.silence_frames_limit = max(1, int(self.silence_timeout / frame_sec))

    def process(self, audio_chunk):
        """返回当前帧是否为语音"""
        if len(audio_chunk) == 0:
            return self.is_speaking

        rms = float(np.sqrt(np.mean(audio_chunk.astype(np.float64) ** 2)))

        if rms > self.threshold:
            self.silence_frames = 0
            self.is_speaking = True
        else:
            self.silence_frames += 1
            if self.silence_frames > self.silence_frames_limit:
                self.is_speaking = False

        return self.is_speaking

    def reset(self):
        self.silence_frames = 0
        self.is_speaking = False


# ============================================================
# 音频工具
# ============================================================
def resample_audio(audio, orig_sr, target_sr):
    """线性插值重采样（无需 scipy）"""
    if orig_sr == target_sr:
        return audio
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    duration = len(audio) / orig_sr
    target_len = int(duration * target_sr)
    x_orig = np.linspace(0, duration, len(audio))
    x_target = np.linspace(0, duration, target_len)
    return np.interp(x_target, x_orig, audio).astype(np.float32)


# ============================================================
# 转录引擎
# ============================================================
class Transcriber:
    """封装 faster-whisper 模型（从国内镜像直接下载，绕过 CAS/Xet）"""

    _MIRROR = "https://hf-mirror.com"
    _REPO = "Systran/faster-whisper-{size}"

    # 模型文件清单（如果 API 获取失败，使用此硬编码列表）
    _KNOWN_FILES = [
        "config.json",
        "model.bin",
        "tokenizer.json",
        "vocabulary.txt",
    ]

    def __init__(self, model_size=MODEL_SIZE, device=DEVICE):
        self.model_size = model_size
        self.device = device
        self.model = None
        self._lock = threading.Lock()
        self.loaded = False

    @property
    def _local_dir(self):
        """模型本地存储路径"""
        return os.path.join(
            os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface")),
            "hub",
            f"models--Systran--faster-whisper-{self.model_size}",
        )

    def _download_file(self, url, dest_path, max_retries=8):
        """下载单个文件，支持断点续传 + 自动重试（处理 429 限流）"""
        import urllib.request
        import urllib.error

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        # 已完成则跳过
        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
            print(f"  跳过（已存在）: {os.path.basename(dest_path)}")
            return True

        tmp_path = dest_path + ".part"
        name = os.path.basename(dest_path)

        for attempt in range(max_retries):
            try:
                # 断点续传：检查已下载的大小
                existing = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0

                req = urllib.request.Request(url)
                req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0)")
                if existing > 0:
                    req.add_header("Range", f"bytes={existing}-")

                with urllib.request.urlopen(req, timeout=120) as resp:
                    # 206 = 服务器支持断点续传；200 = 从头开始
                    if resp.status == 206:
                        total = existing + int(resp.headers.get("Content-Length", 0))
                        mode = "ab"
                        downloaded = existing
                    else:
                        total = int(resp.headers.get("Content-Length", 0))
                        mode = "wb"
                        downloaded = 0
                        existing = 0

                    with open(tmp_path, mode) as f:
                        while True:
                            chunk = resp.read(1024 * 1024)  # 1MB
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                pct = downloaded * 100 // total
                                mb_dl = downloaded // (1024 * 1024)
                                mb_total = total // (1024 * 1024)
                                print(f"\r  下载 {name}: {pct}% ({mb_dl}MB / {mb_total}MB)", end="")

                print()  # 换行

                # 校验文件大小
                actual = os.path.getsize(tmp_path)
                if total > 0 and actual < total:
                    raise Exception(f"文件不完整 ({actual}/{total} bytes)，将重试")

                os.replace(tmp_path, dest_path)
                return True

            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = min(2 ** (attempt + 1), 120)  # 2,4,8,16,32,64,120...
                    print(f"  限流 429，{wait}秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(wait)
                else:
                    raise e
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = min(2 ** (attempt + 1), 60)
                    print(f"  失败: {e}，{wait}秒后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(wait)
                else:
                    # 最后一次不删 .part，方便下次续传
                    raise RuntimeError(f"下载 {name} 失败（已重试 {max_retries} 次）: {e}")

        return False

    def _download_from_mirror(self):
        """从 hf-mirror 直接下载模型文件（使用标准 HTTP，不走 CAS/Xet）"""
        import urllib.request
        import json as _json

        repo = self._REPO.format(size=self.model_size)
        base_url = f"{self._MIRROR}/{repo}/resolve/main"
        local_base = self._local_dir

        print(f"[模型下载] 从 {self._MIRROR}/{repo} 下载...")

        # 1. 获取文件列表
        files = []
        api_url = f"{self._MIRROR}/api/models/{repo}/tree/main?recursive=true"
        try:
            req = urllib.request.Request(api_url)
            req.add_header("User-Agent", "Mozilla/5.0")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = _json.loads(resp.read())
            files = [f["path"] for f in data if f.get("type") == "file"]
            print(f"  获取到 {len(files)} 个文件")
        except Exception:
            print("  API 获取文件列表失败，使用默认列表")
            files = list(self._KNOWN_FILES)

        if not files:
            raise RuntimeError("无法获取模型文件列表")

        # 2. 下载每个文件到 snapshots 目录
        # 跳过不需要的文件
        skip_files = {".gitattributes", "README.md"}
        files = [f for f in files if f not in skip_files]

        snapshot_dir = os.path.join(local_base, "snapshots", "main")
        os.makedirs(snapshot_dir, exist_ok=True)

        for i, fname in enumerate(files):
            url = f"{base_url}/{fname}"
            dest = os.path.join(snapshot_dir, fname)
            print(f"  [{i+1}/{len(files)}] 下载: {fname}")
            try:
                self._download_file(url, dest)
            except Exception as e:
                raise RuntimeError(
                    f"下载 {fname} 失败: {e}\n"
                    f"请检查网络后重试（已下载的 .part 文件会自动续传）"
                )
            # 文件之间稍作间隔，避免触发限流
            if i < len(files) - 1:
                time.sleep(1)

        # 3. 创建 refs 指向 snapshot
        refs_dir = os.path.join(local_base, "refs")
        os.makedirs(refs_dir, exist_ok=True)
        with open(os.path.join(refs_dir, "main"), "w") as f:
            f.write("main")

        print(f"  模型下载完成 → {snapshot_dir}")
        return snapshot_dir

    def load(self):
        """加载模型（优先本地，否则从镜像下载）"""
        if self.loaded:
            return
        with self._lock:
            if self.loaded:
                return

            from faster_whisper import WhisperModel

            compute = "int8" if self.device == "cpu" else "float16"

            # 检查本地是否已有模型
            snapshot_dir = os.path.join(self._local_dir, "snapshots", "main")
            local_exists = (
                os.path.isdir(snapshot_dir)
                and os.path.exists(os.path.join(snapshot_dir, "model.bin"))
            )

            if local_exists:
                # 本地已有，直接加载
                print(f"[模型] 从本地加载: {snapshot_dir}")
                self.model = WhisperModel(
                    snapshot_dir,
                    device=self.device,
                    compute_type=compute,
                    num_workers=2,
                    cpu_threads=CPU_THREADS,
                )
                self.loaded = True
                return

            # 需要下载
            try:
                model_path = self._download_from_mirror()
                self.model = WhisperModel(
                    model_path,
                    device=self.device,
                    compute_type=compute,
                    num_workers=2,
                    cpu_threads=CPU_THREADS,
                )
                self.loaded = True
            except Exception as e:
                raise RuntimeError(f"模型下载失败: {e}")

    def transcribe(self, audio, language="zh"):
        """
        转录音频。
        返回 (text: str, error: str|None)
        """
        if not self.loaded or self.model is None:
            return "", "模型未加载"

        # 预处理
        audio = np.asarray(audio, dtype=np.float32)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if len(audio) < SAMPLE_RATE * 0.1:
            return "", None

        try:
            # 简体中文引导提示（繁体→简体）
            prompt = "以下是普通话的简体中文句子。" if language == "zh" else None

            segments, _info = self.model.transcribe(
                audio,
                language=language if language != "auto" else None,
                beam_size=3,
                best_of=3,
                vad_filter=True,
                initial_prompt=prompt,
                vad_parameters=dict(
                    threshold=0.5,
                    min_speech_duration_ms=100,
                    min_silence_duration_ms=300,
                ),
            )
            parts = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
            text = " ".join(parts)

            # 后处理：繁体→简体（zhconv 兜底）
            if language == "zh" and text:
                text = self._to_simplified(text)

            return text, None
        except Exception as e:
            return "", str(e)

    @staticmethod
    def _to_simplified(text):
        """繁体中文 → 简体中文（优先用 zhconv，否则用内置映射）"""
        try:
            from zhconv import convert
            return convert(text, "zh-cn")
        except ImportError:
            pass

        # 内置常见繁简映射（zhconv 不可用时的兜底）
        _TS_MAP = str.maketrans({
            "這": "这", "個": "个", "們": "们", "來": "来", "時": "时",
            "說": "说", "會": "会", "過": "过", "開": "开", "對": "对",
            "於": "于", "現": "现", "裡": "里", "後": "后", "麼": "么",
            "為": "为", "與": "与", "嗎": "吗", "還": "还", "進": "进",
            "實": "实", "體": "体", "機": "机", "應": "应", "關": "关",
            "頭": "头", "沒": "没", "見": "见", "從": "从", "當": "当",
            "經": "经", "種": "种", "認": "认", "讓": "让", "問": "问",
            "間": "间", "將": "将", "發": "发", "給": "给", "無": "无",
            "繫": "系", "學": "学", "點": "点", "業": "业", "動": "动",
            "嗎": "吗", "聽": "听", "寫": "写", "麼": "么", "妳": "你",
            "愛": "爱", "電": "电", "話": "话", "軍": "军", "國": "国",
            "長": "长", "門": "门", "員": "员", "萬": "万", "裡": "里",
        })
        return text.translate(_TS_MAP)


# ============================================================
# GUI 主程序
# ============================================================
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("🎙 会议语音转文字工具")
        self.root.geometry("880x720")
        self.root.minsize(680, 520)
        self.root.configure(bg=BG_MAIN)

        # -- 状态 --
        self.recording = False
        self.paused = False
        self.devices: list = []
        self.selected: dict | None = None
        self.stream: sd.InputStream | None = None
        self.audio_sr = SAMPLE_RATE
        self.segment_count = 0

        # -- 队列 --
        # Keep captured audio queued while Whisper catches up; never silently drop it.
        self.audio_q = queue.Queue()
        self.result_q = queue.Queue()
        self.transcribe_q = queue.Queue()

        # -- 缓冲 --
        self.speech_buf = deque()
        self.vad = VAD()
        self.transcriber = Transcriber()

        # -- 转录并发控制 --
        self._finalize_pending = False
        self._transcribe_thread = threading.Thread(target=self._transcribe_loop, daemon=True)
        self._transcribe_thread.start()

        # -- 结果 --
        self.full_text = ""
        self.segments: list[dict] = []

        # -- 文件 --
        self.session_dir = ""
        self.output_path = ""

        # -- 线程控制 --
        self._stop_flag = threading.Event()
        self._proc_thread: threading.Thread | None = None
        self._start_time = 0.0

        # -- 样式 --
        self._setup_styles()

        # -- UI --
        self._build_ui()
        self._refresh_devices()
        self._poll_results()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # 卡片面板
        style.configure("Card.TLabelframe",
                        background=BG_CARD, relief="flat", borderwidth=0)
        style.configure("Card.TLabelframe.Label",
                        background=BG_CARD, foreground=TEXT_PRIMARY,
                        font=("Microsoft YaHei", 10, "bold"))

        # 通用按钮（仅用于历史窗口等辅助按钮）
        style.configure("TButton",
                        font=("Microsoft YaHei", 9), padding=(10, 4))
        style.configure("TCombobox",
                        font=("Microsoft YaHei", 9))
        style.configure("TLabel",
                        font=("Microsoft YaHei", 9), background=BG_MAIN,
                        foreground=TEXT_SECONDARY)
        style.configure("Status.TLabel",
                        font=("Microsoft YaHei", 9))
        style.configure("TScrollbar",
                        background=BORDER, troughcolor=BG_MAIN)

    # ==================== UI ====================
    def _build_ui(self):
        # ── 主容器 ──
        main_frame = tk.Frame(self.root, bg=BG_MAIN)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # ═══ 设备设置卡片 ═══
        card_dev = ttk.LabelFrame(main_frame, text=" 音频设置 ",
                                  style="Card.TLabelframe", padding=(16, 12))
        card_dev.pack(fill=tk.X, pady=(0, 8))

        dev_row = tk.Frame(card_dev, bg=BG_CARD)
        dev_row.pack(fill=tk.X)

        ttk.Label(dev_row, text="输入设备",
                  background=BG_CARD, foreground=TEXT_PRIMARY).pack(side=tk.LEFT)
        self.cb_device = ttk.Combobox(dev_row, width=52, state="readonly",
                                      font=("Microsoft YaHei", 9))
        self.cb_device.pack(side=tk.LEFT, padx=(6, 4))
        self.cb_device.bind("<<ComboboxSelected>>", lambda e: self._on_device_pick())

        self.btn_refresh = ttk.Button(dev_row, text="🔄 刷新",
                                      command=self._refresh_devices)
        self.btn_refresh.pack(side=tk.LEFT, padx=4)

        ttk.Label(dev_row, text="识别语言",
                  background=BG_CARD, foreground=TEXT_PRIMARY).pack(
            side=tk.LEFT, padx=(20, 4))
        self.lang_var = tk.StringVar(value="zh")
        self.cb_lang = ttk.Combobox(dev_row, width=10, textvariable=self.lang_var,
                                    values=["zh(中文)", "en(英文)", "auto(自动)"],
                                    state="readonly", font=("Microsoft YaHei", 9))
        self.cb_lang.pack(side=tk.LEFT)

        # 状态指示
        status_row = tk.Frame(card_dev, bg=BG_CARD)
        status_row.pack(fill=tk.X, pady=(10, 0))

        self.status_dot = tk.Canvas(status_row, width=12, height=12,
                                    bg=BG_CARD, highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT)
        self._dot = self.status_dot.create_oval(1, 1, 11, 11,
                                                 fill=TEXT_MUTED, outline="")

        self.status_var = tk.StringVar(value="就绪 — 选择设备后点击「开始录制」")
        self.lbl_status = tk.Label(status_row, textvariable=self.status_var,
                                   bg=BG_CARD, fg=TEXT_SECONDARY,
                                   font=("Microsoft YaHei", 9))
        self.lbl_status.pack(side=tk.LEFT, padx=(6, 0))

        # ═══ 控制按钮（圆角 + 粒子效果）═══
        ctrl_frame = tk.Frame(main_frame, bg=BG_MAIN)
        ctrl_frame.pack(fill=tk.X, pady=(0, 8))

        btn_frame = tk.Frame(ctrl_frame, bg=BG_MAIN)
        btn_frame.pack(side=tk.LEFT)

        self.btn_start = RoundedButton(
            btn_frame, text="▶  开始录制", command=self._start,
            bg_color=BTN_PRIMARY, hover_color=BTN_PRIMARY_HOVER,
            fg_color="#ffffff",
            font=("Microsoft YaHei", 10, "bold"),
            width=134, height=38, radius=10, particle=True,
        )
        self.btn_start.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_pause = RoundedButton(
            btn_frame, text="⏸  暂停", command=self._pause,
            bg_color=BTN_WARN, hover_color=BTN_WARN_HOVER,
            fg_color="#ffffff",
            font=("Microsoft YaHei", 10),
            width=100, height=38, radius=10, particle=True,
            state="disabled",
        )
        self.btn_pause.pack(side=tk.LEFT, padx=4)

        self.btn_stop = RoundedButton(
            btn_frame, text="⏹  停止", command=self._stop,
            bg_color=BTN_DANGER, hover_color=BTN_DANGER_HOVER,
            fg_color="#ffffff",
            font=("Microsoft YaHei", 10),
            width=100, height=38, radius=10, particle=True,
            state="disabled",
        )
        self.btn_stop.pack(side=tk.LEFT, padx=4)

        self.btn_history = RoundedButton(
            btn_frame, text="📂 历史记录", command=self._open_history,
            bg_color=BTN_DARK, hover_color=BTN_DARK_HOVER,
            fg_color=TEXT_PRIMARY,
            font=("Microsoft YaHei", 10),
            width=120, height=38, radius=10, particle=False,
        )
        self.btn_history.pack(side=tk.LEFT, padx=4)

        # 计时器（Canvas 圆角面板 + 数码管风格）
        timer_frame = tk.Frame(ctrl_frame, bg=BG_MAIN)
        timer_frame.pack(side=tk.RIGHT)

        timer_w, timer_h = 130, 42
        timer_r = 10
        timer_margin = 8
        timer_cw = timer_w + timer_margin * 2
        timer_ch = timer_h + timer_margin * 2

        self.timer_canvas = tk.Canvas(timer_frame, width=timer_cw, height=timer_ch,
                                      bg=BG_MAIN, highlightthickness=0)
        self.timer_canvas.pack(side=tk.RIGHT)
        self._timer_bg = BTN_DARK  # 初始背景
        self._timer_fg = ACCENT    # 初始文字色
        self._timer_tx1 = timer_margin
        self._timer_ty1 = timer_margin
        self._timer_tx2 = timer_margin + timer_w
        self._timer_ty2 = timer_margin + timer_h
        self._timer_r = timer_r
        self._timer_text_id = None
        self.time_var = tk.StringVar(value="00:00")
        self._draw_timer()
        # 定时刷新（监听背景/颜色变化）
        self._timer_sync_job = None
        self._sync_timer()

        # ═══ 转写内容卡片 ═══
        card_text = ttk.LabelFrame(main_frame, text=" 实时转写 ",
                                   style="Card.TLabelframe", padding=(16, 12))
        card_text.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # 顶部信息栏
        info_row = tk.Frame(card_text, bg=BG_CARD)
        info_row.pack(fill=tk.X, pady=(0, 8))

        self.seg_count_var = tk.StringVar(value="已识别 0 段")
        tk.Label(info_row, textvariable=self.seg_count_var,
                 bg=BG_CARD, fg=TEXT_SECONDARY,
                 font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)

        # 转写文本区
        txt_frame = tk.Frame(card_text, bg=BG_TEXT,
                             highlightbackground=BORDER,
                             highlightthickness=1)
        txt_frame.pack(fill=tk.BOTH, expand=True)

        self.txt = tk.Text(txt_frame, wrap=tk.WORD,
                           font=("Microsoft YaHei", 11),
                           bg=BG_TEXT, fg=TEXT_PRIMARY, relief="flat",
                           borderwidth=0, padx=14, pady=12,
                           selectbackground="#1e3a5f",
                           selectforeground=TEXT_PRIMARY,
                           insertbackground=TEXT_SECONDARY)
        self.txt.pack(fill=tk.BOTH, expand=True)
        self.txt.config(state=tk.DISABLED)

        # 滚动条
        txt_scroll = ttk.Scrollbar(txt_frame, command=self.txt.yview)
        txt_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt.configure(yscrollcommand=txt_scroll.set)

        # 标签样式
        self.txt.tag_config("ts", foreground=TEXT_MUTED,
                            font=("Consolas", 9))
        self.txt.tag_config("txt", foreground=TEXT_PRIMARY,
                            font=("Microsoft YaHei", 11),
                            spacing1=4, spacing3=4)
        self.txt.tag_config("info", foreground=TEXT_SECONDARY,
                            font=("Microsoft YaHei", 9))
        self.txt.tag_config("system", foreground=TEXT_MUTED,
                            font=("Microsoft YaHei", 9, "italic"))

        # ═══ 底部状态栏 ═══
        footer = tk.Frame(main_frame, bg=BG_FOOTER, height=32)
        footer.pack(fill=tk.X, pady=(0, 0))
        footer.pack_propagate(False)

        self.path_var = tk.StringVar(value="📁 尚未录制")
        tk.Label(footer, textvariable=self.path_var,
                 bg=BG_FOOTER, fg=TEXT_MUTED,
                 font=("Microsoft YaHei", 8)).pack(
            side=tk.LEFT, padx=(12, 0), pady=6)

        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=120)
        # 初始隐藏

    def _log(self, msg, tag="info"):
        self.txt.config(state=tk.NORMAL)
        self.txt.insert(tk.END, msg + "\n", tag)
        self.txt.see(tk.END)
        self.txt.config(state=tk.DISABLED)

    def _set_status(self, text, color=TEXT_SECONDARY, dot_color=TEXT_MUTED):
        self.status_var.set(text)
        self.lbl_status.config(fg=color)
        self.status_dot.itemconfig(self._dot, fill=dot_color)

    # ==================== 设备 ====================
    def _refresh_devices(self):
        try:
            self.devices = list_input_devices()
        except Exception as e:
            messagebox.showwarning("设备扫描失败", str(e))
            self.devices = []

        if not self.devices:
            self.cb_device["values"] = ["(未检测到可用设备)"]
            self.cb_device.current(0)
            self.selected = None
            self._set_status("未检测到音频输入设备", RED, RED)
            return

        self.cb_device["values"] = [d["label"] for d in self.devices]
        best = pick_best_device(self.devices)
        if best:
            self.cb_device.current(self.devices.index(best))
            self.selected = best

            if best.get("is_loopback"):
                self._set_status(f"已选择系统音频设备 — 可捕获腾讯会议声音", GREEN, GREEN)
            elif best.get("is_mic"):
                self._set_status(f"已选择麦克风 — ⚠️ 只能录说话声，不录系统音频", AMBER, AMBER)
            else:
                self._set_status(f"已选择: {best['name']}")

            # 检查是否有环回设备
            has_loopback = any(d.get("is_loopback") for d in self.devices)
            if not has_loopback:
                self._log(
                    "💡 未检测到系统音频环回设备。如需捕获腾讯会议的声音，请在 Windows 声音设置中\n"
                    "   启用「立体声混音」(Stereo Mix) 后点击刷新。",
                    "system"
                )

    def _on_device_pick(self):
        idx = self.cb_device.current()
        if 0 <= idx < len(self.devices):
            self.selected = self.devices[idx]
            if self.selected.get("is_loopback"):
                self._set_status(f"已选择系统音频: {self.selected['name']}", GREEN, GREEN)
            elif self.selected.get("is_mic"):
                self._set_status(f"已选择麦克风: {self.selected['name']}", AMBER, AMBER)
            else:
                self._set_status(f"已选择: {self.selected['name']}")

    # ==================== 录制 ====================
    def _start(self):
        if self.recording:
            return
        if not self.selected:
            messagebox.showwarning("提示", "请先选择音频输入设备")
            return

        # 创建输出目录
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.session_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "transcripts", ts
        )
        os.makedirs(self.session_dir, exist_ok=True)
        self.output_path = os.path.join(self.session_dir, "transcript.txt")

        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(f"会议转录记录\n日期: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
                    f"设备: {self.selected['name']}\n语言: {self.lang_var.get()}\n"
                    f"{'='*50}\n\n")

        self.path_var.set(f"📁 {self.session_dir}")

        # 重置
        self.recording = True
        self.paused = False
        self.segment_count = 0
        self._stop_flag.clear()
        self.full_text = ""
        self.segments.clear()
        self.speech_buf.clear()
        self.vad.reset()

        self.txt.config(state=tk.NORMAL)
        self.txt.delete(1.0, tk.END)
        self.txt.config(state=tk.DISABLED)
        self.seg_count_var.set("已识别 0 段")

        self.btn_start.config(state="disabled")
        self.btn_pause.config(state="normal", text="⏸  暂停",
                              bg=BTN_WARN)
        self.btn_stop.config(state="normal")
        self.cb_device.config(state="disabled")
        self.cb_lang.config(state="disabled")
        self.btn_refresh.config(state="disabled")

        self._set_status("正在加载语音识别模型…", BTN_PRIMARY, BTN_PRIMARY)
        self._log("⏳ 正在加载语音识别模型，请稍候…", "system")

        self.progress.pack(side=tk.RIGHT, padx=12, pady=6)
        self.progress.start()
        # 强制刷新 UI，确保按钮状态变化立即显示
        self.root.update_idletasks()
        threading.Thread(target=self._load_then_run, daemon=True).start()

    def _load_then_run(self):
        try:
            self.transcriber.load()
        except Exception as e:
            self.root.after(0, self._on_load_error, str(e))
            return
        self.root.after(0, self._on_loaded)

    def _on_loaded(self):
        self.progress.stop()
        self.progress.pack_forget()

        self._set_status(f"● 录制中 — {self.selected['name']}", RED, RED)
        self._set_timer_style(BTN_DANGER, "white")

        # 使用设备实际支持的采样率（WASAPI 环回通常只支持 44100/48000）
        dev_sr = int(self.selected.get("sample_rate", 0))
        if dev_sr <= 0:
            dev_sr = SAMPLE_RATE
        self.audio_sr = dev_sr

        # 配置 VAD（使用设备采样率）
        block = int(self.audio_sr * 0.1)  # 100ms per block
        self.vad.configure(self.audio_sr, block)

        # 打开音频流（先验证设备是否仍然有效）
        last_err = None
        target_name = self.selected.get("name", "")
        devices_to_try = [self.selected["index"]]  # 首选当前设备

        for attempt in range(3):
            for dev_id in devices_to_try:
                try:
                    self.stream = sd.InputStream(
                        device=dev_id,
                        channels=1,
                        samplerate=self.audio_sr,
                        dtype=np.float32,
                        blocksize=block,
                        callback=self._audio_cb,
                    )
                    self.stream.start()
                    # 成功了，更新 selected（如果换了设备）
                    if dev_id != self.selected["index"]:
                        for d in self.devices:
                            if d["index"] == dev_id:
                                self.selected = d
                                break
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    err_msg = str(e).lower()
                    if "sample rate" in err_msg or "invalid sample" in err_msg:
                        # 尝试不同采样率
                        for sr in [48000, 44100]:
                            if sr == self.audio_sr:
                                continue
                            try:
                                self.audio_sr = sr
                                block2 = int(sr * 0.1)
                                self.vad.configure(sr, block2)
                                self.stream = sd.InputStream(
                                    device=dev_id, channels=1,
                                    samplerate=sr, dtype=np.float32,
                                    blocksize=block2,
                                    callback=self._audio_cb,
                                )
                                self.stream.start()
                                self.audio_sr = sr
                                block = block2
                                last_err = None
                                break
                            except Exception:
                                continue
                    if last_err is None:
                        break
            if last_err is None:
                break
            # 第一轮失败 → 重新扫描，按名称匹配所有设备
            if attempt == 0:
                self._log("⚠️ 重新扫描音频设备…", "system")
                try:
                    self.devices = list_input_devices()
                except Exception:
                    pass
                devices_to_try = []
                # 先按名称匹配原设备
                for d in self.devices:
                    if d["name"] == target_name:
                        devices_to_try.append(d["index"])
                # 再把所有设备都加上
                for d in self.devices:
                    if d["index"] not in devices_to_try:
                        devices_to_try.append(d["index"])
                if devices_to_try:
                    self.selected = self.devices[0]
                    self.audio_sr = int(self.selected.get("sample_rate", SAMPLE_RATE))
                    block = int(self.audio_sr * 0.1)
                    self.vad.configure(self.audio_sr, block)
                    continue
            break

        if last_err is not None:
            self.btn_start.config(state="normal", bg=BTN_PRIMARY)
            self.btn_pause.config(state="disabled")
            self.btn_stop.config(state="disabled")
            self.cb_device.config(state="readonly")
            self.cb_lang.config(state="readonly")
            self.btn_refresh.config(state="normal")
            self.recording = False
            self._set_timer_style(BG_TIMER, ACCENT)
            messagebox.showerror("音频错误", f"无法打开音频设备:\n{last_err}")
            self._set_status("音频设备打开失败", RED, RED)
            return

        # 处理线程
        self._proc_thread = threading.Thread(target=self._process_loop, daemon=True)
        self._proc_thread.start()

        self._start_time = time.time()
        self._tick()

        dev_type = "系统音频(环回)" if self.selected.get("is_loopback") else "麦克风"
        self._log(f"✅ 模型就绪 — {dev_type} | 采样率: {self.audio_sr}Hz", "system")
        self._log("")

    def _on_load_error(self, msg):
        self.progress.stop()
        self.progress.pack_forget()
        self.recording = False
        self.btn_start.config(state="normal", bg=BTN_PRIMARY)
        self.cb_device.config(state="readonly")
        self.btn_refresh.config(state="normal")
        self._set_status("模型加载失败", RED, RED)
        messagebox.showerror("加载失败",
                             f"模型加载失败:\n{msg}\n\n请检查网络（首次需下载模型）。")

    def _pause(self):
        if not self.recording:
            return
        self.paused = not self.paused
        if self.paused:
            self.btn_pause.config(text="▶  继续", bg=GREEN)
            self._set_status("⏸ 已暂停", AMBER, AMBER)
            self._set_timer_style(AMBER, "white")
            self._log("⏸ 暂停", "system")
        else:
            self.btn_pause.config(text="⏸  暂停", bg=BTN_WARN)
            self._set_status(f"● 录制中 — {self.selected['name']}", RED, RED)
            self._set_timer_style(BTN_DANGER, "white")
            self._log("▶ 继续", "system")

    def _stop(self):
        if not self.recording:
            return
        self.recording = False
        self._stop_flag.set()

        # 关闭流
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        # 等处理线程
        if self._proc_thread and self._proc_thread.is_alive():
            self._proc_thread.join(timeout=10)

        # 处理残余
        if self.speech_buf:
            self._flush_buffer()

        # 等一下最后的转录完成
        self._finalize_pending = True

        self.btn_start.config(state="normal", bg=BTN_PRIMARY)
        self.btn_pause.config(state="disabled", text="⏸  暂停",
                              bg=BTN_WARN)
        self.btn_stop.config(state="disabled")
        self.cb_device.config(state="readonly")
        self.cb_lang.config(state="readonly")
        self.btn_refresh.config(state="normal")

        self._set_status(f"已停止 — 共识别 {self.segment_count} 段")
        self._set_timer_style(BG_TIMER, ACCENT)
        self.time_var.set("00:00")
        self.seg_count_var.set(f"共识别 {self.segment_count} 段")
        self._log(f"\n✅ 录制完成 — 共 {self.segment_count} 段文字", "system")
        self._log(f"📁 文件保存在: {self.session_dir}", "system")
        self.path_var.set(f"📁 {self.session_dir}")

    # ==================== 音频 ====================
    def _audio_cb(self, indata, _frames, _ti, status):
        if status:
            print(f"[音频] {status}", file=sys.stderr)
        if self.paused:
            return
        try:
            self.audio_q.put(indata[:, 0].copy())
        except queue.Full:
            pass  # 丢弃旧数据，防止积压

    def _process_loop(self):
        while not self._stop_flag.is_set() or not self.audio_q.empty():
            try:
                chunk = self.audio_q.get(timeout=0.4)
            except queue.Empty:
                continue

            speaking = self.vad.process(chunk)

            if speaking:
                self.speech_buf.append(chunk)
            else:
                # 停顿 → 自然断句，即刻识别
                if self.speech_buf and not self.vad.is_speaking:
                    self._flush_buffer(reason="pause")

            # 连续说话超过 2 分钟 → 强制分段（保留重叠，下半句归下一段）
            dur = sum(len(c) for c in self.speech_buf) / self.audio_sr
            if dur >= CHUNK_DURATION:
                self._flush_buffer(reason="chunk")

        if self.speech_buf:
            self._flush_buffer(reason="stop")

    def _flush_buffer(self, reason="pause"):
        if not self.speech_buf:
            return
        audio = np.concatenate([c for c in self.speech_buf])
        self.speech_buf.clear()
        dur = len(audio) / self.audio_sr

        if dur < MIN_SEGMENT_DURATION:
            return

        # 强制分段时保留 OVERLAP_DURATION 秒重叠到下一段（避免切断词语）
        if reason == "chunk":
            overlap_samples = int(self.audio_sr * OVERLAP_DURATION)
            if len(audio) > overlap_samples:
                overlap = audio[-overlap_samples:].copy()
                self.speech_buf.append(overlap)

        # 重采样到 16kHz（Whisper 模型要求）
        audio_16k = resample_audio(audio, self.audio_sr, SAMPLE_RATE)

        lang_raw = self.lang_var.get()
        lang = "zh" if "zh" in lang_raw else ("en" if "en" in lang_raw else "auto")

        # 控制并发数
        if self.transcribe_q is None:
            return  # 太忙则跳过

        self.transcribe_q.put((audio_16k.copy(), lang, time.time(), reason))

    def _transcribe_loop(self):
        while True:
            audio, lang, cap_time, reason = self.transcribe_q.get()
            try:
                self._do_transcribe(audio, lang, cap_time, reason)
            finally:
                self.transcribe_q.task_done()

    def _do_transcribe(self, audio, lang, cap_time, reason="pause"):
        try:
            text, err = self.transcriber.transcribe(audio, language=lang)
            if err:
                self.result_q.put(("err", err, cap_time))
            elif text:
                self.result_q.put(("text", text, cap_time, reason))
        except Exception as e:
            self.result_q.put(("err", str(e), cap_time))
    # ==================== 结果输出 ====================
    def _poll_results(self):
        try:
            while True:
                item = self.result_q.get_nowait()
                typ, content, cap_time = item[0], item[1], item[2]

                if typ == "text" and content:
                    ts = datetime.fromtimestamp(cap_time).strftime("%H:%M:%S")
                    self.full_text += content + "\n"
                    self.segments.append({"time": ts, "text": content})
                    self.segment_count += 1
                    self._write_line(ts, content)

                    # 标记：自然断句 vs 强制分段
                    reason = item[3] if len(item) > 3 else "pause"
                    if reason == "chunk":
                        self._log(f"[{ts}] {content}  ↵", "txt")  # ↵ 表示未完继续
                    else:
                        self._log(f"[{ts}] {content}", "txt")

                    self.seg_count_var.set(f"已识别 {self.segment_count} 段")
                elif typ == "err":
                    self._log(f"⚠️ 识别出错: {content}", "system")
        except queue.Empty:
            pass
        if (self._finalize_pending and self.transcribe_q.unfinished_tasks == 0
                and self.result_q.empty()
                and (not self._proc_thread or not self._proc_thread.is_alive())):
            self._save_final()
            self._finalize_pending = False
        self.root.after(200, self._poll_results)

    def _write_line(self, ts, text):
        if self.output_path:
            try:
                with open(self.output_path, "a", encoding="utf-8") as f:
                    f.write(f"[{ts}] {text}\n")
            except Exception:
                pass

    def _save_final(self):
        if not self.session_dir:
            return
        # 纯文本版
        try:
            with open(os.path.join(self.session_dir, "full_text.txt"), "w", encoding="utf-8") as f:
                f.write(self.full_text)
        except Exception:
            pass
        # JSON 结构化版
        try:
            with open(os.path.join(self.session_dir, "segments.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "time": datetime.now().isoformat(),
                    "device": self.selected["name"] if self.selected else "",
                    "segments": self.segments,
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ==================== 计时 ====================
    def _tick(self):
        if self.recording and not self.paused:
            e = time.time() - self._start_time
            self.time_var.set(f"{int(e//60):02d}:{int(e%60):02d}")
            self._draw_timer()
        if self.recording:
            self.root.after(1000, self._tick)

    def _draw_timer(self):
        """重绘计时器 Canvas"""
        c = self.timer_canvas
        c.delete("timer_all")
        x1, y1, x2, y2 = self._timer_tx1, self._timer_ty1, self._timer_tx2, self._timer_ty2
        r = self._timer_r
        d = 2 * r
        fill = self._timer_bg
        # 圆角矩形
        kw = {"fill": fill, "outline": fill, "tags": "timer_all"}
        c.create_rectangle(x1 + r, y1, x2 - r, y2, **kw)
        c.create_rectangle(x1, y1 + r, x2, y2 - r, **kw)
        for cx, cy in [(x1, y1), (x2 - d, y1), (x1, y2 - d), (x2 - d, y2 - d)]:
            c.create_oval(cx, cy, cx + d, cy + d, **kw)
        # 外边框（微亮）
        border_kw = {"outline": BORDER_LIGHT, "tags": "timer_all"}
        c.create_rectangle(x1 + r, y1, x2 - r, y2, **border_kw)
        c.create_rectangle(x1, y1 + r, x2, y2 - r, **border_kw)
        for cx, cy in [(x1, y1), (x2 - d, y1), (x1, y2 - d), (x2 - d, y2 - d)]:
            c.create_oval(cx, cy, cx + d, cy + d, **border_kw)
        # 时间文字
        text = self.time_var.get()
        c.create_text((x1 + x2) // 2, (y1 + y2) // 2,
                      text=text, fill=self._timer_fg,
                      font=("Consolas", 20, "bold"), tags="timer_all")

    def _set_timer_style(self, bg, fg):
        """设置计时器背景与文字色并重绘"""
        self._timer_bg = bg
        self._timer_fg = fg
        self._draw_timer()

    def _sync_timer(self):
        """定时同步 StringVar → Canvas（兜底）"""
        if self._timer_text_id is not None:
            self._draw_timer()
        self._timer_sync_job = self.root.after(800, self._sync_timer)

    # ==================== 退出 ====================
    def _open_history(self):
        """打开历史记录窗口"""
        transcripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transcripts")
        HistoryWindow(self.root, transcripts_dir)

    def _on_close(self):
        if self.recording:
            ok = messagebox.askyesno("确认", "正在录制中，确定停止并退出吗？")
            if ok:
                self._stop()
                self.root.destroy()
        else:
            self.root.destroy()


# ============================================================
# 历史记录窗口
# ============================================================
class HistoryWindow:
    def __init__(self, parent, transcripts_dir):
        self.transcripts_dir = transcripts_dir
        self._card_widgets: list = []  # 记录卡片 + 子控件，方便悬停统一变色

        self.win = tk.Toplevel(parent)
        self.win.title("📂 历史记录")
        self.win.geometry("720x560")
        self.win.minsize(500, 360)
        self.win.configure(bg=BG_MAIN)
        self.win.transient(parent)
        self.win.grab_set()

        self._build()
        self._load()

    def _build(self):
        # ── 顶部 ──
        header = tk.Frame(self.win, bg=BG_MAIN)
        header.pack(fill=tk.X, padx=16, pady=(14, 8))

        tk.Label(header, text="历史记录", bg=BG_MAIN, fg=TEXT_PRIMARY,
                 font=("Microsoft YaHei", 14, "bold")).pack(side=tk.LEFT)

        self.count_var = tk.StringVar(value="")
        tk.Label(header, textvariable=self.count_var, bg=BG_MAIN, fg=TEXT_SECONDARY,
                 font=("Microsoft YaHei", 9)).pack(side=tk.RIGHT)

        tk.Button(header, text="🗑 清空全部", command=self._clear_all,
                  bg=BTN_DANGER, fg="white",
                  activebackground=BTN_DANGER_ACTIVE, activeforeground="white",
                  font=("Microsoft YaHei", 9),
                  relief="flat", padx=12, pady=3, cursor="hand2",
                  borderwidth=0).pack(side=tk.RIGHT, padx=(0, 8))

        tk.Button(header, text="📁 打开目录", command=self._open_dir,
                  bg=BTN_DARK, fg=TEXT_PRIMARY,
                  activebackground=BTN_DARK_HOVER, activeforeground=TEXT_PRIMARY,
                  font=("Microsoft YaHei", 9),
                  relief="flat", padx=12, pady=3, cursor="hand2",
                  borderwidth=0).pack(side=tk.RIGHT, padx=(0, 6))

        # 分隔线
        tk.Frame(self.win, bg=BORDER, height=1).pack(fill=tk.X, padx=16)

        # ── 可滚动卡片列表（Canvas + Frame）──
        canvas_frame = tk.Frame(self.win, bg=BG_MAIN)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=(8, 12))

        self.canvas = tk.Canvas(canvas_frame, bg=BG_MAIN, highlightthickness=0)
        self.vsb = tk.Scrollbar(canvas_frame, orient="vertical",
                                command=self.canvas.yview)
        self.scroll_frame = tk.Frame(self.canvas, bg=BG_MAIN)

        self._inner_id = self.canvas.create_window((0, 0), window=self.scroll_frame,
                                                    anchor="nw")
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 鼠标滚轮
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.canvas.bind("<Enter>",
                         lambda e: self.canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self.canvas.bind("<Leave>",
                         lambda e: self.canvas.unbind_all("<MouseWheel>"))

        # 空状态标签（在 scroll_frame 里）
        self.empty_lbl = tk.Label(self.scroll_frame, text="暂无历史记录",
                                  bg=BG_MAIN, fg=TEXT_MUTED,
                                  font=("Microsoft YaHei", 12))
        self.empty_lbl.pack(pady=60)

    def _sync_canvas_width(self):
        """同步内框宽度 = canvas 可视宽度（延迟调用，确保窗口已完成布局）"""
        w = self.canvas.winfo_width()
        if w > 10:
            self.canvas.itemconfig(self._inner_id, width=w)
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    # ==================== 数据加载 ====================
    def _load(self):
        self._card_widgets.clear()
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        if not os.path.isdir(self.transcripts_dir):
            self.empty_lbl = tk.Label(self.scroll_frame, text="暂无历史记录",
                                      bg=BG_MAIN, fg=TEXT_MUTED,
                                      font=("Microsoft YaHei", 12))
            self.empty_lbl.pack(pady=60)
            self.count_var.set("共 0 条")
            self._sync_canvas_width()
            return

        sessions = []
        for name in os.listdir(self.transcripts_dir):
            path = os.path.join(self.transcripts_dir, name)
            if not os.path.isdir(path):
                continue
            seg_count = 0
            preview = ""
            device = ""
            segments_file = os.path.join(path, "segments.json")
            try:
                if os.path.exists(segments_file):
                    with open(segments_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    segs = data.get("segments", [])
                    seg_count = len(segs)
                    device = data.get("device", "")
                    if segs:
                        preview = segs[0].get("text", "")[:80]
            except Exception:
                pass

            if not preview:
                txt_file = os.path.join(path, "transcript.txt")
                try:
                    if os.path.exists(txt_file):
                        with open(txt_file, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if line and not line.startswith("=") and not line.startswith("会议"):
                                    if "] " in line:
                                        preview = line.split("] ", 1)[1][:80]
                                        break
                except Exception:
                    pass

            sessions.append({
                "name": name,
                "path": path,
                "seg_count": seg_count,
                "preview": preview,
                "device": device,
            })

        sessions.sort(key=lambda s: s["name"], reverse=True)
        self.count_var.set(f"共 {len(sessions)} 条")

        if not sessions:
            self.empty_lbl = tk.Label(self.scroll_frame, text="暂无历史记录",
                                      bg=BG_MAIN, fg=TEXT_MUTED,
                                      font=("Microsoft YaHei", 12))
            self.empty_lbl.pack(pady=60)
            self._sync_canvas_width()
            return

        for s in sessions:
            self._add_card(s)

        # 延迟同步 canvas 宽度（等窗口完成布局后再设）
        self.win.after(50, self._sync_canvas_width)

    # ==================== 卡片 ====================
    def _add_card(self, session):
        CARD_BG = BG_CARD
        CARD_HOVER = "#1a2332"

        card = tk.Frame(self.scroll_frame, bg=CARD_BG,
                        highlightbackground=BORDER, highlightthickness=1,
                        cursor="hand2")
        card.pack(fill=tk.X, pady=(0, 6))

        # ── 左侧内容 ──
        left = tk.Frame(card, bg=CARD_BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(14, 4), pady=10)

        try:
            dt = datetime.strptime(session["name"], "%Y-%m-%d_%H-%M-%S")
            time_str = dt.strftime("%Y-%m-%d  %H:%M:%S")
        except ValueError:
            time_str = session["name"]

        lbl_time = tk.Label(left, text=f"📅 {time_str}", bg=CARD_BG,
                            fg=TEXT_PRIMARY,
                            font=("Microsoft YaHei", 11, "bold"), anchor="w")
        lbl_time.pack(fill=tk.X)

        info = f"{session['seg_count']} 段文字"
        if session.get("device"):
            info += f"  |  {session['device'][:40]}"
        lbl_info = tk.Label(left, text=info, bg=CARD_BG, fg=TEXT_SECONDARY,
                            font=("Microsoft YaHei", 8), anchor="w")
        lbl_info.pack(fill=tk.X, pady=(2, 0))

        lbl_preview = None
        if session["preview"]:
            preview = session["preview"][:60]
            if len(session["preview"]) > 60:
                preview += "…"
            lbl_preview = tk.Label(left, text=preview, bg=CARD_BG,
                                   fg=TEXT_MUTED,
                                   font=("Microsoft YaHei", 9),
                                   anchor="w", justify="left")
            lbl_preview.pack(fill=tk.X, pady=(4, 0))

        # ── 右侧按钮 ──
        right = tk.Frame(card, bg=CARD_BG)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=10)

        # 删除按钮
        def _do_delete(s=session):
            if messagebox.askyesno(
                "确认删除",
                f"确定要删除以下记录吗？\n\n"
                f"{s['name']}\n{s['seg_count']} 段文字\n\n"
                f"此操作不可撤销。"
            ):
                try:
                    import shutil
                    shutil.rmtree(s["path"])
                except Exception as e:
                    messagebox.showerror("删除失败", str(e))
                    return
                self._load()

        btn_delete = tk.Button(right, text="🗑 删除", command=_do_delete,
                               bg="#2d1f1f", fg=BTN_DANGER,
                               activebackground="#3d2020",
                               activeforeground=BTN_DANGER_HOVER,
                               font=("Microsoft YaHei", 9, "bold"),
                               relief="flat", padx=12, pady=6,
                               cursor="hand2", borderwidth=0)
        btn_delete.pack(side=tk.TOP)

        # 目录按钮
        btn_dir = tk.Button(right, text="📁 目录",
                            command=lambda p=session["path"]: os.startfile(p),
                            bg=BTN_DARK, fg=TEXT_PRIMARY,
                            activebackground=BTN_DARK_HOVER,
                            activeforeground=TEXT_PRIMARY,
                            font=("Microsoft YaHei", 9),
                            relief="flat", padx=12, pady=6,
                            cursor="hand2", borderwidth=0)
        btn_dir.pack(side=tk.TOP, pady=(0, 4))

        # ── 收集所有需要变色的子控件 ──
        hover_widgets = [card, left, lbl_time, lbl_info]
        if lbl_preview:
            hover_widgets.append(lbl_preview)

        # 所有子控件（含 right 区）：Enter/Leave 都要参与
        all_child_widgets = [card, left, right, lbl_time, lbl_info,
                             btn_delete, btn_dir]
        if lbl_preview:
            all_child_widgets.append(lbl_preview)

        # ── 悬停效果（带延迟检测）──
        _leave_timer = [None]

        def _apply_hover(on):
            for w in hover_widgets:
                try:
                    w.configure(bg=CARD_HOVER if on else CARD_BG)
                except Exception:
                    pass

        def _on_enter(e, timer=_leave_timer):
            if timer[0] is not None:
                card.after_cancel(timer[0])
                timer[0] = None
            _apply_hover(True)

        def _on_leave(e, timer=_leave_timer, c=card):
            def _check():
                timer[0] = None
                x, y = c.winfo_pointerxy()
                rx, ry = c.winfo_rootx(), c.winfo_rooty()
                rw, rh = c.winfo_width(), c.winfo_height()
                if not (rx <= x <= rx + rw and ry <= y <= ry + rh):
                    _apply_hover(False)
            timer[0] = c.after(80, _check)

        for w in all_child_widgets:
            w.bind("<Enter>", _on_enter)
            w.bind("<Leave>", _on_leave)

        # ── 双击查看 ──
        for w in hover_widgets:
            w.bind("<Double-Button-1>", lambda e, s=session: self._view_session(s))

        self._card_widgets.append((hover_widgets, all_child_widgets))

    # ==================== 操作 ====================
    def _view_session(self, session):
        """双击卡片 → 在新窗口中查看完整转录内容"""
        content = ""
        txt_file = os.path.join(session["path"], "transcript.txt")
        try:
            if os.path.exists(txt_file):
                with open(txt_file, "r", encoding="utf-8") as f:
                    content = f.read()
        except Exception:
            content = "(无法读取文件)"
        if not content.strip():
            content = "(暂无转录内容)"

        try:
            dt = datetime.strptime(session["name"], "%Y-%m-%d_%H-%M-%S")
            time_str = dt.strftime("%Y-%m-%d  %H:%M:%S")
        except ValueError:
            time_str = session["name"]

        viewer = tk.Toplevel(self.win)
        viewer.title(f"📄 {time_str}")
        viewer.geometry("720x600")
        viewer.minsize(480, 360)
        viewer.configure(bg=BG_MAIN)
        viewer.transient(self.win)

        header = tk.Frame(viewer, bg=BG_CARD,
                          highlightbackground=BORDER, highlightthickness=1)
        header.pack(fill=tk.X, padx=12, pady=(12, 6))

        info_text = f"📅 {time_str}    |    {session['seg_count']} 段文字"
        if session.get("device"):
            info_text += f"    |    🎙 {session['device'][:50]}"
        tk.Label(header, text=info_text, bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Microsoft YaHei", 10, "bold")).pack(
            side=tk.LEFT, padx=14, pady=10)

        btn_frame = tk.Frame(header, bg=BG_CARD)
        btn_frame.pack(side=tk.RIGHT, padx=10, pady=8)

        tk.Button(btn_frame, text="📁 打开目录",
                  command=lambda p=session["path"]: os.startfile(p),
                  bg=BTN_DARK, fg=TEXT_PRIMARY,
                  activebackground=BTN_DARK_HOVER, activeforeground=TEXT_PRIMARY,
                  font=("Microsoft YaHei", 9),
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  borderwidth=0).pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(btn_frame, text="🗑 删除此记录",
                  command=lambda s=session: (viewer.destroy(),
                                             self._delete_session(s)),
                  bg="#2d1f1f", fg=BTN_DANGER,
                  activebackground="#3d2020", activeforeground=BTN_DANGER_HOVER,
                  font=("Microsoft YaHei", 9),
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  borderwidth=0).pack(side=tk.LEFT)

        txt_frame = tk.Frame(viewer, bg=BG_TEXT,
                             highlightbackground=BORDER, highlightthickness=1)
        txt_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        txt = tk.Text(txt_frame, wrap=tk.WORD,
                      font=("Microsoft YaHei", 11),
                      bg=BG_TEXT, fg=TEXT_PRIMARY, relief="flat",
                      borderwidth=0, padx=16, pady=14,
                      selectbackground="#1e3a5f",
                      selectforeground=TEXT_PRIMARY,
                      insertbackground=TEXT_SECONDARY)
        txt.pack(fill=tk.BOTH, expand=True)

        vsb = ttk.Scrollbar(txt_frame, command=txt.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        txt.configure(yscrollcommand=vsb.set)

        txt.insert(tk.END, content)
        txt.config(state=tk.DISABLED)

        def _select_all(e):
            txt.config(state=tk.NORMAL)
            txt.tag_add(tk.SEL, "1.0", tk.END)
            txt.mark_set(tk.INSERT, "1.0")
            txt.see(tk.INSERT)
            return "break"
        txt.bind("<Control-a>", _select_all)
        txt.bind("<Control-A>", _select_all)

    def _delete_session(self, session):
        if not messagebox.askyesno("确认删除",
                                   f"确定要删除以下记录吗？\n\n{session['name']}\n"
                                   f"{session['seg_count']} 段文字\n\n此操作不可撤销。"):
            return
        try:
            import shutil
            shutil.rmtree(session["path"])
        except Exception as e:
            messagebox.showerror("删除失败", str(e))
            return
        self._load()

    def _clear_all(self):
        if not messagebox.askyesno("确认清空", "确定要删除所有历史记录吗？\n此操作不可撤销。"):
            return
        try:
            import shutil
            for name in os.listdir(self.transcripts_dir):
                path = os.path.join(self.transcripts_dir, name)
                if os.path.isdir(path):
                    shutil.rmtree(path)
        except Exception as e:
            messagebox.showerror("清空失败", str(e))
            return
        self._load()

    def _open_dir(self):
        if os.path.isdir(self.transcripts_dir):
            os.startfile(self.transcripts_dir)
        else:
            messagebox.showinfo("提示", "暂无历史记录目录")


if __name__ == "__main__":
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except Exception:
        pass
    App(root)
    root.mainloop()
