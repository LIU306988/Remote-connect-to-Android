# ==============================================
# 【必须放在最最开头】PyInstaller无控制台模式终极修复
# ==============================================
import sys
import os

# 第一步：立即将所有标准流重定向到空设备（这是最关键的第一步）
# 必须在导入任何其他模块之前执行
if sys.stdout is None or sys.stderr is None or sys.stdin is None:
    # 打开空设备文件
    devnull = open(os.devnull, "r+", encoding="utf-8", errors="replace")
    
    if sys.stdin is None:
        sys.stdin = devnull
    if sys.stdout is None:
        sys.stdout = devnull
    if sys.stderr is None:
        sys.stderr = devnull

# 第二步：强制设置Python的默认编码为UTF-8
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

# 第三步：现在可以安全地导入io并重新包装标准流
import io
try:
    # 尝试获取底层缓冲区，如果失败则保持原样
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
except Exception:
    # 如果包装失败，继续使用原来的空设备
    pass

# 第四步：禁用所有可能尝试写入控制台的库
import warnings
warnings.filterwarnings("ignore")

# ==============================================
# 以下是你的原始代码（已修复关键问题）
# ==============================================
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
import subprocess
import json
import platform
import threading
import re
import datetime
import time
import ctypes

# ==================== 便携版核心配置 ====================
def get_resource_path(relative_path):
    """获取资源文件的绝对路径（兼容开发环境和打包后环境）"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller单文件打包时的临时目录
        base_path = sys._MEIPASS
    else:
        # 开发环境或文件夹打包时的程序所在目录
        base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    
    return os.path.join(base_path, relative_path)

# 工具路径（优先使用同目录tools文件夹，其次使用系统PATH）
# 注意：打包时tools文件夹会被复制到临时目录
TOOLS_DIR = get_resource_path("tools")
ADB_PATH = os.path.join(TOOLS_DIR, "adb.exe")
SCRCPY_PATH = os.path.join(TOOLS_DIR, "scrcpy.exe")

# 如果同目录没有工具，则使用系统PATH中的
if not os.path.exists(ADB_PATH):
    ADB_PATH = "adb"
if not os.path.exists(SCRCPY_PATH):
    SCRCPY_PATH = "scrcpy"

# Windows下隐藏控制台窗口的通用配置
startupinfo = None
if platform.system() == "Windows":
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    
    # 修复Windows DPI缩放问题
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Windows 8.1+
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # Windows Vista+
        except Exception:
            pass
# ======================================================

class ADBManager:
    def __init__(self, root):
        self.root = root
        self.root.title("ADB设备管理器2.1 便携版")
        self.root.geometry("850x700")
        self.root.minsize(850, 700)
        
        # 配置文件保存在exe同目录（而不是临时目录）
        self.exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.config_file = os.path.join(self.exe_dir, "adb_devices.json")
        self.scrcpy_config = os.path.join(self.exe_dir, "scrcpy_settings.json")
        
        self.devices = self.load_devices()
        self.scrcpy_settings = self.load_scrcpy_settings()
        
        # 提前初始化工具可用性属性（修复错误的关键）
        self.adb_available = False
        self.scrcpy_available = False
        self.scrcpy_version = (0, 0, 0)
        
        self.setup_fonts()
        
        # 先检测工具可用性，再创建界面
        self.check_tools_availability()
        self.scrcpy_version = self.detect_scrcpy_version()
        
        # 最后创建界面
        self.create_widgets()
        
        self.log(f"检测到Scrcpy版本: {'.'.join(map(str, self.scrcpy_version))}")
        self.refresh_connected_devices()
        
        # 设置窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """窗口关闭时的清理操作"""
        try:
            # 关闭所有可能的子进程
            if hasattr(self, 'scrcpy_processes'):
                for process in self.scrcpy_processes:
                    if process.poll() is None:
                        process.terminate()
        except Exception:
            pass
        self.root.destroy()

    def check_tools_availability(self):
        """检查ADB和Scrcpy是否可用"""
        try:
            result = subprocess.run(
                [ADB_PATH, "version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            self.adb_available = True
            print(f"ADB工具可用: {ADB_PATH}")
        except Exception as e:
            print(f"ADB工具不可用: {str(e)}")
        
        try:
            result = subprocess.run(
                [SCRCPY_PATH, "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            self.scrcpy_available = True
            print(f"Scrcpy工具可用: {SCRCPY_PATH}")
        except Exception as e:
            print(f"Scrcpy工具不可用: {str(e)}")

    def detect_scrcpy_version(self):
        """自动检测scrcpy版本号"""
        if not self.scrcpy_available:
            return (0, 0, 0)
            
        try:
            result = subprocess.run(
                [SCRCPY_PATH, "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            output = result.stdout.strip()
            match = re.search(r'scrcpy\s+v?(\d+\.\d+(\.\d+)?)', output)
            if match:
                version_str = match.group(1)
                version_parts = list(map(int, version_str.split('.')))
                while len(version_parts) < 3:
                    version_parts.append(0)
                return tuple(version_parts)
            return (0, 0, 0)
        except Exception as e:
            print(f"检测Scrcpy版本失败: {str(e)}")
            return (0, 0, 0)

    def is_scrcpy_version_at_least(self, major, minor=0, patch=0):
        """检查scrcpy版本是否至少为指定版本"""
        return self.scrcpy_version >= (major, minor, patch)

    def setup_fonts(self):
        system = platform.system()
        if system == "Windows":
            default_font = ("SimHei", 10)
        elif system == "Darwin":
            default_font = ("Heiti TC", 10)
        else:
            default_font = ("WenQuanYi Micro Hei", 10)
        
        self.root.option_add("*Font", default_font)
        self.style = ttk.Style()
        self.style.configure("Treeview", rowheight=25)
        self.style.configure("TButton", padding=5)
        self.style.configure("TLabelFrame", padding=5)

    def create_widgets(self):
        tab_control = ttk.Notebook(self.root)
        
        self.connect_tab = ttk.Frame(tab_control)
        tab_control.add(self.connect_tab, text="设备连接")
        
        self.connected_tab = ttk.Frame(tab_control)
        tab_control.add(self.connected_tab, text="已连接设备")
        
        self.scrcpy_tab = ttk.Frame(tab_control)
        tab_control.add(self.scrcpy_tab, text="Scrcpy设置")
        
        self.log_tab = ttk.Frame(tab_control)
        tab_control.add(self.log_tab, text="操作日志")
        
        tab_control.pack(expand=1, fill="both", padx=5, pady=5)
        
        self.init_connect_tab()
        self.init_connected_tab()
        self.init_scrcpy_tab()
        self.init_log_tab()
        
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w", padding=(5, 2))
        status_bar.pack(side="bottom", fill="x")
        
        # 如果工具不可用，禁用相关功能
        if not self.adb_available:
            messagebox.showerror("致命错误", "未找到ADB工具！\n请确保tools文件夹中包含adb.exe及相关dll文件")
            self.root.quit()
            
        if not self.scrcpy_available:
            messagebox.showwarning("警告", "未找到Scrcpy工具，屏幕投射功能将无法使用")
            self.disable_scrcpy_functions()

    def disable_scrcpy_functions(self):
        """禁用所有Scrcpy相关功能"""
        self.scrcpy_saved_btn.config(state="disabled")
        self.scrcpy_connected_btn.config(state="disabled")
        self.test_scrcpy_btn.config(state="disabled")
        for child in self.scrcpy_tab.winfo_children():
            if isinstance(child, (ttk.Button, ttk.Entry, ttk.Checkbutton, ttk.Radiobutton, ttk.Combobox)):
                child.config(state="disabled")

    def init_connect_tab(self):
        # 连接区域
        conn_frame = ttk.LabelFrame(self.connect_tab, text="通过IP连接设备")
        conn_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(conn_frame, text="设备IP地址:").grid(row=0, column=0, padx=5, pady=10, sticky="w")
        self.ip_entry = ttk.Entry(conn_frame, width=20)
        self.ip_entry.grid(row=0, column=1, padx=5, pady=10, sticky="w")
        self.ip_entry.insert(0, "192.168.")
        
        ttk.Label(conn_frame, text="端口 (默认5555):").grid(row=0, column=2, padx=5, pady=10, sticky="w")
        self.port_entry = ttk.Entry(conn_frame, width=8)
        self.port_entry.grid(row=0, column=3, padx=5, pady=10, sticky="w")
        self.port_entry.insert(0, "5555")
        
        self.connect_btn = ttk.Button(conn_frame, text="连接设备", command=self.connect_device)
        self.connect_btn.grid(row=0, column=4, padx=5, pady=10)
        
        self.get_ip_btn = ttk.Button(conn_frame, text="获取有线设备IP", command=self.get_wired_device_ip)
        self.get_ip_btn.grid(row=0, column=5, padx=5, pady=10)
        
        # 已保存设备列表
        saved_frame = ttk.LabelFrame(self.connect_tab, text="已保存的设备")
        saved_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ("备注", "IP地址", "端口")
        self.device_tree = ttk.Treeview(saved_frame, columns=columns, show="headings", height=12)
        self.device_tree.column("备注", width=180)
        self.device_tree.column("IP地址", width=180)
        self.device_tree.column("端口", width=80)
        
        for col in columns:
            self.device_tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(saved_frame, orient="vertical", command=self.device_tree.yview)
        self.device_tree.configure(yscroll=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        self.device_tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.refresh_device_list()
        
        # 设备管理按钮
        btn_frame = ttk.Frame(self.connect_tab)
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        self.save_btn = ttk.Button(btn_frame, text="保存当前连接", command=self.save_current_device)
        self.save_btn.pack(side="left", padx=5)
        
        self.delete_btn = ttk.Button(btn_frame, text="删除选中设备", command=self.delete_selected_device)
        self.delete_btn.pack(side="left", padx=5)
        
        self.refresh_btn = ttk.Button(btn_frame, text="刷新设备列表", command=self.refresh_device_list)
        self.refresh_btn.pack(side="left", padx=5)
        
        self.export_btn = ttk.Button(btn_frame, text="导出设备列表", command=self.export_devices)
        self.export_btn.pack(side="left", padx=5)
        
        self.import_btn = ttk.Button(btn_frame, text="导入设备列表", command=self.import_devices)
        self.import_btn.pack(side="left", padx=5)
        
        # 操作按钮
        op_btn_frame = ttk.Frame(self.connect_tab)
        op_btn_frame.pack(fill="x", padx=10, pady=5)
        
        self.connect_saved_btn = ttk.Button(op_btn_frame, text="连接选中设备", command=self.connect_selected_device)
        self.connect_saved_btn.pack(side="left", padx=5)
        
        self.scrcpy_saved_btn = ttk.Button(op_btn_frame, text="Scrcpy远程设备", command=self.scrcpy_selected_device)
        self.scrcpy_saved_btn.pack(side="left", padx=5)
        
        self.edit_saved_btn = ttk.Button(op_btn_frame, text="编辑选中设备", command=self.edit_selected_device)
        self.edit_saved_btn.pack(side="left", padx=5)

    def init_connected_tab(self):
        frame = ttk.LabelFrame(self.connected_tab, text="当前已连接的设备")
        frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        columns = ("备注", "设备ID", "状态")
        self.connected_tree = ttk.Treeview(frame, columns=columns, show="headings", height=15)
        self.connected_tree.column("备注", width=180)
        self.connected_tree.column("设备ID", width=250)
        self.connected_tree.column("状态", width=100)
        
        for col in columns:
            self.connected_tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.connected_tree.yview)
        self.connected_tree.configure(yscroll=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        self.connected_tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 操作按钮
        btn_frame = ttk.Frame(self.connected_tab)
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        self.refresh_connected_btn = ttk.Button(btn_frame, text="刷新连接列表", command=self.refresh_connected_devices)
        self.refresh_connected_btn.pack(side="left", padx=5)
        
        self.disconnect_btn = ttk.Button(btn_frame, text="断开选中连接", command=self.disconnect_device)
        self.disconnect_btn.pack(side="left", padx=5)
        
        self.scrcpy_connected_btn = ttk.Button(btn_frame, text="Scrcpy远程设备", command=self.scrcpy_connected_device)
        self.scrcpy_connected_btn.pack(side="left", padx=5)
        
        self.save_connected_btn = ttk.Button(btn_frame, text="保存选中设备", command=self.save_connected_device_selected)
        self.save_connected_btn.pack(side="left", padx=5)
        
        # 应用管理按钮
        app_btn_frame = ttk.Frame(self.connected_tab)
        app_btn_frame.pack(fill="x", padx=10, pady=5)
        
        self.install_apk_btn = ttk.Button(app_btn_frame, text="安装APK", command=self.install_apk_to_devices)
        self.install_apk_btn.pack(side="left", padx=5)
        
        self.uninstall_app_btn = ttk.Button(app_btn_frame, text="卸载App", command=self.uninstall_app_from_devices)
        self.uninstall_app_btn.pack(side="left", padx=5)
        
        self.open_app_btn = ttk.Button(app_btn_frame, text="打开App", command=self.open_app_on_devices)
        self.open_app_btn.pack(side="left", padx=5)
        
        self.screenshot_btn = ttk.Button(app_btn_frame, text="截图", command=self.take_screenshot)
        self.screenshot_btn.pack(side="left", padx=5)

    def init_scrcpy_tab(self):
        frame = ttk.LabelFrame(self.scrcpy_tab, text="Scrcpy参数设置")
        frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 视频设置
        video_frame = ttk.LabelFrame(frame, text="视频设置")
        video_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(video_frame, text="最大分辨率 (如1080):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.max_size = ttk.Entry(video_frame, width=10)
        self.max_size.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(video_frame, text="比特率 (如8M):").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.bitrate = ttk.Entry(video_frame, width=10)
        self.bitrate.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        
        ttk.Label(video_frame, text="帧率 (如60):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.fps = ttk.Entry(video_frame, width=10)
        self.fps.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        # 窗口设置
        window_frame = ttk.LabelFrame(frame, text="窗口设置")
        window_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(window_frame, text="窗口标题:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.window_title = ttk.Entry(window_frame, width=30)
        self.window_title.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        self.window_borderless = tk.BooleanVar()
        ttk.Checkbutton(window_frame, text="无边框窗口", variable=self.window_borderless).grid(row=0, column=2, padx=15, pady=5, sticky="w")
        
        self.always_on_top = tk.BooleanVar()
        ttk.Checkbutton(window_frame, text="窗口始终置顶", variable=self.always_on_top).grid(row=1, column=0, padx=15, pady=5, sticky="w")
        
        self.show_touches = tk.BooleanVar()
        ttk.Checkbutton(window_frame, text="显示触摸操作", variable=self.show_touches).grid(row=1, column=1, padx=15, pady=5, sticky="w")
        
        # 音频设置
        audio_frame = ttk.LabelFrame(frame, text="音频设置")
        audio_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(audio_frame, text="音频输出模式:").grid(row=0, column=0, padx=5, pady=10, sticky="w")
        
        self.audio_mode = tk.StringVar(value="host")
        audio_modes = [
            ("仅电脑播放 (默认)", "host"),
            ("仅设备播放", "device"),
            ("两端同时播放 (Android 13+)", "both"),
            ("禁用音频", "none")
        ]
        
        for i, (text, value) in enumerate(audio_modes):
            ttk.Radiobutton(audio_frame, text=text, variable=self.audio_mode, value=value).grid(row=0, column=i+1, padx=10, pady=10, sticky="w")
        
        # 兼容性设置
        compat_frame = ttk.LabelFrame(frame, text="兼容性设置")
        compat_frame.pack(fill="x", padx=10, pady=5)
        
        self.no_downsize_on_error = tk.BooleanVar(value=True)
        ttk.Checkbutton(compat_frame, text="禁用错误时自动降分辨率 (解决黑屏)", variable=self.no_downsize_on_error).grid(row=0, column=0, padx=15, pady=5, sticky="w")
        
        self.no_clipboard = tk.BooleanVar(value=False)
        ttk.Checkbutton(compat_frame, text="禁用剪贴板同步", variable=self.no_clipboard).grid(row=0, column=1, padx=15, pady=5, sticky="w")
        
        self.video_codec = tk.StringVar(value="h264")
        ttk.Label(compat_frame, text="视频编码器:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        codec_combo = ttk.Combobox(compat_frame, textvariable=self.video_codec, values=["h264", "h265", "av1"], width=10, state="readonly")
        codec_combo.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        # 保存按钮
        btn_frame = ttk.Frame(self.scrcpy_tab)
        btn_frame.pack(fill="x", padx=10, pady=15)
        
        self.save_scrcpy_btn = ttk.Button(btn_frame, text="保存Scrcpy设置", command=self.save_scrcpy_settings)
        self.save_scrcpy_btn.pack(side="left", padx=5)
        
        self.reset_scrcpy_btn = ttk.Button(btn_frame, text="恢复默认设置", command=self.reset_scrcpy_settings)
        self.reset_scrcpy_btn.pack(side="left", padx=5)
        
        self.test_scrcpy_btn = ttk.Button(btn_frame, text="测试默认参数", command=self.test_scrcpy_default)
        self.test_scrcpy_btn.pack(side="left", padx=5)
        
        self.load_scrcpy_settings_to_ui()

    def load_scrcpy_settings(self):
        try:
            if os.path.exists(self.scrcpy_config):
                with open(self.scrcpy_config, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    defaults = {
                        "max_size": "1080",
                        "bitrate": "8M",
                        "fps": "60",
                        "window_title": "",
                        "window_borderless": False,
                        "always_on_top": False,
                        "show_touches": False,
                        "audio_mode": "host",
                        "no_downsize_on_error": True,
                        "no_clipboard": False,
                        "video_codec": "h264"
                    }
                    defaults.update(settings)
                    return defaults
            return {
                "max_size": "1080",
                "bitrate": "8M",
                "fps": "60",
                "window_title": "",
                "window_borderless": False,
                "always_on_top": False,
                "show_touches": False,
                "audio_mode": "host",
                "no_downsize_on_error": True,
                "no_clipboard": False,
                "video_codec": "h264"
            }
        except Exception as e:
            print(f"加载Scrcpy设置失败: {str(e)}")
            return {
                "max_size": "1080",
                "bitrate": "8M",
                "fps": "60",
                "window_title": "",
                "window_borderless": False,
                "always_on_top": False,
                "show_touches": False,
                "audio_mode": "host",
                "no_downsize_on_error": True,
                "no_clipboard": False,
                "video_codec": "h264"
            }

    def load_scrcpy_settings_to_ui(self):
        self.max_size.delete(0, tk.END)
        self.max_size.insert(0, self.scrcpy_settings.get("max_size", "1080"))
        
        self.bitrate.delete(0, tk.END)
        self.bitrate.insert(0, self.scrcpy_settings.get("bitrate", "8M"))
        
        self.fps.delete(0, tk.END)
        self.fps.insert(0, self.scrcpy_settings.get("fps", "60"))
        
        self.window_title.delete(0, tk.END)
        self.window_title.insert(0, self.scrcpy_settings.get("window_title", ""))
        
        self.window_borderless.set(self.scrcpy_settings.get("window_borderless", False))
        self.always_on_top.set(self.scrcpy_settings.get("always_on_top", False))
        self.show_touches.set(self.scrcpy_settings.get("show_touches", False))
        self.audio_mode.set(self.scrcpy_settings.get("audio_mode", "host"))
        self.no_downsize_on_error.set(self.scrcpy_settings.get("no_downsize_on_error", True))
        self.no_clipboard.set(self.scrcpy_settings.get("no_clipboard", False))
        self.video_codec.set(self.scrcpy_settings.get("video_codec", "h264"))

    def save_scrcpy_settings(self):
        try:
            self.scrcpy_settings = {
                "max_size": self.max_size.get().strip() or "1080",
                "bitrate": self.bitrate.get().strip() or "8M",
                "fps": self.fps.get().strip() or "60",
                "window_title": self.window_title.get().strip(),
                "window_borderless": self.window_borderless.get(),
                "always_on_top": self.always_on_top.get(),
                "show_touches": self.show_touches.get(),
                "audio_mode": self.audio_mode.get(),
                "no_downsize_on_error": self.no_downsize_on_error.get(),
                "no_clipboard": self.no_clipboard.get(),
                "video_codec": self.video_codec.get()
            }
            with open(self.scrcpy_config, "w", encoding="utf-8") as f:
                json.dump(self.scrcpy_settings, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("成功", "Scrcpy设置已保存", parent=self.root)
            self.log("Scrcpy设置已保存")
            return True
        except Exception as e:
            messagebox.showerror("错误", f"保存Scrcpy设置失败: {str(e)}", parent=self.root)
            self.log(f"保存Scrcpy设置失败: {str(e)}")
            return False

    def reset_scrcpy_settings(self):
        if messagebox.askyesno("确认", "确定要恢复Scrcpy默认设置吗？", parent=self.root):
            self.scrcpy_settings = {
                "max_size": "1080",
                "bitrate": "8M",
                "fps": "60",
                "window_title": "",
                "window_borderless": False,
                "always_on_top": False,
                "show_touches": False,
                "audio_mode": "host",
                "no_downsize_on_error": True,
                "no_clipboard": False,
                "video_codec": "h264"
            }
            self.load_scrcpy_settings_to_ui()
            self.save_scrcpy_settings()
            self.log("Scrcpy设置已恢复默认")

    def test_scrcpy_default(self):
        """使用最简单的参数测试scrcpy是否能正常工作"""
        selected = self.connected_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要操作的设备", parent=self.root)
            return
        
        serial = self.connected_tree.item(selected[0], "values")[1]
        self.status_var.set(f"正在使用默认参数测试scrcpy...")
        self.root.update()
        threading.Thread(target=self._test_scrcpy_thread, args=(serial,), daemon=True).start()

    def _test_scrcpy_thread(self, serial):
        try:
            cmd = [SCRCPY_PATH, "-s", serial]
            
            self.log(f"测试scrcpy命令: {' '.join(cmd)}")
            
            env = os.environ.copy()
            env["PNG_SKIP_sRGB_CHECK_PROFILE"] = "1"
            env["PYTHONUTF8"] = "1"
            env["LANG"] = "en_US.UTF-8"
            
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            
            try:
                stdout, stderr = process.communicate(timeout=3)
                if process.returncode != 0:
                    error_msg = f"Scrcpy启动失败\n返回码: {process.returncode}\n错误输出:\n{stderr}"
                    self.log(error_msg)
                    self.root.after(0, lambda: messagebox.showerror("失败", error_msg, parent=self.root))
                    return
            except subprocess.TimeoutExpired:
                self.log("Scrcpy测试启动成功！")
                self.root.after(0, lambda: messagebox.showinfo("成功", "Scrcpy测试命令已发送\n如果3秒内没有弹出窗口，请：\n1. 检查Windows防火墙是否阻止了scrcpy\n2. 确保设备已开启USB调试(安全设置)\n3. 尝试更换视频编码器", parent=self.root))
                return
                
        except Exception as e:
            error_msg = f"启动scrcpy失败: {str(e)}"
            self.log(error_msg)
            self.root.after(0, lambda: messagebox.showerror("失败", error_msg, parent=self.root))

    def init_log_tab(self):
        frame = ttk.LabelFrame(self.log_tab, text="操作日志")
        frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        btn_frame = ttk.Frame(self.log_tab)
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        self.clear_log_btn = ttk.Button(btn_frame, text="清空日志", command=self.clear_log)
        self.clear_log_btn.pack(side="left", padx=5)
        
        self.export_log_btn = ttk.Button(btn_frame, text="导出日志", command=self.export_log)
        self.export_log_btn.pack(side="left", padx=5)
        
        self.log("ADB设备管理器便携版已启动")
        self.log(f"程序目录: {self.exe_dir}")
        self.log(f"临时目录: {get_resource_path('')}")

    def log(self, message):
        if not hasattr(self, 'log_text'):
            print(message)
            return
            
        time_str = datetime.datetime.now().strftime("%H:%M:%S")
        # 确保日志操作在主线程中执行
        def _log():
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, f"[{time_str}] {message}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")
        
        if threading.current_thread() is threading.main_thread():
            _log()
        else:
            self.root.after(0, _log)

    def clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")
        self.log("日志已清空")

    def export_log(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("日志文件", "*.log"), ("文本文件", "*.txt"), ("所有文件", "*.*")],
            title="导出操作日志"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.log_text.get(1.0, tk.END))
                messagebox.showinfo("成功", f"日志已导出到:\n{file_path}", parent=self.root)
                self.log(f"操作日志已导出到: {file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"导出日志失败: {str(e)}", parent=self.root)
                self.log(f"导出日志失败: {str(e)}")

    def load_devices(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"加载设备信息失败: {str(e)}")
            return []

    def save_devices(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.devices, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            messagebox.showerror("错误", f"保存设备信息失败: {str(e)}", parent=self.root)
            self.log(f"保存设备信息失败: {str(e)}")
            return False

    def export_devices(self):
        if not self.devices:
            messagebox.showinfo("提示", "没有可导出的设备", parent=self.root)
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
            title="导出设备列表"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(self.devices, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("成功", f"设备列表已导出到:\n{file_path}", parent=self.root)
                self.log(f"设备列表已导出到: {file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {str(e)}", parent=self.root)
                self.log(f"设备导出失败: {str(e)}")

    def import_devices(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")],
            title="导入设备列表"
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    imported_devices = json.load(f)
                
                valid = True
                for device in imported_devices:
                    if not all(k in device for k in ["name", "ip", "port"]):
                        valid = False
                        break
                
                if not valid:
                    messagebox.showerror("错误", "导入的文件格式不正确", parent=self.root)
                    return
                
                if self.devices:
                    answer = messagebox.askyesnocancel(
                        "选择操作", 
                        "是否替换现有设备列表？\n(选择否将合并设备，选择取消将取消导入)", 
                        parent=self.root
                    )
                    if answer is None:
                        return
                    elif answer is False:
                        existing = {(d["ip"], d["port"]) for d in self.devices}
                        new_devices = [d for d in imported_devices if (d["ip"], d["port"]) not in existing]
                        self.devices.extend(new_devices)
                    else:
                        self.devices = imported_devices
                else:
                    self.devices = imported_devices
                
                self.save_devices()
                self.refresh_device_list()
                messagebox.showinfo("成功", f"已导入 {len(imported_devices)} 个设备", parent=self.root)
                self.log(f"已从 {file_path} 导入 {len(imported_devices)} 个设备")
            except Exception as e:
                messagebox.showerror("错误", f"导入失败: {str(e)}", parent=self.root)
                self.log(f"设备导入失败: {str(e)}")

    def refresh_device_list(self):
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)
        
        for device in self.devices:
            self.device_tree.insert(
                "", "end",
                values=(device["name"], device["ip"], device["port"])
            )

    def connect_selected_device(self):
        selected = self.device_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要连接的设备", parent=self.root)
            return
        
        devices = [self.devices[self.device_tree.index(item)] for item in selected]
        self.status_var.set(f"正在连接 {len(devices)} 个设备...")
        
        for device in devices:
            threading.Thread(
                target=self._connect_device_thread, 
                args=(device["ip"], device["port"]), 
                daemon=True
            ).start()

    def scrcpy_selected_device(self):
        selected = self.device_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要操作的设备", parent=self.root)
            return
        
        index = self.device_tree.index(selected[0])
        device = self.devices[index]
        self.start_scrcpy(device["ip"], device["port"])

    def edit_selected_device(self):
        selected = self.device_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要编辑的设备", parent=self.root)
            return
        
        index = self.device_tree.index(selected[0])
        self.edit_device(index)

    def refresh_connected_devices(self):
        for item in self.connected_tree.get_children():
            self.connected_tree.delete(item)
        
        success, output = self.run_adb_command([ADB_PATH, "devices"])
        if success and output:
            lines = output.strip().split("\n")[1:]
            for line in lines:
                if line.strip():
                    parts = line.strip().split("\t")
                    if len(parts) == 2:
                        device_id, status = parts
                        remark = ""
                        for d in self.devices:
                            if f"{d['ip']}:{d['port']}" == device_id:
                                remark = d["name"]
                                break
                            if d["ip"] == device_id:
                                remark = d["name"]
                        self.connected_tree.insert("", "end", values=(remark, device_id, status))
        
        self.log("已刷新连接设备列表")

    def install_apk_to_devices(self):
        selected = self.connected_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要安装APK的设备", parent=self.root)
            return
        
        apk_path = filedialog.askopenfilename(
            filetypes=[("APK文件", "*.apk"), ("所有文件", "*.*")],
            title="选择要安装的APK文件"
        )
        if not apk_path:
            return
        
        serials = [self.connected_tree.item(item, "values")[1] for item in selected]
        self.status_var.set(f"正在安装APK到 {len(serials)} 个设备...")
        self.root.update()
        
        threading.Thread(
            target=self._install_apk_batch_thread, 
            args=(serials, apk_path), 
            daemon=True
        ).start()

    def _install_apk_batch_thread(self, serials, apk_path):
        results = []
        for serial in serials:
            try:
                success, output = self.run_adb_command([ADB_PATH, "-s", serial, "install", "-r", apk_path])
            except Exception as e:
                success, output = False, str(e)
            results.append((serial, success, output))
        
        def update_ui():
            msg = ""
            success_count = 0
            for serial, success, output in results:
                if success:
                    msg += f"{serial} 安装成功\n"
                    self.log(f"{serial} 安装APK成功: {apk_path}")
                    success_count += 1
                else:
                    msg += f"{serial} 安装失败: {output}\n"
                    self.log(f"{serial} 安装APK失败: {output}")
            
            self.status_var.set(f"安装完成: {success_count}/{len(serials)} 成功")
            messagebox.showinfo("安装结果", msg, parent=self.root)
        
        self.root.after(0, update_ui)

    def uninstall_app_from_devices(self):
        selected = self.connected_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要卸载App的设备", parent=self.root)
            return
        
        package = simpledialog.askstring(
            "卸载App", 
            "请输入要卸载的包名（如com.example.app）:", 
            parent=self.root
        )
        if not package:
            return
        
        serials = [self.connected_tree.item(item, "values")[1] for item in selected]
        self.status_var.set(f"正在卸载 {package} ...")
        self.root.update()
        
        threading.Thread(
            target=self._uninstall_app_batch_thread, 
            args=(serials, package), 
            daemon=True
        ).start()

    def _uninstall_app_batch_thread(self, serials, package):
        results = []
        for serial in serials:
            try:
                success, output = self.run_adb_command([ADB_PATH, "-s", serial, "uninstall", package])
            except Exception as e:
                success, output = False, str(e)
            results.append((serial, success, output))
        
        def update_ui():
            msg = ""
            success_count = 0
            for serial, success, output in results:
                if success and "Success" in output:
                    msg += f"{serial} 卸载成功\n"
                    self.log(f"{serial} 卸载App成功: {package}")
                    success_count += 1
                else:
                    msg += f"{serial} 卸载失败: {output}\n"
                    self.log(f"{serial} 卸载App失败: {output}")
            
            self.status_var.set(f"卸载完成: {success_count}/{len(serials)} 成功")
            messagebox.showinfo("卸载结果", msg, parent=self.root)
        
        self.root.after(0, update_ui)

    def open_app_on_devices(self):
        selected = self.connected_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要打开App的设备", parent=self.root)
            return
        
        package = simpledialog.askstring(
            "打开App", 
            "请输入要打开的包名（如com.example.app）:", 
            parent=self.root
        )
        if not package:
            return
        
        serials = [self.connected_tree.item(item, "values")[1] for item in selected]
        self.status_var.set(f"正在打开 {package} ...")
        self.root.update()
        
        threading.Thread(
            target=self._open_app_batch_thread, 
            args=(serials, package), 
            daemon=True
        ).start()

    def _open_app_batch_thread(self, serials, package):
        results = []
        for serial in serials:
            try:
                success, output = self.run_adb_command(
                    [ADB_PATH, "-s", serial, "shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"]
                )
            except Exception as e:
                success, output = False, str(e)
            results.append((serial, success, output))
        
        def update_ui():
            msg = ""
            success_count = 0
            for serial, success, output in results:
                if success:
                    msg += f"{serial} 打开成功\n"
                    self.log(f"{serial} 打开App成功: {package}")
                    success_count += 1
                else:
                    msg += f"{serial} 打开失败: {output}\n"
                    self.log(f"{serial} 打开App失败: {output}")
            
            self.status_var.set(f"打开完成: {success_count}/{len(serials)} 成功")
            messagebox.showinfo("打开结果", msg, parent=self.root)
        
        self.root.after(0, update_ui)

    def take_screenshot(self):
        selected = self.connected_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要截图的设备", parent=self.root)
            return
        
        serial = self.connected_tree.item(selected[0], "values")[1]
        self.status_var.set(f"正在为 {serial} 截图...")
        self.root.update()
        
        threading.Thread(
            target=self._screenshot_thread, 
            args=(serial,), 
            daemon=True
        ).start()

    def _screenshot_thread(self, serial):
        try:
            success, _ = self.run_adb_command([ADB_PATH, "-s", serial, "shell", "screencap", "-p", "/sdcard/screenshot.png"])
            if not success:
                raise Exception("截图失败")
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{serial.replace(':', '_')}_{timestamp}.png"
            
            success, _ = self.run_adb_command([ADB_PATH, "-s", serial, "pull", "/sdcard/screenshot.png", filename])
            if not success:
                raise Exception("拉取截图失败")
            
            self.run_adb_command([ADB_PATH, "-s", serial, "shell", "rm", "/sdcard/screenshot.png"])
            
            self.root.after(0, lambda: [
                self.status_var.set(f"截图已保存: {filename}"),
                messagebox.showinfo("成功", f"截图已保存为:\n{filename}", parent=self.root),
                self.log(f"设备 {serial} 截图已保存: {filename}")
            ])
        except Exception as e:
            self.root.after(0, lambda: [
                self.status_var.set("截图失败"),
                messagebox.showerror("失败", f"截图失败:\n{str(e)}", parent=self.root),
                self.log(f"设备 {serial} 截图失败: {str(e)}")
            ])

    def _start_scrcpy_thread(self, serial):
        try:
            self.log(f"正在检查设备 {serial} 是否在线...")
            for i in range(3):
                success, output = self.run_adb_command([ADB_PATH, "devices"])
                if success and serial in output:
                    break
                self.log(f"设备不在线，尝试连接... ({i+1}/3)")
                success, output = self.run_adb_command([ADB_PATH, "connect", serial])
                if success:
                    time.sleep(1)
                    break
                time.sleep(1)
            else:
                self.root.after(0, lambda: [
                    self.status_var.set("Scrcpy启动失败"),
                    messagebox.showerror("失败", f"无法连接设备:\n{output}", parent=self.root),
                    self.log(f"Scrcpy启动失败: 无法连接设备 {serial}")
                ])
                return
            
            cmd = [SCRCPY_PATH, "-s", serial]
            
            max_size = self.max_size.get().strip()
            if max_size and max_size.isdigit():
                cmd.extend(["-m", max_size])
            
            bitrate = self.bitrate.get().strip()
            if bitrate:
                cmd.extend(["-b", bitrate])
            
            fps = self.fps.get().strip()
            if fps and fps.isdigit():
                cmd.extend(["--max-fps", fps])
            
            codec = self.video_codec.get()
            if codec:
                cmd.extend(["--video-codec", codec])
            
            title = self.window_title.get().strip()
            if title:
                cmd.extend(["--window-title", title])
            
            if self.window_borderless.get():
                cmd.append("--window-borderless")
            
            if self.always_on_top.get():
                cmd.append("--always-on-top")
            
            if self.show_touches.get():
                cmd.append("--show-touches")
            
            # 正确的音频参数
            audio_mode = self.audio_mode.get()
            if audio_mode == "none":
                cmd.append("--no-audio")
            elif audio_mode == "device":
                cmd.append("--no-playback")
            elif audio_mode == "both":
                if self.is_scrcpy_version_at_least(2, 0, 0):
                    cmd.append("--audio-dup")
                    self.log("注意: 两端同时播放需要Android 13及以上版本")
                else:
                    self.log("警告: 当前Scrcpy版本不支持--audio-dup参数，将使用默认音频模式")
                    messagebox.showwarning("兼容性警告", 
                        "当前Scrcpy版本不支持两端同时播放功能\n"
                        "请升级到Scrcpy 2.0或更高版本\n"
                        "将使用默认音频模式(仅电脑播放)", 
                        parent=self.root)
            
            if self.no_downsize_on_error.get():
                if self.is_scrcpy_version_at_least(4, 0, 0):
                    cmd.append("--no-downsize-on-error")
                elif self.is_scrcpy_version_at_least(3, 0, 0):
                    cmd.append("--no-dlsr")
            
            if self.no_clipboard.get():
                cmd.append("--no-clipboard")
            
            self.log(f"构建scrcpy命令: {' '.join(cmd)}")
            
            env = os.environ.copy()
            env["PNG_SKIP_sRGB_CHECK_PROFILE"] = "1"
            env["PYTHONUTF8"] = "1"
            env["LANG"] = "en_US.UTF-8"
            
            # 启动scrcpy进程（不等待，不捕获输出，避免阻塞）
            process = subprocess.Popen(
                cmd,
                env=env,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            
            # 保存进程引用以便关闭时清理
            if not hasattr(self, 'scrcpy_processes'):
                self.scrcpy_processes = []
            self.scrcpy_processes.append(process)
            
            time.sleep(2)
            if process.poll() is None:
                self.root.after(0, lambda: [
                    self.status_var.set(f"Scrcpy已启动连接 {serial}"),
                    self.log(f"Scrcpy进程已启动，PID: {process.pid}")
                ])
            else:
                self.root.after(0, lambda: [
                    self.status_var.set("Scrcpy启动失败"),
                    messagebox.showerror("失败", f"Scrcpy进程启动后立即退出\n请点击\"测试默认参数\"按钮查看详细错误", parent=self.root),
                    self.log(f"Scrcpy进程启动失败，返回码: {process.returncode}")
                ])
            
        except Exception as e:
            error_msg = f"启动scrcpy失败: {str(e)}"
            self.log(error_msg)
            self.root.after(0, lambda: [
                self.status_var.set("Scrcpy启动失败"),
                messagebox.showerror("失败", error_msg, parent=self.root)
            ])

    def connect_device(self):
        ip = self.ip_entry.get().strip()
        port = self.port_entry.get().strip() or "5555"
        
        if not ip:
            messagebox.showwarning("警告", "请输入IP地址", parent=self.root)
            return
        
        ip_pattern = re.compile(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$')
        if not ip_pattern.match(ip):
            messagebox.showwarning("警告", "IP地址格式不正确", parent=self.root)
            return
        
        self.status_var.set(f"正在连接 {ip}:{port}...")
        self.root.update()
        
        threading.Thread(
            target=self._connect_device_thread, 
            args=(ip, port), 
            daemon=True
        ).start()

    def _connect_device_thread(self, ip, port):
        success, output = self.run_adb_command([ADB_PATH, "connect", f"{ip}:{port}"])
        
        def update_ui():
            if success:
                self.status_var.set(f"已连接 {ip}:{port}")
                messagebox.showinfo("成功", f"设备连接成功:\n{output}", parent=self.root)
                self.refresh_connected_devices()
                self.log(f"设备 {ip}:{port} 连接成功")
            else:
                self.status_var.set("连接失败")
                messagebox.showerror("失败", f"设备连接失败:\n{output}", parent=self.root)
                self.log(f"设备 {ip}:{port} 连接失败")
        
        self.root.after(0, update_ui)

    def connect_saved_device(self, ip, port):
        self.ip_entry.delete(0, tk.END)
        self.ip_entry.insert(0, ip)
        self.port_entry.delete(0, tk.END)
        self.port_entry.insert(0, port)
        self.connect_device()

    def get_wired_device_ip(self):
        self.status_var.set("正在获取设备IP地址...")
        self.root.update()
        threading.Thread(target=self._get_wired_ip_thread, daemon=True).start()

    def _get_wired_ip_thread(self):
        success, output = self.run_adb_command([ADB_PATH, "devices"])
        if not success:
            self.root.after(0, lambda: [
                self.status_var.set("获取IP失败"),
                messagebox.showerror("失败", "无法获取设备列表", parent=self.root)
            ])
            return
        
        lines = output.strip().split("\n")[1:]
        if not lines:
            self.root.after(0, lambda: [
                self.status_var.set("未找到有线连接设备"),
                messagebox.showinfo("提示", "未找到有线连接的设备，请先通过USB连接设备", parent=self.root)
            ])
            return
        
        device_id = lines[0].split("\t")[0]
        commands = [
            [ADB_PATH, "-s", device_id, "shell", "ip", "addr", "show", "wlan0"],
            [ADB_PATH, "-s", device_id, "shell", "ip", "addr", "show", "eth0"],
            [ADB_PATH, "-s", device_id, "shell", "ifconfig", "wlan0"],
            [ADB_PATH, "-s", device_id, "shell", "ifconfig", "eth0"]
        ]
        
        ip_pattern = re.compile(r'inet\s+(\d+\.\d+\.\d+\.\d+)')
        ip_address = None
        
        for cmd in commands:
            success, output = self.run_adb_command(cmd)
            if success and output:
                match = ip_pattern.search(output)
                if match:
                    ip_address = match.group(1)
                    break
        
        def update_ui():
            if ip_address:
                self.ip_entry.delete(0, tk.END)
                self.ip_entry.insert(0, ip_address)
                self.status_var.set(f"已获取IP地址: {ip_address}")
                self.log(f"已获取设备IP: {ip_address}")
                messagebox.showinfo("成功", f"已获取设备IP地址:\n{ip_address}", parent=self.root)
            else:
                self.status_var.set("获取IP地址失败")
                messagebox.showerror("失败", "无法获取设备IP地址，请手动输入", parent=self.root)
                self.log("获取设备IP地址失败")
        
        self.root.after(0, update_ui)

    def save_current_device(self):
        ip = self.ip_entry.get().strip()
        port = self.port_entry.get().strip() or "5555"
        
        if not ip:
            messagebox.showwarning("警告", "请输入IP地址", parent=self.root)
            return
        
        for device in self.devices:
            if device["ip"] == ip and device["port"] == port:
                messagebox.showinfo("提示", "该设备已保存", parent=self.root)
                return
        
        name = simpledialog.askstring("保存设备", "请输入设备备注名称:", parent=self.root)
        if not name:
            return
        
        for device in self.devices:
            if device["name"] == name:
                messagebox.showwarning("警告", "备注名已存在，请更换", parent=self.root)
                return
        
        self.devices.append({
            "name": name,
            "ip": ip,
            "port": port
        })
        
        if self.save_devices():
            self.refresh_device_list()
            messagebox.showinfo("成功", "设备已保存", parent=self.root)
            self.log(f"已保存设备: {name} ({ip}:{port})")

    def delete_selected_device(self):
        selected_items = self.device_tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "请先选择要删除的设备", parent=self.root)
            return
        
        item = selected_items[0]
        index = self.device_tree.index(item)
        device_name = self.devices[index]['name']
        
        if messagebox.askyesno("确认", f"确定要删除设备 '{device_name}' 吗?", parent=self.root):
            del self.devices[index]
            self.save_devices()
            self.refresh_device_list()
            self.log(f"已删除设备: {device_name}")

    def run_adb_command(self, cmd_list):
        """执行ADB命令（使用列表参数，避免shell注入和空格问题）"""
        try:
            result = subprocess.run(
                cmd_list,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            self.log(f"执行命令成功: {' '.join(cmd_list)}")
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
            self.log(f"命令执行失败: {' '.join(cmd_list)}\n错误: {stderr}")
            return False, f"命令执行失败: {stderr}"
        except Exception as e:
            self.log(f"命令执行错误: {' '.join(cmd_list)}\n错误: {str(e)}")
            return False, f"发生错误: {str(e)}"

    def start_scrcpy(self, ip, port):
        self.start_scrcpy_by_serial(f"{ip}:{port}")

    def start_scrcpy_by_serial(self, serial):
        self.status_var.set(f"正在启动scrcpy连接 {serial}...")
        self.root.update()
        threading.Thread(target=self._start_scrcpy_thread, args=(serial,), daemon=True).start()

    def scrcpy_connected_device(self):
        selected = self.connected_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要操作的设备", parent=self.root)
            return
        
        serial = self.connected_tree.item(selected[0], "values")[1]
        self.start_scrcpy_by_serial(serial)

    def save_connected_device_selected(self):
        selected = self.connected_tree.selection()
        if not selected:
            messagebox.showwarning("警告", "请先选择要保存的设备", parent=self.root)
            return
        
        serial = self.connected_tree.item(selected[0], "values")[1]
        self.save_connected_device(serial)

    def save_connected_device(self, serial):
        if ":" in serial:
            ip, port = serial.split(":", 1)
        else:
            success, output = self.run_adb_command([ADB_PATH, "-s", serial, "shell", "ip", "addr", "show", "wlan0"])
            ip_pattern = re.compile(r'inet\s+(\d+\.\d+\.\d+\.\d+)')
            match = ip_pattern.search(output) if success else None
            if match:
                ip = match.group(1)
                port = "5555"
            else:
                ip = serial
                port = "5555"
        
        for device in self.devices:
            if device["ip"] == ip and device["port"] == port:
                messagebox.showinfo("提示", "该设备已保存", parent=self.root)
                return
        
        name = simpledialog.askstring("保存设备", "请输入设备备注名称:", parent=self.root)
        if not name:
            return
        
        for device in self.devices:
            if device["name"] == name:
                messagebox.showwarning("警告", "备注名已存在，请更换", parent=self.root)
                return
        
        self.devices.append({
            "name": name,
            "ip": ip,
            "port": port
        })
        
        if self.save_devices():
            self.refresh_device_list()
            messagebox.showinfo("成功", "设备已保存", parent=self.root)
            self.log(f"已保存设备: {name} ({ip}:{port})")

    def edit_device(self, index):
        if 0 <= index < len(self.devices):
            device = self.devices[index]
            dialog = tk.Toplevel(self.root)
            dialog.title("编辑设备")
            dialog.geometry("350x180")
            dialog.resizable(False, False)
            dialog.transient(self.root)
            dialog.grab_set()
            
            ttk.Label(dialog, text="备注名称:").grid(row=0, column=0, padx=5, pady=10, sticky="w")
            name_entry = ttk.Entry(dialog, width=25)
            name_entry.grid(row=0, column=1, padx=5, pady=10)
            name_entry.insert(0, device["name"])
            
            ttk.Label(dialog, text="IP地址:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
            ip_entry = ttk.Entry(dialog, width=25)
            ip_entry.grid(row=1, column=1, padx=5, pady=5)
            ip_entry.insert(0, device["ip"])
            
            ttk.Label(dialog, text="端口:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
            port_entry = ttk.Entry(dialog, width=25)
            port_entry.grid(row=2, column=1, padx=5, pady=5)
            port_entry.insert(0, device["port"])
            
            def save_changes():
                new_name = name_entry.get().strip()
                new_ip = ip_entry.get().strip()
                new_port = port_entry.get().strip() or "5555"
                
                if not new_name or not new_ip:
                    messagebox.showwarning("警告", "备注和IP地址不能为空", parent=dialog)
                    return
                
                ip_pattern = re.compile(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$')
                if not ip_pattern.match(new_ip):
                    messagebox.showwarning("警告", "IP地址格式不正确", parent=dialog)
                    return
                
                for idx, dev in enumerate(self.devices):
                    if idx != index and dev["name"] == new_name:
                        messagebox.showwarning("警告", "备注名已存在，请更换", parent=dialog)
                        return
                
                self.devices[index] = {
                    "name": new_name,
                    "ip": new_ip,
                    "port": new_port
                }
                self.save_devices()
                self.refresh_device_list()
                dialog.destroy()
                self.log(f"已编辑设备: {new_name} ({new_ip}:{new_port})")
            
            btn_frame = ttk.Frame(dialog)
            btn_frame.grid(row=3, column=0, columnspan=2, pady=10)
            
            ttk.Button(btn_frame, text="保存", command=save_changes).pack(side="left", padx=10)
            ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side="left", padx=10)
            
            dialog.update_idletasks()
            width = dialog.winfo_width()
            height = dialog.winfo_height()
            x = (self.root.winfo_width() // 2) - (width // 2) + self.root.winfo_x()
            y = (self.root.winfo_height() // 2) - (height // 2) + self.root.winfo_y()
            dialog.geometry(f"+{x}+{y}")

    def disconnect_device(self, serial=None):
        if not serial:
            selected_items = self.connected_tree.selection()
            if not selected_items:
                messagebox.showwarning("警告", "请先选择要断开的设备", parent=self.root)
                return
            item = selected_items[0]
            serial = self.connected_tree.item(item, "values")[1]
        
        self.status_var.set(f"正在断开 {serial} 的连接...")
        self.root.update()
        threading.Thread(target=self._disconnect_thread, args=(serial,), daemon=True).start()

    def _disconnect_thread(self, serial):
        success, output = self.run_adb_command([ADB_PATH, "disconnect", serial])
        
        def update_ui():
            if success:
                self.status_var.set(f"已断开 {serial} 的连接")
                self.log(f"已断开 {serial} 的连接")
            else:
                self.status_var.set(f"断开 {serial} 连接失败")
                self.log(f"断开 {serial} 连接失败: {output}")
            self.refresh_connected_devices()
        
        self.root.after(0, update_ui)

if __name__ == "__main__":
    root = tk.Tk()
    app = ADBManager(root)
    root.mainloop()