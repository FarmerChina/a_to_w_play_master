import psutil
import subprocess
import time
import os
from pywinauto.keyboard import send_keys
from .logger import Logger
from .utils import get_soda_music_path

class QishuiController:
    def __init__(self):
        self.app = None
        self.window = None 
 
    def _send_command(self, keys):
        try:
            soda_running = any(p.name() == "SodaMusic.exe" for p in psutil.process_iter(['name']))
            if soda_running:
                send_keys(keys)
                return {'status': 'ok'}
            else:
                Logger.warning("未检测到汽水音乐进程")
                return {'status': 'error', 'message': '未检测到汽水音乐进程'}
        except Exception as e:
            error_msg = f'命令发送失败: {str(e)}'
            Logger.error(error_msg)
            return {'status': 'error', 'message': error_msg}

    def run_shell_command(self, cmd):
        try:
            Logger.info(f"执行远程命令: {cmd}")
            # 使用 shell=True 允许执行 shell 命令
            # 注意：这存在安全风险，但在个人使用的工具中通常可以接受
            
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, startupinfo=startupinfo)
            stdout, stderr = process.communicate()
            return {'status': 'ok', 'stdout': stdout, 'stderr': stderr}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def play_pause(self):
        # 检查是否运行
        soda_running = any(p.name() == "SodaMusic.exe" for p in psutil.process_iter(['name']))
        if not soda_running:
            Logger.info("未检测到汽水音乐，尝试自动启动...")
            path = get_soda_music_path()
            if path:
                try:
                    Logger.info(f"正在启动汽水音乐: {path}")
                    # 尝试使用 os.startfile 启动 (相当于双击)
                    try:
                        os.startfile(path)
                    except Exception as e1:
                        Logger.warning(f"os.startfile启动失败: {e1}，尝试使用subprocess...")
                        # 备用方案：使用 shell start 命令
                        work_dir = os.path.dirname(path)
                        
                        startupinfo = None
                        if os.name == 'nt':
                            startupinfo = subprocess.STARTUPINFO()
                            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            startupinfo.wShowWindow = subprocess.SW_HIDE
                            
                        subprocess.Popen(f'start "" "{path}"', shell=True, cwd=work_dir, startupinfo=startupinfo)

                    # 等待启动，最多等待15秒
                    for _ in range(30):
                        time.sleep(0.5)
                        if any(p.name() == "SodaMusic.exe" for p in psutil.process_iter(['name'])):
                            break
                    else:
                        return {'status': 'error', 'message': '启动汽水音乐超时'}
                    
                    # 额外等待界面加载
                    time.sleep(2)
                except Exception as e:
                     Logger.error(f"启动汽水音乐失败: {e}")
                     return {'status': 'error', 'message': f'启动失败: {e}'}
            else:
                 Logger.warning("未找到汽水音乐安装路径，无法自动启动")

        result = self._send_command('^%p')
        result['action'] = 'play/pause'
        return result

    def next_track(self):
        result = self._send_command('^%n')
        result['action'] = 'next'
        return result

    def prev_track(self):
        result = self._send_command('^%t')
        result['action'] = 'prev'
        return result
    
    def collect_track(self):
        result = self._send_command('^%l')
        result['action'] = 'collect'
        return result

    def volume_up(self):
        result = self._send_command('^%u')
        result['action'] = 'vol_up'
        return result
    
    def volume_down(self):
        result = self._send_command('^%d')
        result['action'] = 'vol_down'
        return result
