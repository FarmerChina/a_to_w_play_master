def get_static_folder(sys, __file__):
    import os
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'web_client')
    else:
        # 修正为项目根目录下的 web_client
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'web_client'))

def get_local_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip
