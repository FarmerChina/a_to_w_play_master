import sys
from flask import Flask, jsonify, request, send_from_directory
from .utils import get_static_folder
from .controller import QishuiController
import psutil

app = Flask(__name__, static_folder=get_static_folder(sys, __file__), static_url_path='')
qishui = QishuiController()

@app.route('/api/play', methods=['POST'])
def play():
    return jsonify(qishui.play_pause())

@app.route('/api/pause', methods=['POST'])
def pause():
    return jsonify(qishui.play_pause())

@app.route('/api/next', methods=['POST'])
def next_track():
    return jsonify(qishui.next_track())

@app.route('/api/prev', methods=['POST'])
def prev_track():
    return jsonify(qishui.prev_track())

@app.route('/api/collect', methods=['POST'])
def collect_track():
    return jsonify(qishui.collect_track())

@app.route('/api/volume/up', methods=['POST'])
def volume_up():
    return jsonify(qishui.volume_up())

@app.route('/api/volume/down', methods=['POST'])
def volume_down():
    return jsonify(qishui.volume_down())

@app.route('/api/status', methods=['GET'])
def status():
    soda_running = any(p.name() == "SodaMusic.exe" for p in psutil.process_iter(['name']))
    if soda_running:
        return jsonify({'status': 'ok'}), 200
    else:
        return jsonify({'status': 'error', 'message': '未检测到汽水音乐进程'}), 503

@app.route('/')
def web_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:filename>')
def web_static(filename):
    return send_from_directory(app.static_folder, filename)
