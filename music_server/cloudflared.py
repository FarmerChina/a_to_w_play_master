import os
import sys
import subprocess
import time
import threading
import re
import shutil
from collections import deque
from urllib import request
from .logger import Logger

class Cloudflared:
    def __init__(self):
        self.process = None
        self.url = None
        # Determine binary name
        self.bin_name = "cloudflared.exe" if os.name == 'nt' else "cloudflared"
        
        # Determine base directory for storing binary
        if getattr(sys, 'frozen', False):
            # Running as compiled exe
            # First check if bundled in _MEIPASS (where PyInstaller unpacks datas)
            if hasattr(sys, '_MEIPASS'):
                bundled_path = os.path.join(sys._MEIPASS, self.bin_name)
                if os.path.exists(bundled_path):
                    self.bin_path = bundled_path
                    return

            # If not found in bundle, use exe dir (so it can be downloaded there)
            base_dir = os.path.dirname(sys.executable)
        else:
            # Running as script, use current working directory
            base_dir = os.getcwd()
            
        self.bin_path = os.path.join(base_dir, self.bin_name)
        
    def check_installed(self):
        return os.path.exists(self.bin_path)
        
    def download(self):
        """Download cloudflared binary"""
        url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        if os.name != 'nt':
            # Fallback for linux/mac (simplified, assuming linux amd64 for now)
            url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
            
        Logger.info(f"正在下载 Cloudflared 组件: {url}")
        try:
            # Download with progress indication is hard with simple urlopen without blocking UI log too much
            # Just simple download
            with request.urlopen(url) as response, open(self.bin_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
                
            if os.name != 'nt':
                os.chmod(self.bin_path, 0o755)
                
            Logger.info("Cloudflared 组件下载完成")
            return True
        except Exception as e:
            Logger.error(f"Cloudflared 下载失败: {e}")
            return False

    def start(self, port):
        """Start the tunnel and return the public URL"""
        if self.process:
            if self.process.poll() is None:
                return self.url
            else:
                # Process died
                self.process = None
                self.url = None
            
        if not self.check_installed():
            if not self.download():
                raise Exception("无法下载 Cloudflared 组件")

        cmd = [
            self.bin_path,
            "tunnel",
            "--url",
            f"http://127.0.0.1:{port}",
            "--no-autoupdate",
            "--loglevel",
            "info",
        ]
        
        # Hide window on Windows
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        try:
            Logger.info("正在启动 Cloudflare Tunnel...")
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                startupinfo=startupinfo,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            output_tail = deque(maxlen=200)
            self.url = None
            
            def read_stream():
                """Thread to read output and find the URL"""
                while self.process and self.process.poll() is None:
                    try:
                        line = self.process.stdout.readline()
                        if not line:
                            break
                        output_tail.append(line)
                        # Check for URL pattern
                        # Example: https://cool-name.trycloudflare.com
                        match = re.search(r'https://[^\s]+\.trycloudflare\.com', line)
                        if match:
                            self.url = match.group(0)
                            Logger.info(f"Cloudflare Tunnel 已建立: {self.url}")
                    except Exception:
                        break
            
            t = threading.Thread(target=read_stream, daemon=True)
            t.start()
            
            # Wait for URL (up to 30 seconds)
            for _ in range(120): 
                if self.url:
                    return self.url
                if self.process.poll() is not None:
                    break
                time.sleep(0.5)
                
            if not self.url:
                # Check if process exited
                if self.process.poll() is not None:
                    out, _ = self.process.communicate()
                    raise Exception(f"Cloudflared 启动失败: {out}")
                raise Exception("获取 Cloudflare Tunnel URL 超时: " + "".join(list(output_tail)[-30:]).strip())
                
        except Exception as e:
            self.stop()
            raise e
            
        return self.url

    def stop(self):
        """Stop the tunnel"""
        if self.process:
            try:
                self.process.terminate()
                # Wait a bit
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            except Exception as e:
                Logger.error(f"关闭 Cloudflared 失败: {e}")
            finally:
                self.process = None
        self.url = None
