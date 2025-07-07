import psutil
from pywinauto.keyboard import send_keys
from .logger import Logger

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

    def play_pause(self):
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
