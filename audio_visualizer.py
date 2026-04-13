"""
音频可视化模块 - 支持频率分析和动态颜色过渡
================================================
功能：
1. 捕获系统音频输出
2. 实时频率分析（FFT）
3. 节拍检测
4. 灰度到彩色的动态过渡
5. 可配置的颜色调色板和敏感度
"""

import numpy as np
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, List, Tuple, Optional
import colorsys


@dataclass
class VisualizerConfig:
    """可视化配置"""
    sensitivity: float = 1.0  # 敏感度 (0.5 - 2.0)
    transition_speed: float = 0.15  # 过渡速度 (0.05 - 0.5)
    color_palette: str = "rainbow"  # 调色板: rainbow, ocean, fire, neon, pastel
    bass_threshold: float = 0.3  # 低音阈值
    mid_threshold: float = 0.2  # 中音阈值
    treble_threshold: float = 0.15  # 高音阈值
    smoothing_factor: float = 0.3  # 平滑因子


class AudioVisualizer:
    """
    音频可视化核心类
    基于 Windows Core Audio API 捕获系统音频
    """

    # 预定义调色板
    PALETTES = {
        "rainbow": [
            (255, 0, 0), (255, 127, 0), (255, 255, 0),
            (0, 255, 0), (0, 0, 255), (75, 0, 130), (148, 0, 211)
        ],
        "ocean": [
            (0, 20, 40), (0, 60, 120), (0, 100, 200),
            (0, 150, 255), (100, 200, 255), (200, 230, 255)
        ],
        "fire": [
            (40, 0, 0), (80, 0, 0), (120, 20, 0),
            (180, 60, 0), (255, 100, 0), (255, 200, 0), (255, 255, 100)
        ],
        "neon": [
            (255, 0, 255), (0, 255, 255), (255, 255, 0),
            (0, 255, 0), (255, 0, 128), (128, 0, 255)
        ],
        "pastel": [
            (255, 179, 186), (255, 223, 186), (255, 255, 186),
            (186, 255, 201), (186, 225, 255), (218, 186, 255)
        ],
        "gold": [
            (50, 40, 20), (100, 80, 30), (150, 120, 40),
            (200, 160, 50), (255, 200, 60), (255, 220, 100)
        ]
    }

    def __init__(self, config: Optional[VisualizerConfig] = None):
        self.config = config or VisualizerConfig()
        self._running = False
        self._audio_thread: Optional[threading.Thread] = None

        # 音频数据缓冲区
        self._fft_data = np.zeros(64)
        self._bass_energy = 0.0
        self._mid_energy = 0.0
        self._treble_energy = 0.0
        self._overall_energy = 0.0

        # 平滑处理的历史数据
        self._energy_history = deque(maxlen=10)
        self._beat_history = deque(maxlen=8)

        # 当前颜色状态 (HSL格式)
        self._current_hue = 0.0
        self._current_saturation = 0.0  # 0.0 = 灰度, 1.0 = 全彩
        self._current_lightness = 0.5

        # 目标颜色状态
        self._target_saturation = 0.0
        self._target_hue = 0.0

        # 节拍检测
        self._last_beat_time = 0
        self._beat_detected = False
        self._bpm_estimate = 120

        # 回调函数
        self._on_color_update: Optional[Callable[[Tuple[int, int, int], float], None]] = None

    def start(self):
        """启动音频捕获和分析"""
        if self._running:
            return

        self._running = True
        self._audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self._audio_thread.start()
        print("[Visualizer] 音频可视化已启动")

    def stop(self):
        """停止音频捕获"""
        self._running = False
        if self._audio_thread:
            self._audio_thread.join(timeout=1.0)
        print("[Visualizer] 音频可视化已停止")

    def set_callback(self, callback: Callable[[Tuple[int, int, int], float], None]):
        """
        设置颜色更新回调
        callback: (rgb_color, intensity) -> None
        """
        self._on_color_update = callback

    def update_config(self, **kwargs):
        """更新配置参数"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                print(f"[Visualizer] 配置更新: {key} = {value}")

    def _audio_loop(self):
        """音频捕获和分析主循环"""
        try:
            # 尝试使用 Windows Core Audio
            self._capture_windows_audio()
        except Exception as e:
            print(f"[Visualizer] Windows音频捕获失败: {e}")
            # 降级到模拟模式（用于测试）
            self._simulate_audio()

    def _capture_windows_audio(self):
        """使用 Windows Core Audio API 捕获系统音频"""
        try:
            import comtypes
            from pycaw.pycaw import AudioUtilities, IAudioClient, IAudioCaptureClient
            from pycaw.constants import AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK

            # 获取默认音频设备
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioClient._iid_, 0, None)
            audio_client = interface.QueryInterface(IAudioClient)

            # 获取音频格式
            waveformatex = audio_client.GetMixFormat()
            sample_rate = waveformatex.nSamplesPerSec
            channels = waveformatex.nChannels

            # 初始化音频客户端
            buffer_duration = 10000000  # 100ms in 100-nanosecond units
            audio_client.Initialize(
                AUDCLNT_SHAREMODE_SHARED,
                AUDCLNT_STREAMFLAGS_LOOPBACK,
                buffer_duration,
                0,
                waveformatex,
                None
            )

            # 获取捕获客户端
            capture_client = audio_client.GetService(IAudioCaptureClient._iid_)

            # 开始捕获
            audio_client.Start()
            print(f"[Visualizer] 音频捕获启动: {sample_rate}Hz, {channels}ch")

            while self._running:
                try:
                    # 获取可用数据包
                    packet_length = capture_client.GetNextPacketSize()
                    if packet_length == 0:
                        time.sleep(0.001)
                        continue

                    # 读取音频数据
                    data, flags = capture_client.GetBuffer()
                    if data:
                        # 转换为numpy数组
                        audio_data = np.frombuffer(data, dtype=np.float32)
                        if channels > 1:
                            audio_data = audio_data.reshape(-1, channels).mean(axis=1)

                        # 分析音频
                        self._analyze_audio(audio_data, sample_rate)

                    capture_client.ReleaseBuffer(packet_length)

                except Exception as e:
                    time.sleep(0.001)

            audio_client.Stop()

        except ImportError:
            print("[Visualizer] 未安装 pycaw，切换到模拟模式")
            self._simulate_audio()

    def _simulate_audio(self):
        """模拟音频数据（用于测试）- 增强效果"""
        print("[Visualizer] 使用模拟音频模式（增强版）")
        print("[Visualizer] 模拟模式：歌词颜色会周期性变化")
        beat_phase = 0
        while self._running:
            # 生成模拟音频数据
            sample_rate = 44100
            duration = 0.05  # 50ms
            samples = int(sample_rate * duration)

            # 模拟节拍 - 更强的效果
            beat_phase += 0.25  # 节拍速度
            beat = (np.sin(beat_phase) + 1) / 2  # 0-1范围
            
            # 添加随机波动
            noise = np.random.random(samples) * 0.5
            
            # 合成音频数据 - 放大到0-1范围
            audio_data = np.zeros(samples)
            for i in range(samples):
                phase = i / samples
                # 节拍脉冲 - 高能量
                pulse = np.exp(-((phase - 0.5) ** 2) * 15) * beat
                audio_data[i] = min(1.0, pulse * 0.9 + noise[i] * 0.3)

            self._analyze_audio(audio_data, sample_rate)
            time.sleep(duration)

    def _analyze_audio(self, audio_data: np.ndarray, sample_rate: int):
        """分析音频数据"""
        if len(audio_data) < 64:
            return

        # 计算整体能量
        energy = np.sqrt(np.mean(audio_data ** 2))
        self._energy_history.append(energy)

        # 平滑处理
        smoothed_energy = np.mean(self._energy_history) if self._energy_history else energy
        self._overall_energy = smoothed_energy * self.config.sensitivity

        # FFT 频率分析
        fft = np.fft.rfft(audio_data)
        fft_magnitude = np.abs(fft)

        # 分频段能量计算
        freqs = np.fft.rfftfreq(len(audio_data), 1 / sample_rate)

        # 低音 (20-250Hz)
        bass_mask = (freqs >= 20) & (freqs <= 250)
        self._bass_energy = np.mean(fft_magnitude[bass_mask]) * self.config.sensitivity if np.any(bass_mask) else 0

        # 中音 (250-4000Hz)
        mid_mask = (freqs >= 250) & (freqs <= 4000)
        self._mid_energy = np.mean(fft_magnitude[mid_mask]) * self.config.sensitivity if np.any(mid_mask) else 0

        # 高音 (4000-20000Hz)
        treble_mask = (freqs >= 4000) & (freqs <= 20000)
        self._treble_energy = np.mean(fft_magnitude[treble_mask]) * self.config.sensitivity if np.any(treble_mask) else 0

        # 节拍检测
        self._detect_beat(smoothed_energy)

        # 更新颜色
        self._update_color()

    def _detect_beat(self, energy: float):
        """检测节拍"""
        current_time = time.time()

        # 使用阈值检测节拍
        threshold = np.mean(self._beat_history) * 1.3 if self._beat_history else 0.1
        is_beat = energy > threshold and energy > self.config.bass_threshold

        if is_beat and (current_time - self._last_beat_time) > 0.3:  # 最小节拍间隔
            self._beat_detected = True
            self._last_beat_time = current_time
        else:
            self._beat_detected = False

        self._beat_history.append(energy)

    def _update_color(self):
        """更新颜色状态"""
        # 根据音频能量计算目标饱和度
        # 基础饱和度由整体能量决定
        base_saturation = min(1.0, self._overall_energy * 2)

        # 节拍时增加饱和度
        if self._beat_detected:
            base_saturation = min(1.0, base_saturation * 1.5)

        self._target_saturation = base_saturation

        # 平滑过渡
        speed = self.config.transition_speed
        self._current_saturation += (self._target_saturation - self._current_saturation) * speed

        # 根据频段计算色调
        total_energy = self._bass_energy + self._mid_energy + self._treble_energy
        if total_energy > 0:
            # 低音偏红/橙，中音偏绿/黄，高音偏蓝/紫
            bass_ratio = self._bass_energy / total_energy
            mid_ratio = self._mid_energy / total_energy
            treble_ratio = self._treble_energy / total_energy

            # 计算目标色调
            target_hue = (bass_ratio * 0.05 + mid_ratio * 0.33 + treble_ratio * 0.66) % 1.0

            # 平滑色调过渡
            hue_diff = target_hue - self._current_hue
            # 处理色调环绕
            if hue_diff > 0.5:
                hue_diff -= 1.0
            elif hue_diff < -0.5:
                hue_diff += 1.0

            self._current_hue += hue_diff * speed
            self._current_hue %= 1.0

        # 计算亮度
        self._current_lightness = 0.3 + self._overall_energy * 0.4

        # 触发回调
        if self._on_color_update:
            rgb = self.get_current_rgb()
            intensity = self._current_saturation
            self._on_color_update(rgb, intensity)
        else:
            # 每2秒打印一次调试信息
            if not hasattr(self, '_debug_counter'):
                self._debug_counter = 0
            self._debug_counter += 1
            if self._debug_counter % 40 == 0:
                rgb = self.get_current_rgb()
                print(f"[Visualizer] 能量={self._overall_energy:.3f}, 饱和度={self._current_saturation:.3f}, RGB={rgb}, 回调={'已设置' if self._on_color_update else '未设置'}")

    def get_current_rgb(self) -> Tuple[int, int, int]:
        """获取当前 RGB 颜色"""
        # 获取调色板颜色
        palette = self.PALETTES.get(self.config.color_palette, self.PALETTES["rainbow"])

        # 根据当前色调选择调色板颜色
        palette_index = int(self._current_hue * (len(palette) - 1))
        palette_index = max(0, min(len(palette) - 1, palette_index))
        base_color = palette[palette_index]

        # 应用饱和度
        saturation = self._current_saturation
        lightness = self._current_lightness

        # 灰度颜色
        gray = int(128 * lightness)

        # 混合灰度和彩色
        r = int(gray * (1 - saturation) + base_color[0] * saturation * lightness)
        g = int(gray * (1 - saturation) + base_color[1] * saturation * lightness)
        b = int(gray * (1 - saturation) + base_color[2] * saturation * lightness)

        return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))

    def get_energy_levels(self) -> dict:
        """获取各频段能量水平"""
        return {
            "bass": self._bass_energy,
            "mid": self._mid_energy,
            "treble": self._treble_energy,
            "overall": self._overall_energy,
            "beat": self._beat_detected
        }


class VisualizerUI:
    """
    可视化UI组件
    提供配置界面和实时预览
    """

    def __init__(self, visualizer: AudioVisualizer, parent=None):
        self.visualizer = visualizer
        self.parent = parent
        self._window = None

    def show_config_window(self):
        """显示配置窗口"""
        try:
            import tkinter as tk
            from tkinter import ttk

            if self._window and self._window.winfo_exists():
                self._window.lift()
                return

            self._window = tk.Toplevel(self.parent) if self.parent else tk.Tk()
            self._window.title("音频可视化设置")
            self._window.geometry("400x500")
            self._window.configure(bg="#1a1a2e")

            # 标题
            tk.Label(
                self._window, text="音频可视化设置",
                font=("Microsoft YaHei UI", 14, "bold"),
                fg="#FFD700", bg="#1a1a2e"
            ).pack(pady=10)

            # 敏感度
            self._create_slider("敏感度", "sensitivity", 0.5, 2.0, 0.1)

            # 过渡速度
            self._create_slider("过渡速度", "transition_speed", 0.05, 0.5, 0.05)

            # 调色板选择
            tk.Label(
                self._window, text="调色板",
                font=("Microsoft YaHei UI", 11),
                fg="#AAAAAA", bg="#1a1a2e"
            ).pack(pady=(10, 5))

            palette_var = tk.StringVar(value=self.visualizer.config.color_palette)
            palette_combo = ttk.Combobox(
                self._window,
                textvariable=palette_var,
                values=list(self.visualizer.PALETTES.keys()),
                state="readonly"
            )
            palette_combo.pack(pady=5)
            palette_combo.bind("<<ComboboxSelected>>",
                              lambda e: self.visualizer.update_config(color_palette=palette_var.get()))

            # 预览区域
            tk.Label(
                self._window, text="颜色预览",
                font=("Microsoft YaHei UI", 11),
                fg="#AAAAAA", bg="#1a1a2e"
            ).pack(pady=(20, 5))

            self._preview_canvas = tk.Canvas(
                self._window, width=300, height=100,
                bg="#333333", highlightthickness=0
            )
            self._preview_canvas.pack(pady=10)

            # 能量显示
            self._energy_label = tk.Label(
                self._window, text="能量: 0.00 | 节拍: --",
                font=("Microsoft YaHei UI", 10),
                fg="#888888", bg="#1a1a2e"
            )
            self._energy_label.pack(pady=10)

            # 开始更新预览
            self._update_preview()

            if not self.parent:
                self._window.mainloop()

        except Exception as e:
            print(f"[VisualizerUI] 创建配置窗口失败: {e}")

    def _create_slider(self, label: str, config_key: str, min_val: float, max_val: float, step: float):
        """创建滑块控件"""
        import tkinter as tk

        frame = tk.Frame(self._window, bg="#1a1a2e")
        frame.pack(fill=tk.X, padx=20, pady=5)

        tk.Label(
            frame, text=label,
            font=("Microsoft YaHei UI", 11),
            fg="#AAAAAA", bg="#1a1a2e"
        ).pack(anchor=tk.W)

        value_var = tk.DoubleVar(value=getattr(self.visualizer.config, config_key))
        value_label = tk.Label(
            frame, text=f"{value_var.get():.2f}",
            font=("Microsoft YaHei UI", 10),
            fg="#FFD700", bg="#1a1a2e"
        )
        value_label.pack(anchor=tk.E)

        def on_scale(val):
            value = float(val)
            value_var.set(value)
            value_label.config(text=f"{value:.2f}")
            self.visualizer.update_config(**{config_key: value})

        scale = tk.Scale(
            frame, from_=min_val, to=max_val, resolution=step,
            orient=tk.HORIZONTAL, command=on_scale,
            bg="#1a1a2e", fg="#AAAAAA", highlightthickness=0,
            troughcolor="#333355", activebackground="#FFD700"
        )
        scale.set(value_var.get())
        scale.pack(fill=tk.X)

    def _update_preview(self):
        """更新预览"""
        if not self._window or not self._window.winfo_exists():
            return

        try:
            import tkinter as tk

            # 获取当前颜色
            rgb = self.visualizer.get_current_rgb()
            color_hex = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

            # 绘制渐变预览
            self._preview_canvas.delete("all")

            # 灰度到彩色的渐变
            for i in range(20):
                ratio = i / 19
                r = int(128 * (1 - ratio) + rgb[0] * ratio)
                g = int(128 * (1 - ratio) + rgb[1] * ratio)
                b = int(128 * (1 - ratio) + rgb[2] * ratio)
                c = f"#{r:02x}{g:02x}{b:02x}"
                self._preview_canvas.create_rectangle(
                    i * 15, 0, (i + 1) * 15, 100,
                    fill=c, outline=""
                )

            # 更新能量显示
            energy = self.visualizer.get_energy_levels()
            self._energy_label.config(
                text=f"能量: {energy['overall']:.2f} | "
                     f"低音: {energy['bass']:.2f} | "
                     f"节拍: {'●' if energy['beat'] else '○'}"
            )

            # 继续更新
            self._window.after(50, self._update_preview)

        except Exception as e:
            pass


# 测试代码
if __name__ == "__main__":
    print("音频可视化模块测试")
    print("=" * 40)

    # 创建可视化器
    config = VisualizerConfig(
        sensitivity=1.2,
        transition_speed=0.2,
        color_palette="rainbow"
    )
    visualizer = AudioVisualizer(config)

    # 设置回调
    def on_color_update(rgb, intensity):
        if intensity > 0.3:
            print(f"\r颜色: RGB{rgb} | 饱和度: {intensity:.2f}", end="", flush=True)

    visualizer.set_callback(on_color_update)

    # 启动
    visualizer.start()

    # 显示配置窗口
    ui = VisualizerUI(visualizer)
    ui.show_config_window()

    # 停止
    visualizer.stop()
