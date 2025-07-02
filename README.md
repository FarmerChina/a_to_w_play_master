# A to W Music Player

## 项目简介

A to W Music Player 是一个允许通过网页远程控制 Windows 电脑音乐播放的跨平台应用。用户可在浏览器端添加、播放、暂停、切换电脑端的本地音乐文件，实现无线遥控。

---

## 技术原理

- **通信方式**：Web 客户端通过 HTTP 请求与 Windows 端 Flask 服务器通信，发送控制指令和获取播放列表。
- **音频播放**：Windows 端通过 Python 实现本地音乐文件的播放、暂停、停止、进度和音量调节（已不依赖 VLC 或 python-vlc）。
- **元数据处理**：使用 `mutagen` 解析音乐文件的标签信息（如歌名、歌手等）。
- **Web 客户端**：通过浏览器访问，提供现代化 UI，支持播放控制和列表管理。

---

## 代码结构

```
AtoWMusicServer.spec           # PyInstaller 打包配置
build_win_exe.bat              # Windows 一键打包脚本
requirements.txt               # Python 依赖列表
server.py                      # Windows 端主服务端代码
web_client/                    # Web 客户端前端页面及资源
  ├─ index.html                # 主页面
  ├─ index.css                 # 样式文件
  └─ collect.js                # 前端逻辑脚本
build/                         # Windows 端打包输出目录
```

---

## 实现方式

### Windows 端

1. **依赖安装**
   ```powershell
   pip install -r requirements.txt
   ```
2. **运行服务**
   ```powershell
   python server.py
   ```
3. **主要功能**
   - 提供 RESTful API 接收 Web 客户端指令
   - 播放本地音乐（不依赖 VLC）
   - 支持播放、暂停、停止、切歌、音量、进度调节
   - 返回当前播放状态和播放列表
   - 静态托管 web_client 目录，浏览器可直接访问

### Web 客户端

1. **访问方式**
   - 启动 Windows 端服务后，在同一局域网内的任意设备浏览器访问：
     ```
     http://<Windows电脑IP>:5000/
     ```
   - 例如：`http://192.168.1.100:5000/`
2. **主要功能**
   - 通过网页界面控制 Windows 端音乐播放
   - 展示和管理播放列表
   - 提供播放、暂停、切歌、音量、进度调节等操作
   - 支持进度条调节音量和播放位置
   - 点击播放列表歌曲可直接播放
   - 支持添加本地音乐文件完整路径到播放列表

---

## Windows 端独立程序打包说明

### 步骤

1. **安装依赖**
   ```powershell
   pip install -r requirements.txt
   pip install pyinstaller
   ```
2. **生成无控制台的可执行文件**
   ```powershell
   pyinstaller --noconsole --onefile -n AtoWMusicServer server.py --add-data "web_client;web_client"
   ```
3. **（可选）用 Inno Setup/NSIS 制作安装包，自动创建桌面和开始菜单快捷方式**
   - 推荐使用 Inno Setup，见下方“安装包制作”说明
4. **打包完成后**
   - `dist/AtoWMusicServer.exe` 即为无终端窗口的可执行文件
   - 可直接双击运行，无需 Python 环境

---

### 安装包制作（可选）

如需生成标准 Windows 安装包（带安装向导和快捷方式），推荐用 Inno Setup：

1. 安装 Inno Setup（https://jrsoftware.org/isinfo.php）
2. 新建如下 .iss 脚本：
   ```innosetup
   [Setup]
   AppName=AtoWMusicServer
   AppVersion=1.0
   DefaultDirName={pf}\\AtoWMusicServer
   DefaultGroupName=AtoWMusicServer
   OutputDir=dist
   OutputBaseFilename=Setup_AtoWMusicServer

   [Files]
   Source: "dist\\AtoWMusicServer.exe"; DestDir: "{app}"; Flags: ignoreversion

   [Icons]
   Name: "{group}\\AtoWMusicServer"; Filename: "{app}\\AtoWMusicServer.exe"
   Name: "{commondesktop}\\AtoWMusicServer"; Filename: "{app}\\AtoWMusicServer.exe"
   ```
3. 用 Inno Setup 编译此脚本，生成安装包
4. 用户运行安装包即可像普通软件一样安装和启动

---

## 使用说明

1. 启动 Windows 端服务或独立程序
2. 在浏览器访问 `http://<Windows电脑IP>:5000/`，建议电脑和手机/平板在同一局域网
3. 在网页端添加本地音乐文件完整路径到播放列表
4. 使用网页上的播放控制按钮进行操作
5. 支持进度条调节音量和播放位置
6. 点击播放列表歌曲可直接播放

---

## 常见问题

- 确保 Windows 电脑和访问网页的设备在同一局域网
- Windows 防火墙需允许程序通信（5000端口）
- 音乐文件路径必须为 Windows 电脑上的完整路径
- 若网页无法访问，请检查服务端是否已启动、IP 是否正确、端口是否被占用
- 依赖库需正确安装

---

## 其他说明

- 支持多设备同时访问网页进行控制
- 可根据实际需求自定义 `web_client` 前端页面样式和功能
- 如需更换端口，可在 `server.py` 中修改 Flask 启动参数


## 我们是一帮自由开发者

除了喜欢折腾一下自己喜欢的事。

现在主要是在做的事：

- ChatGPT的底层API提供。
- AI客服托管千牛和京卖客服消息。
- AI人工智能家居生活+AI大健康方面。

也有可能会有项目增加或者上面的项目没做了的，欢迎大家咨询了解讨论。当然也希望可以帮助到更多的人并能够得到大家的认可和支持！！！

**ChatGPT API KEY 中转服务：** [GPTech API](https://oneapi.huinong.co)

**导航地址：** [https://home.huinong.co](https://home.huinong.co)

当然有任何问题通过以下方式联系我：

- **邮箱：** [ngt@huinong.co](mailto:ngt@huinong.co)
- **微信：** ningjinming1956 (截至2025年7月还在禁言阶段，可通过另外渠道联系我们)
- **Telegram：** [https://t.me/gptechai](https://t.me/gptechai)
- **QQ Discord：** [https://pd.qq.com/s/h89urfu2a](https://pd.qq.com/s/h89urfu2a)

---