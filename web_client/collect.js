const apiBase = '/api';
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
function setButtonState(enabled, allowPlay = false) {
    const btns = document.querySelectorAll('.btn-control, .btn-volume, #collect-btn');
    btns.forEach(btn => {
        btn.disabled = !enabled;
        btn.style.opacity = enabled ? 1 : 0.5;
        btn.style.cursor = enabled ? '' : 'not-allowed';
    });

    const playBtn = document.querySelector('.btn-play');
    if (playBtn) {
        const playEnabled = enabled || allowPlay;
        playBtn.disabled = !playEnabled;
        playBtn.style.opacity = playEnabled ? 1 : 0.5;
        playBtn.style.cursor = playEnabled ? '' : 'not-allowed';
    }
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
let lastConnectionState = null; // 'CONNECTED', 'WAITING', 'DISCONNECTED'
let failureCount = 0; // 连续失败计数
const FAILURE_THRESHOLD = 3; // 连续失败多少次才判定为断开

function checkAndUpdateState() { 
    // 增加超时时间到 3000ms，防止网络波动或服务器响应慢导致误判
    fetchWithTimeout(apiBase + '/status', { method: 'GET', timeout: 3000 })
        .then(r => { 
            if (r.status === 200) {
                // 连接成功，重置失败计数
                failureCount = 0;
                
                // 只有状态改变时才刷新UI
                if (lastConnectionState !== 'CONNECTED') {
                    isConnected = true;
                    updateConnectionUI(true);
                    setButtonState(true);
                    lastConnectionState = 'CONNECTED';
                }
            } else {
                // 连接上服务器但状态异常（如503未检测到进程）
                // 这种情况下通常不是网络问题，而是业务状态，所以可以立即更新（或者也稍微缓冲一下？）
                // 这里选择立即更新，因为响应是明确的
                failureCount = 0; // 服务器是通的，重置网络失败计数
                
                if (lastConnectionState !== 'WAITING') {
                    isConnected = false;
                    updateConnectionUI(false);
                    // 状态码非200（如503），说明连接上了服务器但检测不到汽水音乐
                    // 此时允许点击播放按钮以尝试自动启动
                    setButtonState(false, true);
                    lastConnectionState = 'WAITING';
                }
            }
        })
        .catch((e) => { 
            // 网络请求失败（超时、断网等）
            failureCount++;
            console.warn(`状态检查失败 (${failureCount}/${FAILURE_THRESHOLD}):`, e);

            // 只有连续失败达到阈值，才更新为断开状态
            if (failureCount >= FAILURE_THRESHOLD) {
                if (lastConnectionState !== 'DISCONNECTED') {
                    isConnected = false;
                    updateConnectionUI(false);
                    // 网络错误，完全无法连接
                    setButtonState(false, false);
                    lastConnectionState = 'DISCONNECTED';
                }
            }
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
    // 播放/暂停是特例，如果未连接（即汽水音乐未启动），我们仍允许点击以触发自动启动
    // 后端会自动启动汽水音乐
    // 但如果连后端服务都连不上（status检查失败），那还是不能点
    // 这里的isConnected是基于 /status 接口返回的 200 OK (表示检测到进程) 
    // 还是仅仅表示能连上后端？
    // 看 status() 实现： only returns 200 if process exists.
    // 所以 isConnected 为 false 时，也可能是后端活着但汽水音乐没活。
    // 我们应该允许 playPause 即使 isConnected 为 false (只要是 503 而不是网络错误)
    
    // Wait, if /status returns 503, isConnected is set to false.
    // If I block playPause when !isConnected, I block the auto-start feature!
    // I need to change this logic.
    
    // Let's relax the check for playPause.
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

function sendCmd() {
    // 同样允许发送CMD即使汽水音乐没启动，只要后端服务在
    const input = document.getElementById('cmd-input');
    const cmd = input.value.trim();
    if (!cmd) return;
    
    fetch(apiBase + '/cmd', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({cmd: cmd})
    })
    .then(r => r.json())
    .then(res => {
        if(res.status === 'ok') {
            showNotification('指令已发送');
            showMsg('指令已执行');
            if (res.stdout) console.log(res.stdout);
        } else {
            showNotification('指令失败', false);
            showMsg('错误: ' + (res.message || '未知错误'), false);
        }
    })
    .catch(e => {
        showNotification('请求失败', false);
        console.error(e);
    });
}

function shutdownPC() {
    const confirmText = window.prompt('危险操作：请输入“关机”以确认执行')
    if (confirmText !== '关机') {
        showNotification('已取消', false);
        return;
    }

    const delayInput = window.prompt('请输入延时秒数(0-3600)，默认30', '30');
    if (delayInput === null) {
        showNotification('已取消', false);
        return;
    }

    const delaySeconds = Number.parseInt(String(delayInput).trim(), 10);
    if (Number.isNaN(delaySeconds) || delaySeconds < 0) {
        showNotification('延时秒数不合法', false);
        return;
    }

    fetch(apiBase + '/system/shutdown', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({confirm: '关机', delay_seconds: delaySeconds})
    })
    .then(r => r.json())
    .then(res => {
        if (res.status === 'ok') {
            showNotification(`关机指令已下发(${res.delay_seconds ?? delaySeconds}s)`);
            showMsg('关机操作已执行');
        } else {
            showNotification('关机失败', false);
            showMsg('错误: ' + (res.message || '未知错误'), false);
        }
    })
    .catch(e => {
        showNotification('请求失败', false);
        console.error(e);
    });
}

function restartPC() {
    const confirmText = window.prompt('危险操作：请输入“重启”以确认执行')
    if (confirmText !== '重启') {
        showNotification('已取消', false);
        return;
    }

    const delayInput = window.prompt('请输入延时秒数(0-3600)，默认30', '30');
    if (delayInput === null) {
        showNotification('已取消', false);
        return;
    }

    const delaySeconds = Number.parseInt(String(delayInput).trim(), 10);
    if (Number.isNaN(delaySeconds) || delaySeconds < 0) {
        showNotification('延时秒数不合法', false);
        return;
    }

    fetch(apiBase + '/system/restart', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({confirm: '重启', delay_seconds: delaySeconds})
    })
    .then(r => r.json())
    .then(res => {
        if (res.status === 'ok') {
            showNotification(`重启指令已下发(${res.delay_seconds ?? delaySeconds}s)`);
            showMsg('重启操作已执行');
        } else {
            showNotification('重启失败', false);
            showMsg('错误: ' + (res.message || '未知错误'), false);
        }
    })
    .catch(e => {
        showNotification('请求失败', false);
        console.error(e);
    });
}
