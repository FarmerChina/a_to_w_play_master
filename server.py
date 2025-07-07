import os
import sys
import ctypes
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox
import webbrowser
import time
import queue
import platform
import psutil
try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None
from music_server.web import app
from music_server.utils import get_local_ip
from music_server.logger import Logger

LOCAL_IP = get_local_ip()

class ServerUI:
    def __init__(self, master):
        self.master = master
        master.title("汽水音乐控制台")
        master.geometry("700x480")
        master.configure(bg="#f7f7f7")
        self.is_running = False
        self.server_thread = None
        self.log_queue = Logger.get_queue()
        self.port = tk.IntVar(value=5000)
        self.tray_icon = None
        self.soda_monitor_thread = None
        self.soda_monitor_running = False
        self._build_ui(master)
        self._poll_log()
        self._start_soda_monitor()
        # 启动时创建托盘图标
        self._init_tray_icon()
        # 启动后自动最小化到托盘
        self.master.after(100, self.minimize_to_tray)
        # 绑定关闭按钮为最小化到托盘
        self.master.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

    def _init_tray_icon(self):
        if not pystray:
            return
        image = self._create_tray_icon()
        def on_tray_click(icon, item=None):
            # 切换窗口显示/隐藏
            def toggle_window():
                if self.master.state() == 'withdrawn':
                    self._show_and_raise_window()
                else:
                    self.master.withdraw()
            self.master.after(0, toggle_window)
        if self.tray_icon:
            try:
                self.master.after(0, self.tray_icon.stop)
            except Exception:
                pass
        self.tray_icon = pystray.Icon(
            "AtoWMusicServer",
            image,
            "AtoW Music Server",
            menu=pystray.Menu(
                pystray.MenuItem("显示主界面", lambda icon, item: self.master.after(0, self._show_and_raise_window)),
                pystray.MenuItem("退出", lambda icon, item: self.master.after(0, self.quit))
            ),
            on_activate=on_tray_click
        )
        self.tray_icon.run_detached()

    def _show_and_raise_window(self):
        self.master.deiconify()
        self.master.lift()
        self.master.focus_force()

    def _build_ui(self, master):
        top_frame = tk.Frame(master, bg="#f7f7f7")
        top_frame.pack(fill=tk.X, pady=5)
        tk.Label(top_frame, text="服务状态:", bg="#f7f7f7").pack(side=tk.LEFT, padx=(10,0))
        self.status_label = tk.Label(top_frame, text="未启动", fg="red", bg="#f7f7f7", font=("微软雅黑", 11, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=5)
        tk.Label(top_frame, text="端口:", bg="#f7f7f7").pack(side=tk.LEFT, padx=(30,0))
        self.port_entry = tk.Entry(top_frame, textvariable=self.port, width=6, font=("Consolas", 11))
        self.port_entry.pack(side=tk.LEFT)
        self.open_btn = tk.Button(top_frame, text="打开Web控制台", command=self.open_browser, bg="#2196F3", fg="white")
        self.open_btn.pack(side=tk.RIGHT, padx=10)
        self.open_btn.config(state=tk.DISABLED)

        self.log_area = scrolledtext.ScrolledText(master, state='disabled', height=20, font=("Consolas", 10))
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        btn_frame = tk.Frame(master, bg="#f7f7f7")
        btn_frame.pack(fill=tk.X, pady=8)
        self.start_btn = tk.Button(btn_frame, text="启动服务", command=self.start_server, bg="#4CAF50", fg="white", width=12, font=("微软雅黑", 11, "bold"))
        self.start_btn.pack(side=tk.LEFT, padx=20)
        self.stop_btn = tk.Button(btn_frame, text="停止服务", command=self.stop_server, state=tk.DISABLED, bg="#F44336", fg="white", width=12, font=("微软雅黑", 11, "bold"))
        self.stop_btn.pack(side=tk.LEFT, padx=20)
        self.quit_btn = tk.Button(btn_frame, text="退出", command=self.quit, width=8)
        self.quit_btn.pack(side=tk.RIGHT, padx=20)
        self.min_btn = tk.Button(btn_frame, text="最小化到托盘", command=self.minimize_to_tray, width=14)
        self.min_btn.pack(side=tk.RIGHT, padx=10)
 
    def log(self, msg, level="info"):
        # 只保留关键日志，过滤掉频繁的监控和状态日志
        if any(x in msg for x in ["服务启动中", "服务已停止", "Flask服务已启动", "Flask服务关闭异常", "Flask服务启动失败", "检测到汽水音乐已启动", "汽水音乐已退出"]):
            self.log_queue.put((msg, level))
        # 其它日志不再写入，防止内存溢出

    def _poll_log(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                if isinstance(item, tuple):
                    if len(item) == 2:
                        msg, level = item
                    elif len(item) == 1:
                        msg, level = item[0], "info"
                    else:
                        msg, level = str(item), "info"
                else:
                    msg, level = str(item), "info"
                self.log_area.config(state='normal')
                tag = level
                color = {"info":"#333","warn":"#e67e22","error":"#e53935"}.get(level, "#333")
                self.log_area.tag_config(tag, foreground=color)
                self.log_area.insert(tk.END, msg + '\n', tag)
                self.log_area.see(tk.END)
                self.log_area.config(state='disabled')
        except queue.Empty:
            pass
        self.master.after(200, self._poll_log)

    def start_server(self):
        if self.is_running:
            return
        port = self.port.get()
        if not (1024 <= port <= 65535):
            messagebox.showerror("端口错误", "端口号必须在1024-65535之间！")
            return
        self.is_running = True
        self.status_label.config(text=f"运行中 (http://{LOCAL_IP}:{port})", fg="#388e3c")
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.open_btn.config(state=tk.NORMAL)
        self.log(f"[INFO] 服务启动中，端口:{port} ...")
        def flask_thread():
            import logging
            from werkzeug.serving import make_server
            class FlaskServerThread(threading.Thread):
                def __init__(self, app, log_callback):
                    super().__init__()
                    self.srv = make_server('0.0.0.0', port, app)
                    self.ctx = app.app_context()
                    self.ctx.push()
                    self.log_callback = log_callback
                def run(self):
                    self.log_callback(f'[INFO] Flask服务已启动，端口:{port}，等待控制端连接...')
                    self.srv.serve_forever()
                def shutdown(self):
                    self.srv.shutdown()
            self.flask_server = FlaskServerThread(app, self.log)
            self.flask_server.start()
        self.flask_server = None
        self.server_thread = threading.Thread(target=flask_thread, daemon=True)
        self.server_thread.start()

    def stop_server(self):
        if not self.is_running:
            return
        self.is_running = False
        self.status_label.config(text="服务已停止", fg="red")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.open_btn.config(state=tk.DISABLED)
        self.log("[INFO] 服务已停止。请关闭窗口退出进程。", "warn")
        # 优雅关闭 Flask 服务，不退出主程序
        if hasattr(self, 'flask_server') and self.flask_server:
            try:
                self.flask_server.shutdown()
            except Exception as e:
                self.log(f"[ERROR] Flask服务关闭异常: {e}", "error")
        self.flask_server = None

    def open_browser(self):
        port = self.port.get()
        webbrowser.open(f"http://{LOCAL_IP}:{port}")

    def minimize_to_tray(self):
        if not pystray:
            messagebox.showinfo("提示", "未安装pystray和Pillow，无法最小化到托盘。\n可用pip安装: pip install pystray pillow")
            return
        self.master.withdraw()

    def _show_window(self, icon=None, item=None):
        self.master.after(0, self.master.deiconify)

    def _create_tray_icon(self):
        # 生成32x32音乐符号图标
        img = Image.new('RGBA', (32, 32), (255, 255, 255, 0))
        d = ImageDraw.Draw(img)
        # 蓝色圆形
        d.ellipse((2, 2, 30, 30), fill="#2196F3", outline="#1976D2", width=2)
        # 白色音符
        d.line((12, 10, 12, 22), fill="#fff", width=3)
        d.ellipse((10, 20, 16, 26), fill="#fff", outline="#fff")
        d.line((12, 10, 22, 14), fill="#fff", width=3)
        d.ellipse((20, 12, 26, 18), fill="#fff", outline="#fff")
        return img

    def _start_soda_monitor(self):
        """启动汽水音乐监控线程"""
        self.soda_monitor_running = True
        self.soda_monitor_thread = threading.Thread(
            target=self._monitor_soda_music, 
            daemon=True
        )
        self.soda_monitor_thread.start()
        self.log("[监控] 启动汽水音乐状态监控...", "info")

    def _stop_soda_monitor(self):
        """停止监控线程"""
        self.soda_monitor_running = False
        if self.soda_monitor_thread and self.soda_monitor_thread.is_alive():
            self.soda_monitor_thread.join(timeout=1.0)

    def _monitor_soda_music(self):
        """监控汽水音乐运行状态并自动启停服务（资源优化版）"""
        
        last_state = None
        
        while self.soda_monitor_running:
            # 轻量级检查：通过进程名判断
            soda_running = any(p.name() == "SodaMusic.exe" for p in psutil.process_iter(['name']))
            
            # 状态变化处理
            if soda_running and last_state != soda_running:
                if not self.is_running:
                    self.log("[监控] 检测到汽水音乐已启动，正在自动启动服务...", "info")
                    self.master.after(0, self.start_server)
            
            if not soda_running and last_state != soda_running:
                if self.is_running:
                    self.log("[监控] 汽水音乐已退出，正在自动停止服务...", "info")
                    self.master.after(0, self.stop_server)
            
            last_state = soda_running
            time.sleep(10)  # 每10秒检查一次，减少资源占用

    def quit(self, *args):
        self._stop_soda_monitor()  # 停止监控线程
        if self.tray_icon:
            try:
                self.master.after(0, self.tray_icon.stop)
            except Exception:
                pass
        self.master.after(0, self.master.destroy)

class LogToTk:
    def __init__(self, ui):
        self.ui = ui
    def write(self, msg):
        if msg.strip():
            self.ui.log(msg.strip())
    def flush(self):
        pass

def main():
    root = tk.Tk()
    ui = ServerUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
