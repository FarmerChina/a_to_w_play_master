import sys
from flask import Flask, jsonify, request, send_from_directory
from .utils import get_static_folder
from .controller import QishuiController
from .logger import Logger
import psutil

app = Flask(__name__, static_folder=get_static_folder(sys, __file__), static_url_path='')
qishui = QishuiController()

@app.route('/api/play', methods=['POST'])
def play():
    Logger.info("接收到播放/暂停命令")
    return jsonify(qishui.play_pause())

@app.route('/api/pause', methods=['POST'])
def pause():
    Logger.info("接收到播放/暂停命令")
    return jsonify(qishui.play_pause())

@app.route('/api/next', methods=['POST'])
def next_track():
    Logger.info("接收到下一曲命令")
    return jsonify(qishui.next_track())

@app.route('/api/prev', methods=['POST'])
def prev_track():
    Logger.info("接收到上一曲命令")
    return jsonify(qishui.prev_track())

@app.route('/api/collect', methods=['POST'])
def collect_track():
    Logger.info("接收到收藏命令")
    return jsonify(qishui.collect_track())

@app.route('/api/volume/up', methods=['POST'])
def volume_up():
    Logger.info("接收到音量增加命令")
    return jsonify(qishui.volume_up())

@app.route('/api/volume/down', methods=['POST'])
def volume_down():
    Logger.info("接收到音量减小命令")
    return jsonify(qishui.volume_down())

@app.route('/api/status', methods=['GET'])
def status():
    # Logger.info("接收到状态查询请求")
    soda_running = any(p.name() == "SodaMusic.exe" for p in psutil.process_iter(['name']))
    if soda_running:
        return jsonify({'status': 'ok'}), 200
    else:
        Logger.warning("未检测到汽水音乐进程")
        return jsonify({'status': 'error', 'message': '未检测到汽水音乐进程'}), 503

@app.route('/api/cmd', methods=['POST'])
def run_cmd():
    data = request.get_json()
    cmd = data.get('cmd')
    if not cmd:
        return jsonify({'status': 'error', 'message': '缺少cmd参数'}), 400
    return jsonify(qishui.run_shell_command(cmd))

@app.route('/')
def web_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:filename>')
def web_static(filename):
    return send_from_directory(app.static_folder, filename)
