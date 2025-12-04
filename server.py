import os
import sys
import ctypes
import threading
import subprocess
import tkinter as tk
from tkinter import scrolledtext, messagebox
import webbrowser
import time
import queue
import platform
import psutil
import json
import atexit
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
        master.geometry("700x650") # 增加高度以容纳新功能
        master.configure(bg="#f7f7f7")
        self.is_running = False
        self.server_thread = None
        self.log_queue = Logger.get_queue()
        self.port = tk.IntVar(value=5000)
        self.tray_icon = None
        self.soda_monitor_thread = None
        self.soda_monitor_running = False
        
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
        
        # 远程访问控制区域
        remote_frame = tk.LabelFrame(master, text="远程访问 (公网穿透)", bg="#f7f7f7", pady=5)
        remote_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 移除了 Ngrok Token 配置区域，改用 Cloudflare Tunnel (无需配置)
        
        ctrl_frame = tk.Frame(remote_frame, bg="#f7f7f7")
        ctrl_frame.pack(fill=tk.X, padx=5, pady=5)
        self.remote_btn = tk.Button(ctrl_frame, text="开启远程访问", command=self.toggle_remote_access, bg="#673AB7", fg="white", width=14)
        self.remote_btn.pack(side=tk.LEFT)
        tk.Label(ctrl_frame, text="公网地址:", bg="#f7f7f7").pack(side=tk.LEFT, padx=(10,0))
        self.url_entry = tk.Entry(ctrl_frame, textvariable=self.remote_url, width=35, state='readonly')
        self.url_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(ctrl_frame, text="复制", command=lambda: self.master.clipboard_clear() or self.master.clipboard_append(self.remote_url.get()), height=1).pack(side=tk.LEFT)

        # 邮件通知配置
        mail_frame = tk.Frame(remote_frame, bg="#f7f7f7")
        mail_frame.pack(fill=tk.X, padx=5, pady=2)
        tk.Checkbutton(mail_frame, text="启用邮件通知", variable=self.email_notify_enabled, bg="#f7f7f7", command=self.save_config).pack(side=tk.LEFT)
        tk.Label(mail_frame, text="接收邮箱(逗号分隔):", bg="#f7f7f7").pack(side=tk.LEFT, padx=(10,5))
        tk.Entry(mail_frame, textvariable=self.recv_email, width=40).pack(side=tk.LEFT)
        tk.Button(mail_frame, text="保存", command=self.save_config, height=1).pack(side=tk.LEFT, padx=5)

        # 二维码区域
        self.qr_label = tk.Label(remote_frame, bg="#f7f7f7")
        self.qr_label.pack(pady=5)

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
                    time.sleep(1)

                    self.log("[远程] 正在启动 Cloudflare Tunnel...", "info")
                    
                    url = self.cloudflared.start(self.port.get())
                    
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
                                mailer.send_link_notification(self.recv_email.get(), url, qr_path)

                        threading.Thread(target=send_mail_after_qr, daemon=True).start()
                            
                    else:
                        self.log("[远程] 开启失败: 无法获取URL", "error")
                    
                except Exception as e:
                    err = str(e)
                    self.log(f"[远程] 开启失败: {err}", "error")

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
    ui = ServerUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
