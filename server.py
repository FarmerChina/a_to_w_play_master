import os
import sys
import ctypes
import threading
import subprocess
import tkinter as tk
from tkinter import scrolledtext, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import webbrowser
import time
import queue
import platform
import psutil
import json
import atexit
import winreg
try:
    import pystray
    from PIL import Image, ImageDraw, ImageTk
    import qrcode
except ImportError:
    pystray = None
    qrcode = None

from music_server.web import app
from music_server.utils import get_local_ip
from music_server.logger import Logger
from music_server.cloudflared import Cloudflared
from music_server.mailer import Mailer

LOCAL_IP = get_local_ip()
CONFIG_FILE = "config.json"

class ServerUI:
    def __init__(self, master):
        self.master = master
        master.title("汽水音乐控制台")
        master.geometry("750x800")
        
        # 应用扁平化主题
        self.style = ttk.Style("cosmo")
        
        self.is_running = False
        self.server_thread = None
        self.log_queue = Logger.get_queue()
        self.port = tk.IntVar(value=5000)
        self.tray_icon = None
        self.soda_monitor_thread = None
        self.soda_monitor_running = False
        self.health_check_thread = None
        self.health_check_running = False
        self.restart_attempt_count = 0
        
        # 开机自启状态
        self.autostart_enabled = tk.BooleanVar(value=False)
        
        # 远程访问相关变量
        self.remote_tunnel = None
        self.cloudflared = Cloudflared()
        self.remote_url = tk.StringVar(value="未开启")
        self.qr_image = None
        self.qr_image_data = None # 新增：用于存储二维码PIL对象
        
        # 邮件通知相关
        self.email_notify_enabled = tk.BooleanVar(value=True)
        self.recv_email = tk.StringVar(value="ngt@huinong.co")
        # 发送配置 (使用腾讯企业邮箱)
        self.smtp_server = "smtp.exmail.qq.com"
        self.smtp_port = 465
        self.sender_email = "ngt@huinong.co"
        self.sender_password = "MiNR6qWE83AFWn3K"
        
        self.load_config()
        self._check_autostart_status()
        
        # 注册退出清理函数
        atexit.register(self.cleanup_resources)

        self._build_ui(master)
        self._poll_log()
        self._start_soda_monitor()
        # 启动时创建托盘图标
        self._init_tray_icon()
        
        # 自动启动逻辑
        self.log("[系统] 正在初始化服务...", "info")
        self.master.after(1000, self.start_server) # 延迟1秒启动本地服务
        self.master.after(3000, self.toggle_remote_access) # 延迟3秒启动远程服务
        
        # 启动后自动最小化到托盘
        self.master.after(5000, self.minimize_to_tray)
        # 绑定关闭按钮为最小化到托盘
        self.master.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    # 读取邮件配置
                    self.email_notify_enabled.set(data.get('email_notify_enabled', True))
                    self.recv_email.set(data.get('recv_email', 'ngt@huinong.co'))
            except Exception:
                pass

    def save_config(self):
        try:
            data = {}
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
            
            data['email_notify_enabled'] = self.email_notify_enabled.get()
            data['recv_email'] = self.recv_email.get()
            
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass

    def _check_autostart_status(self):
        """检查注册表中是否已开启开机自启"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
            try:
                winreg.QueryValueEx(key, "AtoWMusicServer")
                self.autostart_enabled.set(True)
            except FileNotFoundError:
                self.autostart_enabled.set(False)
            finally:
                winreg.CloseKey(key)
        except Exception as e:
            self.log(f"[系统] 检查自启状态失败: {e}", "warn")

    def _toggle_autostart(self):
        """切换开机自启状态"""
        exe_path = os.path.abspath(sys.argv[0])
        app_name = "AtoWMusicServer"
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
            if self.autostart_enabled.get():
                # 开启自启
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
                self.log("[系统] 已开启开机自启动", "info")
            else:
                # 关闭自启
                try:
                    winreg.DeleteValue(key, app_name)
                    self.log("[系统] 已关闭开机自启动", "info")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            self.log(f"[系统] 设置自启动失败: {e}", "error")
            # 回滚UI状态
            self.autostart_enabled.set(not self.autostart_enabled.get())

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
        # 主容器
        main_container = ttk.Frame(master, padding=20)
        main_container.pack(fill=BOTH, expand=YES)
        
        # 1. 顶部状态栏
        status_frame = ttk.Labelframe(main_container, text="服务状态", padding=15, bootstyle="info")
        status_frame.pack(fill=X, pady=(0, 15))
        
        # 状态指示灯和文本
        status_inner = ttk.Frame(status_frame)
        status_inner.pack(fill=X)
        
        self.status_label = ttk.Label(status_inner, text="● 未启动", font=("微软雅黑", 12, "bold"), bootstyle="danger")
        self.status_label.pack(side=LEFT, padx=(5, 20))
        
        # 端口输入
        ttk.Label(status_inner, text="端口:").pack(side=LEFT)
        self.port_entry = ttk.Entry(status_inner, textvariable=self.port, width=8, font=("Consolas", 10))
        self.port_entry.pack(side=LEFT, padx=5)
        
        # 打开浏览器按钮
        self.open_btn = ttk.Button(status_inner, text="打开 Web 控制台", command=self.open_browser, bootstyle="outline-primary", state=DISABLED)
        self.open_btn.pack(side=RIGHT)

        # 2. 控制按钮区域
        btn_frame = ttk.Frame(main_container)
        btn_frame.pack(fill=X, pady=(0, 15))
        
        self.start_btn = ttk.Button(btn_frame, text="启动服务", command=self.start_server, bootstyle="success", width=15)
        self.start_btn.pack(side=LEFT, padx=(0, 10))
        
        self.stop_btn = ttk.Button(btn_frame, text="停止服务", command=self.stop_server, state=DISABLED, bootstyle="danger", width=15)
        self.stop_btn.pack(side=LEFT, padx=(0, 10))
        
        # 开机自启开关
        self.autostart_chk = ttk.Checkbutton(btn_frame, text="开机自启", variable=self.autostart_enabled, command=self._toggle_autostart, bootstyle="round-toggle")
        self.autostart_chk.pack(side=LEFT, padx=20)

        self.min_btn = ttk.Button(btn_frame, text="最小化", command=self.minimize_to_tray, bootstyle="secondary-outline", width=10)
        self.min_btn.pack(side=RIGHT, padx=(10, 0))
        
        self.quit_btn = ttk.Button(btn_frame, text="退出", command=self.quit, bootstyle="secondary-outline", width=10)
        self.quit_btn.pack(side=RIGHT)

        # 3. 日志区域
        log_frame = ttk.Labelframe(main_container, text="运行日志", padding=10)
        log_frame.pack(fill=BOTH, expand=YES, pady=(0, 15))
        
        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', height=10, font=("Consolas", 9), relief="flat")
        self.log_area.pack(fill=BOTH, expand=YES)
        
        # 4. 远程访问与高级功能
        remote_frame = ttk.Labelframe(main_container, text="远程访问 & 通知", padding=15, bootstyle="primary")
        remote_frame.pack(fill=X)
        
        # 远程开关行
        remote_ctrl_row = ttk.Frame(remote_frame)
        remote_ctrl_row.pack(fill=X, pady=(0, 10))
        
        self.remote_btn = ttk.Button(remote_ctrl_row, text="开启远程访问", command=self.toggle_remote_access, bootstyle="info", width=15)
        self.remote_btn.pack(side=LEFT, padx=(0, 10))
        
        ttk.Label(remote_ctrl_row, text="公网地址:").pack(side=LEFT)
        self.url_entry = ttk.Entry(remote_ctrl_row, textvariable=self.remote_url, state='readonly')
        self.url_entry.pack(side=LEFT, fill=X, expand=YES, padx=5)
        
        ttk.Button(remote_ctrl_row, text="复制", command=lambda: self.master.clipboard_clear() or self.master.clipboard_append(self.remote_url.get()), bootstyle="outline-secondary").pack(side=LEFT)
        
        # 邮件设置行
        mail_row = ttk.Frame(remote_frame)
        mail_row.pack(fill=X, pady=(0, 10))
        
        ttk.Checkbutton(mail_row, text="启用邮件通知", variable=self.email_notify_enabled, command=self.save_config, bootstyle="square-toggle").pack(side=LEFT, padx=(0, 10))
        ttk.Label(mail_row, text="接收邮箱:").pack(side=LEFT)
        ttk.Entry(mail_row, textvariable=self.recv_email, width=30).pack(side=LEFT, padx=5)
        ttk.Button(mail_row, text="保存配置", command=self.save_config, bootstyle="outline-success", width=10).pack(side=LEFT)

        # 二维码显示区
        self.qr_frame = ttk.Frame(remote_frame)
        self.qr_frame.pack(fill=BOTH, expand=YES)
        
        self.qr_label = ttk.Label(self.qr_frame)
        self.qr_label.pack(pady=5)
        
        self.loading_label = ttk.Label(self.qr_frame, text="正在启动远程服务...", font=("微软雅黑", 10), bootstyle="info")
        self.loading_spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.loading_idx = 0
        self.is_loading = False

    def _start_loading_animation(self, text="正在启动..."):
        self.is_loading = True
        self.qr_label.pack_forget() # 隐藏二维码
        self.loading_label.config(text=text)
        self.loading_label.pack(pady=20)
        self._animate_loading()

    def _stop_loading_animation(self):
        self.is_loading = False
        self.loading_label.pack_forget()
        self.qr_label.pack(pady=5) # 恢复二维码显示位置

    def _animate_loading(self):
        if self.is_loading:
            char = self.loading_spinner_chars[self.loading_idx % len(self.loading_spinner_chars)]
            current_text = self.loading_label.cget("text").split(' ')[-1] # 获取除图标外的文本
            self.loading_label.config(text=f"{char} {current_text}")
            self.loading_idx += 1
            self.master.after(100, self._animate_loading)

    def cleanup_tunnels(self):
        """清理残留的隧道进程"""
        if self.cloudflared:
            self.cloudflared.stop()
            
        # 尝试清理残留的 cloudflared 进程
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and 'cloudflared' in proc.info['name'].lower():
                     self.log(f"[系统] 发现残留隧道进程 (PID: {proc.info['pid']})，正在清理...", "warn")
                     proc.kill()
        except Exception:
            pass

    def toggle_remote_access(self):
        if self.remote_tunnel:
            # 关闭远程访问
            if self.cloudflared:
                self.cloudflared.stop()
            
            self.remote_tunnel = None
            self.remote_url.set("未开启")
            self.remote_btn.config(text="开启远程访问", bg="#673AB7")
            self.qr_label.config(image='', text='')
            self.log("[远程] 远程访问已关闭", "info")
        else:
            # 开启远程访问
            if not self.is_running:
                messagebox.showwarning("提示", "请先启动本地服务！")
                return
                
            def connect_thread():
                try:
                    # 开启前先清理
                    self.cleanup_tunnels()
                    
                    # 显示加载动画
                    self.master.after(0, lambda: self._start_loading_animation("正在启动 Cloudflare Tunnel (首次运行可能需要下载)..."))
                    
                    time.sleep(1)

                    self.log("[远程] 正在启动 Cloudflare Tunnel...", "info")
                    
                    url = self.cloudflared.start(self.port.get())
                    
                    # 停止加载动画
                    self.master.after(0, self._stop_loading_animation)
                    
                    if url:
                        self.remote_tunnel = True # Just a flag now
                        self.remote_url.set(url)
                        self.log(f"[远程] 远程访问开启成功: {url}", "info")
                        
                        # 更新UI
                        self.master.after(0, lambda: self.remote_btn.config(text="关闭远程访问", bg="#9E9E9E"))
                        self.master.after(0, lambda: self._show_qr_code(url))
                        
                        # 确保二维码生成后再发送邮件
                        def send_mail_after_qr():
                            # 等待一小会儿确保 self.qr_image_data 已生成
                            time.sleep(0.5) 
                            if self.email_notify_enabled.get() and self.recv_email.get():
                                self.log(f"[邮件] 正在发送新地址到 {self.recv_email.get()}...", "info")
                                
                                # 临时保存二维码图片以便发送
                                qr_path = None
                                if self.qr_image_data:
                                    try:
                                        import tempfile
                                        temp_dir = tempfile.gettempdir()
                                        qr_path = os.path.join(temp_dir, 'atow_qrcode.png')
                                        self.qr_image_data.save(qr_path)
                                    except Exception as e:
                                        self.log(f"[邮件] 保存二维码失败: {e}", "warn")
                                
                                mailer = Mailer(self.smtp_server, self.smtp_port, self.sender_email, self.sender_password)
                                success = mailer.send_link_notification(self.recv_email.get(), url, qr_path)
                                if success:
                                    self.log(f"[邮件] 邮件发送成功", "info")
                                else:
                                    self.log(f"[邮件] 邮件发送失败，请检查配置", "error")
 
                        threading.Thread(target=send_mail_after_qr, daemon=True).start()
                            
                    else:
                        self.log("[远程] 开启失败: 无法获取URL", "error")
                        self.master.after(0, self._stop_loading_animation)
                    
                except Exception as e:
                    err = str(e)
                    self.log(f"[远程] 开启失败: {err}", "error")
                    self.master.after(0, self._stop_loading_animation)

            threading.Thread(target=connect_thread, daemon=True).start()

    def _show_qr_code(self, data):
        if not qrcode:
            return
        qr = qrcode.QRCode(box_size=4, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        self.qr_image_data = img # 保存原始PIL图像对象用于邮件发送
        self.qr_image = ImageTk.PhotoImage(img)
        self.qr_label.config(image=self.qr_image)

    def log(self, msg, level="info"):
        print(f"[{level.upper()}] {msg}")
        # 只保留关键日志，过滤掉频繁的监控和状态日志
        if any(x in msg for x in ["服务启动中", "服务已停止", "Flask服务已启动", "Flask服务关闭异常", "Flask服务启动失败", "检测到汽水音乐已启动", "汽水音乐已退出", "邮件发送成功", "邮件发送失败"]):
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

    def is_port_in_use(self, port):
        """
        检查端口是否被其他进程占用。
        如果端口被当前进程占用，则视为未被占用。
        """
        import socket
        
        # 1. 尝试绑定端口，如果成功则说明未被占用
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                return False # 绑定成功，说明端口空闲
            except OSError:
                pass # 绑定失败，说明端口可能被占用

        # 2. 如果绑定失败，进一步检查是否是当前进程占用的
        try:
            current_pid = os.getpid()
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    for conn in proc.connections():
                        if conn.laddr.port == port:
                            if proc.info['pid'] == current_pid:
                                return False # 是当前进程占用的，视为未被占用
                            else:
                                return True # 是其他进程占用的
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass
            
        return True # 默认视为被占用

    def _on_server_started(self, port):
        self.is_running = True
        self.status_label.config(text=f"● 运行中 (http://{LOCAL_IP}:{port})", bootstyle="success")
        self.start_btn.config(state=DISABLED)
        self.stop_btn.config(state=NORMAL)
        self.open_btn.config(state=NORMAL)
        self.restart_attempt_count = 0 # 重置重启计数
        
        # 启动健康检查
        if not self.health_check_running:
            self.health_check_running = True
            self.health_check_thread = threading.Thread(target=self._monitor_service_health, daemon=True)
            self.health_check_thread.start()

    def _monitor_service_health(self):
        """服务健康检查线程"""
        import urllib.request
        failure_count = 0
        
        while self.health_check_running:
            if self.is_running:
                port = self.port.get()
                url = f"http://127.0.0.1:{port}/api/health"
                try:
                    with urllib.request.urlopen(url, timeout=3) as response:
                        if response.getcode() == 200:
                            failure_count = 0 # 重置失败计数
                except Exception as e:
                    failure_count += 1
                    self.log(f"[监控] 健康检查失败 ({failure_count}/3): {e}", "warn")
                
                if failure_count >= 3:
                    self.log("[监控] 服务响应异常，正在尝试自动修复...", "error")
                    self._trigger_auto_restart()
                    failure_count = 0 # 重置以免重复触发
                    time.sleep(10) # 冷却时间
            
            time.sleep(10) # 每10秒检查一次

    def _trigger_auto_restart(self):
        """触发自动重启流程"""
        if self.restart_attempt_count >= 3:
             self.log("[监控] 自动修复失败次数过多，请检查端口占用或手动重启", "error")
             return

        self.restart_attempt_count += 1
        self.log(f"[系统] 正在执行第 {self.restart_attempt_count} 次自动重启...", "warn")
        
        # 1. 尝试停止服务
        self.master.after(0, self.stop_server)
        
        # 2. 尝试强制清理端口占用 (如果停止失败)
        time.sleep(2)
        port = self.port.get()
        self._kill_process_on_port(port)
        
        # 3. 重新启动
        time.sleep(2)
        self.master.after(0, self.start_server)

    def _kill_process_on_port(self, port):
        """尝试杀掉占用指定端口的进程"""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    for conn in proc.connections():
                        if conn.laddr.port == port:
                             self.log(f"[系统] 发现占用端口 {port} 的进程 {proc.info['name']} (PID: {proc.info['pid']})，正在清理...", "warn")
                             proc.kill()
                             return
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            self.log(f"[系统] 清理端口占用失败: {e}", "warn")

    def _on_server_start_failed(self, error_msg):
        self.is_running = False
        self.status_label.config(text="● 启动失败", bootstyle="danger")
        self.start_btn.config(state=NORMAL)
        self.stop_btn.config(state=DISABLED)
        self.open_btn.config(state=DISABLED)
        messagebox.showerror("启动失败", f"服务启动失败: {error_msg}\n请尝试更换端口或检查是否有其他程序占用。")

    def start_server(self):
        if self.is_running:
            return
        port = self.port.get()
        if not (1024 <= port <= 65535):
            messagebox.showerror("端口错误", "端口号必须在1024-65535之间！")
            return
            
        # 预检查端口
        if self.is_port_in_use(port):
             messagebox.showerror("启动失败", f"端口 {port} 已被占用，请更换端口！")
             return

        self.start_btn.config(state=tk.DISABLED)
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
            
            try:
                self.flask_server = FlaskServerThread(app, self.log)
                self.flask_server.start()
                # 成功启动，回调 UI
                self.master.after(0, lambda: self._on_server_started(port))
            except Exception as e:
                # 启动失败，回调 UI
                err = str(e)
                self.log(f"[ERROR] Flask服务启动异常: {err}", "error")
                self.master.after(0, lambda: self._on_server_start_failed(err))

        self.flask_server = None
        self.server_thread = threading.Thread(target=flask_thread, daemon=True)
        self.server_thread.start()

    def stop_server(self):
        if not self.is_running:
            return
        self.is_running = False
        self.status_label.config(text="● 已停止", bootstyle="secondary")

        self.start_btn.config(state=NORMAL)
        self.stop_btn.config(state=DISABLED)
        self.open_btn.config(state=DISABLED)
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

    def _save_soda_path_if_needed(self, path):
        """保存汽水音乐路径到配置文件"""
        try:
            current_config = {}
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    current_config = json.load(f)
            
            saved_path = current_config.get('soda_music_path')
            # 如果路径不同，或者是新路径，则保存
            if saved_path != path and os.path.exists(path):
                current_config['soda_music_path'] = path
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(current_config, f)
                self.log(f"[配置] 已自动捕获并保存汽水音乐路径: {path}", "info")
        except Exception as e:
            pass

    def _monitor_soda_music(self):
        """监控汽水音乐运行状态并自动启动服务（资源优化版）
           注意：汽水音乐退出时不再自动停止服务，以保持服务在线
        """
        
        last_state = None
        
        while self.soda_monitor_running:
            soda_running = False
            soda_path = None
            
            try:
                for p in psutil.process_iter(['name']):
                    if p.info['name'] == "SodaMusic.exe":
                        soda_running = True
                        # 尝试获取路径
                        try:
                            soda_path = p.exe()
                        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                            pass
                        break
            except Exception:
                pass

            # 如果检测到路径，尝试保存
            if soda_path:
                 self._save_soda_path_if_needed(soda_path)
            
            # 状态变化处理
            if soda_running and last_state != soda_running:
                if not self.is_running:
                    self.log("[监控] 检测到汽水音乐已启动，正在自动启动服务...", "info")
                    self.master.after(0, self.start_server)
            
            if not soda_running and last_state != soda_running:
                if self.is_running:
                    self.log("[监控] 汽水音乐已退出，服务保持运行等待唤醒...", "info")
                    # self.master.after(0, self.stop_server) # 取消自动停止
            
            last_state = soda_running
            time.sleep(5)  # 缩短检查间隔到5秒

    def cleanup_resources(self):
        """清理资源，确保隧道进程关闭"""
        if self.cloudflared:
            try:
                self.cloudflared.stop()
                print("[INFO] Cloudflared进程已清理")
            except:
                pass
        if self.remote_tunnel:
             # Reset flag
             self.remote_tunnel = None

    def quit(self, *args):
        self._stop_soda_monitor()  # 停止监控线程
        self.health_check_running = False # 停止健康检查
        self.cleanup_resources()
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
    # 隐藏主窗口，直到构建完成
    root.withdraw()
    ui = ServerUI(root)
    # 构建完成后显示
    root.deiconify()
    root.mainloop()

if __name__ == '__main__':
    main()
