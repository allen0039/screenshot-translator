# Windows 截图翻译工具（可视化配置版）

这是一个可在 Windows 使用的截图翻译工具，支持：

- 全局热键截图（默认 `Ctrl+Shift+Q`）
- 截图后弹出“是否翻译”
- OCR 识别文本
- 调用 **OpenAI 兼容接口**翻译
- 结果以“贴图”形式显示（可拖拽、置顶、可关闭）
- **可视化设置面板**（无需手改配置文件）

---

## 一、先运行源码版（用于开发/调试）

### 1) 安装依赖

```powershell
cd "D:\Agent\截图翻译"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 2) 启动

```powershell
python main.py
```

### 3) 在面板里配置（不再需要手改 .env）

启动后你会看到可视化面板，可直接填写：

- OpenAI Base URL（兼容接口地址）
- OpenAI API Key
- 模型名称（如 `gpt-4o-mini` / 你的兼容模型名）
- 目标语言（如 `中文`、`English`）
- 截图热键（如 `ctrl+shift+q`）

点击：
- **保存设置**：持久化到本地配置
- **测试翻译**：验证 API 是否可用
- **开始截图**：立即进入截图流程

---

## 二、打包成可分发软件（EXE）

你可以直接打包成 Windows 可执行程序：

### 1) 安装打包工具

```powershell
cd "D:\Agent\截图翻译"
.\.venv\Scripts\activate
pip install pyinstaller
```

### 2) 执行打包

```powershell
pyinstaller --noconfirm --clean --windowed --name ScreenshotTranslator main.py
```

打包完成后生成：

- `dist\ScreenshotTranslator\ScreenshotTranslator.exe`

双击该 EXE 即可运行（有可视化面板）。

---

## 三、做“安装包”（Setup.exe）

如果你希望是“下一步下一步安装”的形式，可再用 **Inno Setup** 制作安装程序。

### 方案（推荐）
1. 先完成上面的 PyInstaller 打包
2. 用 Inno Setup 把 `dist\ScreenshotTranslator\` 目录打成 `Setup.exe`
3. 安装后可在开始菜单启动

> 说明：本仓库当前默认交付的是可运行 EXE；安装包属于发布步骤，可按你的品牌信息再做定制（图标、安装路径、卸载项、开机启动选项等）。

---

## 四、配置保存位置

可视化面板保存的配置文件路径：

- `%APPDATA%\ScreenshotTranslator\config.json`

所以你的 API Key 等设置会自动记住，不用每次重填。

---

## 五、常见问题

1. **看不到热键生效**
   - 某些系统环境下 `keyboard` 全局监听需要管理员权限运行。

2. **测试翻译失败**
   - 检查 Base URL / API Key / Model 是否正确
   - 确认你的接口是 OpenAI 兼容格式

3. **OCR 识别慢**
   - 首次启动模型加载会慢一些，后续会好很多。
