# 截图翻译工具（Windows）

一个开箱即用的截图翻译工具：按快捷键截图、识别文字并原位覆盖翻译，适合日常阅读外语图片/界面。

## 功能亮点
- 全局截图热键（默认 `Ctrl+Shift+Q`）
- 退出热键（默认 `Esc`，支持自定义）
- OCR 识别 + 原位覆盖翻译（翻译结果覆盖到原文字区域）
- 贴图窗口支持：翻译、重截、保存、复制、缩放、拖拽、快捷键关闭
- 多供应商模板：`OpenAI` / `DeepL` / `LibreTranslate` / `Argos Translate`
- 供应商配置可导入/导出（导出文件默认不包含 API Key）
- 深色 / 浅色主题切换

---

## 1. 下载与启动（普通用户）

请在 GitHub Release 下载以下任一文件：

- `ScreenshotTranslator-Setup-v1.0.7.exe`（推荐）：安装包，按向导安装即可
- `ScreenshotTranslator-OneFile.exe`：单文件免安装版，下载后可直接运行

如果你使用目录版（`dist\ScreenshotTranslator\ScreenshotTranslator.exe`）：
- 必须保留整个 `ScreenshotTranslator` 目录（包含 `_internal`）
- 不要只单独拷贝 exe 运行

首次启动会打开设置面板。

---

## 2. 首次配置（3 分钟）

在设置面板中填写：

1. **模型供应商**：选择现有项，或新增一个自定义名称
2. **供应商模板**：选择 `OpenAI` / `DeepL` / `LibreTranslate` / `Argos Translate`
3. **API 地址**：模板会自动填默认值，可按你的服务修改
4. **API 密钥**：
   - OpenAI / DeepL 通常必填
   - LibreTranslate / Argos 视服务端而定
5. **目标语言**：可下拉选择或手动输入（如 `中文`、`English`、`日本語`）
6. **截图热键 / 退出热键**
7. **保存目录**（用于保存贴图）

点击 **保存设置**。

---

## 3. 如何使用

1. 按截图热键（默认 `Ctrl+Shift+Q`）或点 **开始截图**
2. 鼠标框选需要翻译的区域
3. 弹出贴图窗口后点击 **翻译**
4. 翻译结果会覆盖在原文字位置

常用操作：
- **Esc**（或你设置的退出热键）快速关闭截图/贴图
- 在贴图窗口可执行：重截、保存、复制、缩放、拖拽

---

## 4. 供应商模板说明

### OpenAI 模板
- 用于 OpenAI 兼容接口
- 需要 `API 地址` + `API 密钥`
- 可点击“获取”拉取模型后加入模型列表

### DeepL 模板
- 调用 `/translate`
- 需要 DeepL API Key
- 不使用模型列表

### LibreTranslate 模板
- 调用 `/translate`
- 可无 API Key（取决于服务端配置）
- 不使用模型列表

### Argos Translate 模板
- 常见本地服务地址：`http://127.0.0.1:8000`
- 一般无需 API Key
- 不使用模型列表

提示：界面中的 **配置指引** 会显示当前模板的填写示例。

---

## 5. 供应商配置导入 / 导出

- **导出配置**：导出供应商列表为 JSON
  - 导出的 JSON 中 `api_key` 默认会被清空
  - 导入后请手动补填密钥
- **导入配置**：导入 JSON 时可选
  - **合并**：按供应商名称合并，同名项使用导入内容覆盖
  - **覆盖**：用导入内容替换本地供应商列表

---

## 6. 常见问题

### 1) 热键无效
尝试以管理员权限运行软件后再测试。

### 2) 翻译失败
检查：
- 供应商模板是否与 API 地址匹配
- API Key 是否正确
- 网络是否可用

### 3) OpenAI 获取模型失败
确认你的接口支持 `models.list`。

### 4) Libre / Argos 无响应
确认服务已经启动，且地址可访问。

### 5) 启动报错：`Failed to load Python DLL ... _internal\python312.dll`
- 目录版请确认运行的是完整 `dist\ScreenshotTranslator` 目录
- 确认 `ScreenshotTranslator.exe` 同级存在 `_internal\python312.dll`
- 若被杀毒软件隔离，请恢复文件并将目录加入白名单
- 仍失败时，安装/修复 Microsoft Visual C++ Redistributable (x64, 2015-2022)

---

## 7. 配置文件位置

程序配置保存在：

- `%APPDATA%\ScreenshotTranslator\config.json`

其中包含热键、主题、供应商、模型、保存目录等设置。

---

## 8. 从源码运行（开发者）

### 环境要求
- Windows
- Python 3.11 或 3.12（不建议 3.14）

### 启动
```powershell
cd screenshot-translator
py -3.12 -m venv .venv312
.\.venv312\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## 9. 打包（开发者）

### 单文件 EXE
```powershell
build_onefile.bat
```
产物：`dist\ScreenshotTranslator-OneFile.exe`

### 一键发布构建（目录版 + 单文件 + 安装包）
```powershell
build_release.bat
```
产物：
- `dist\ScreenshotTranslator\ScreenshotTranslator.exe`
- `dist\ScreenshotTranslator-OneFile.exe`
- `dist\ScreenshotTranslator-Setup-v1.0.7.exe`（系统已安装 Inno Setup 时生成）
