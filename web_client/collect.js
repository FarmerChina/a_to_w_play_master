const apiBase = location.origin.replace(/:\d+$/, '') + ':' + (location.port || '5000') + '/api';
const notification = document.getElementById('notification');
const playerState = document.getElementById('player-state') || document.getElementById('player-state-mobile');
const connectionStatus = document.getElementById('connection-status') || document.getElementById('connection-status-mobile');
let isConnected = false;

// 显示通知（带动画）
function showNotification(msg, isSuccess = true) {
    notification.textContent = msg;
    notification.style.backgroundColor = isSuccess ? 'rgba(76, 175, 80, 0.9)' : 'rgba(244, 67, 54, 0.9)';
    notification.classList.add('show');
    
    setTimeout(() => {
        notification.classList.remove('show');
    }, 2000);
}

// 显示消息（在消息区域）
function showMsg(msg, isSuccess = true) {
    const msgElement = document.getElementById('msg');
    msgElement.textContent = msg;
    msgElement.style.color = isSuccess ? 'var(--success-color)' : 'var(--danger-color)';
    msgElement.style.opacity = 1;
    
    setTimeout(() => {
        msgElement.style.opacity = 0;
    }, 1500);
}

// 只显示“已连接”或“未连接”
function updateConnectionUI(connected) {
    const playerStates = [
        document.getElementById('player-state'),
        document.getElementById('player-state-mobile')
    ];
    const connectionStatuses = [
        document.getElementById('connection-status'),
        document.getElementById('connection-status-mobile')
    ];
    playerStates.forEach(el => {
        if (el) {
            el.textContent = connected ? '已连接' : '未连接';
            el.style.color = connected ? 'var(--success-color)' : 'var(--danger-color)';
        }
    });
    connectionStatuses.forEach(el => {
        if (el) {
            el.textContent = connected ? '已连接到汽水音乐' : '等待连接汽水音乐...';
            el.style.color = connected ? 'var(--success-color)' : 'var(--danger-color)';
        }
    });
}

// 更新播放器状态
function updatePlayerState(isPlaying) {
    playerState.textContent = isPlaying ? '播放中' : '已暂停';
    playerState.style.color = isPlaying ? 'var(--success-color)' : 'var(--danger-color)';
    connectionStatus.textContent = '已连接到汽水音乐';
    connectionStatus.style.color = 'var(--success-color)';
}

// API请求函数
function post(url, actionName) {
    fetch(apiBase + url, {method: 'POST'})
        .then(r => r.json())
        .then(res => {
            if(res.status === 'ok') {
                showNotification(`${actionName}成功`);
                showMsg(`${actionName}操作已执行`);
                
                // 如果是播放/暂停，更新状态
                if(url === '/play' || url === '/pause') {
                    updatePlayerState(res.action === 'play/pause');
                }
            } else {
                showNotification(`${actionName}失败: ${res.message || '未知错误'}`, false);
                showMsg(`${actionName}失败`, false);
            }
        })
        .catch((error) => {
            showNotification('网络错误，请检查连接', false);
            showMsg('网络请求失败', false);
            console.error('API请求错误:', error);
        });
}

// 控制按钮状态
function setButtonState(enabled) {
    const btns = document.querySelectorAll('.btn-play, .btn-control, .btn-volume');
    btns.forEach(btn => {
        btn.disabled = !enabled;
        btn.style.opacity = enabled ? 1 : 0.5;
        btn.style.cursor = enabled ? '' : 'not-allowed';
    });
}


// 超时请求函数
function fetchWithTimeout(resource, options = {}) {
    const { timeout = 800 } = options;
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    return fetch(resource, {
        ...options,
        signal: controller.signal
    }).finally(() => clearTimeout(id));
}

// 初始状态检测和自动轮询
function checkAndUpdateState() { 
    fetchWithTimeout(apiBase + '/status', { method: 'GET', timeout: 1000 })
        .then(r => { 
            if (r.status === 200) {
                isConnected = true;
                updateConnectionUI(true);
            } else {
                isConnected = false;
                updateConnectionUI(false);
            }
            setButtonState(isConnected);
        })
        .catch((e) => { 
            isConnected = false;
            updateConnectionUI(false);
            setButtonState(false);
        });
}

// 页面加载完成后定时检测状态
window.addEventListener('load', () => {
    checkAndUpdateState();
    setInterval(checkAndUpdateState, 2000); // 检测间隔，提升响应速度
});

// 禁止双击放大和双指缩放
let lastTouchEnd = 0;
document.addEventListener('touchend', function (event) {
    const now = Date.now();
    if (now - lastTouchEnd <= 300) {
        event.preventDefault();
    }
    lastTouchEnd = now;
}, false);

document.addEventListener('gesturestart', function (event) {
    event.preventDefault();
});



// 收藏按钮的交互逻辑，调用后端API
function collect() {
    if (!isConnected) {
        showNotification('未连接到服务，无法操作', false);
        showMsg('请先启动服务', false);
        return;
    }
    post('/collect', '收藏');
}

// 控制器函数（增加连接判断）
function playPause() {
    if (!isConnected) {
        showNotification('未连接到服务，无法操作', false);
        showMsg('请先启动服务', false);
        return;
    }
    post('/play', '播放/暂停');
}

function next() {
    if (!isConnected) {
        showNotification('未连接到服务，无法操作', false);
        showMsg('请先启动服务', false);
        return;
    }
    post('/next', '下一首');
}

function prev() {
    if (!isConnected) {
        showNotification('未连接到服务，无法操作', false);
        showMsg('请先启动服务', false);
        return;
    }
    post('/prev', '上一首');
}

function volUp() {
    if (!isConnected) {
        showNotification('未连接到服务，无法操作', false);
        showMsg('请先启动服务', false);
        return;
    }
    post('/volume/up', '音量+');
}

function volDown() {
    if (!isConnected) {
        showNotification('未连接到服务，无法操作', false);
        showMsg('请先启动服务', false);
        return;
    }
    post('/volume/down', '音量-');
}
