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

def get_soda_music_path():
    import winreg
    import os
    import shutil
    import json
    import subprocess

    # 0. 优先读取配置文件中的路径
    config_file = "config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                data = json.load(f)
                saved_path = data.get('soda_music_path')
                if saved_path and os.path.exists(saved_path) and saved_path.lower().endswith('.exe'):
                    return saved_path
        except Exception:
            pass

    # 1. 尝试从注册表获取 (HKEY_CURRENT_USER 和 HKEY_LOCAL_MACHINE)
    roots = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
    key_paths = [
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall\SodaMusic",
        r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\SodaMusic",
        r"Software\SodaMusic" # 尝试应用自己的注册表项
    ]
    
    for root in roots:
        for key_path in key_paths:
            try:
                with winreg.OpenKey(root, key_path) as key:
                    # 尝试不同的键值
                    for value_name in ["DisplayIcon", "InstallLocation", "InstallPath", "Path"]:
                        try:
                            path, _ = winreg.QueryValueEx(key, value_name)
                            if not path: continue
                            
                            # 清理路径
                            path = path.strip('"').split(',')[0]
                            
                            # 如果是目录，拼接文件名
                            if os.path.isdir(path):
                                path = os.path.join(path, "SodaMusic.exe")
                                
                            if path and os.path.exists(path) and path.lower().endswith('.exe'):
                                return path
                        except WindowsError:
                            continue
            except WindowsError:
                continue
    
    # 2. 常见安装路径
    user_home = os.path.expanduser("~")
    local_app_data = os.environ.get('LOCALAPPDATA', '')
    program_files = os.environ.get('ProgramFiles', '')
    program_files_x86 = os.environ.get('ProgramFiles(x86)', '')
    
    paths = [
        os.path.join(local_app_data, r"SodaMusic\SodaMusic.exe"),
        os.path.join(local_app_data, r"Programs\SodaMusic\SodaMusic.exe"), # 某些Electron应用的默认路径
        os.path.join(program_files, r"SodaMusic\SodaMusic.exe"),
        os.path.join(program_files_x86, r"SodaMusic\SodaMusic.exe"),
        os.path.join(user_home, r"AppData\Local\SodaMusic\SodaMusic.exe"),
        r"D:\Program Files\SodaMusic\SodaMusic.exe", # 常见的D盘路径
        r"E:\Program Files\SodaMusic\SodaMusic.exe"
    ]
    
    for p in paths:
        if os.path.exists(p):
            return p
            
    # 3. 使用 shutil.which 查找 path 环境变量
    cmd_path = shutil.which("SodaMusic.exe")
    if cmd_path:
        return cmd_path
        
    # 4. 深度搜索开始菜单快捷方式
    try:
        # 定义开始菜单路径
        start_menu_paths = [
            os.path.join(os.environ.get('APPDATA', ''), r'Microsoft\Windows\Start Menu\Programs'),
            os.path.join(os.environ.get('PROGRAMDATA', ''), r'Microsoft\Windows\Start Menu\Programs')
        ]
        
        for menu_path in start_menu_paths:
            if not os.path.exists(menu_path):
                continue
                
            # 递归查找包含 "汽水" 或 "Soda" 的 .lnk 文件
            for root, dirs, files in os.walk(menu_path):
                for file in files:
                    if file.lower().endswith('.lnk') and ('汽水' in file or 'soda' in file.lower()):
                        lnk_path = os.path.join(root, file)
                        
                        # 使用 PowerShell 解析快捷方式目标路径 (无需额外依赖)
                        cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -Command "(New-Object -ComObject WScript.Shell).CreateShortcut(\'{lnk_path}\').TargetPath"'
                        try:
                            result = subprocess.check_output(cmd, shell=True, text=True).strip()
                            if result and os.path.exists(result) and result.lower().endswith('.exe'):
                                return result
                        except Exception:
                            continue
    except Exception:
        pass

    return None
