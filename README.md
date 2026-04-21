# 截图翻译工具（Windows）

一个面向普通用户的截图翻译工具，开箱即用，支持多供应商模板、贴图翻译、快捷键配置。

## 功能亮点
- 全局截图热键（默认 `Ctrl+Shift+Q`）
- 退出热键（默认 `Esc`，可自定义）
- OCR 识别 + 原位覆盖翻译（翻译结果覆盖在截图对应文本区域）
- 贴图窗口支持：翻译、重截、保存、复制、缩放、拖拽、快捷键关闭
- 供应商模板：`OpenAI` / `DeepL` / `LibreTranslate` / `Argos Translate`
- 可导入/导出供应商配置（支持导入时合并或覆盖）
- 深色 / 浅色主题切换

---

## 1. 普通用户使用（推荐）

### 1) 直接运行 EXE
- 打开：`dist\ScreenshotTranslator\ScreenshotTranslator.exe`
- 首次启动进入可视化设置面板。

### 2) 基本设置
- `模型供应商`：选择已有项或新增自定义名称
- `供应商模板`：选择 OpenAI / DeepL / LibreTranslate / Argos Translate
- `API 地址`：模板会自动填默认值，可手改
- `API 密钥`：按模板填写（OpenAI / DeepL 必填；Libre/Argos 视服务而定）
- `目标语言`：下拉快速选择或手动输入
- `截图热键`、`退出热键`
- `保存目录`

点击 `保存设置`。

### 3) 使用截图翻译
- 按截图热键或点击 `开始截图`
- 框选区域后弹出贴图
- 在贴图上点 `翻译`，结果会覆盖到对应文字区域
- 可用 `Esc` 或你设置的退出热键快速关闭截图/贴图

---

## 2. 供应商配置指引

### OpenAI 模板
- 用于 OpenAI 兼容接口
- 先填 `API 地址` + `API 密钥`
- 可点击 `获取` 拉模型，再手动添加到模型列表

### DeepL 模板
- 调用 `/translate`
- 需要 DeepL API Key
- 不使用模型列表

### LibreTranslate 模板
- 调用 `/translate`
- 可无 API Key（取决于服务端）
- 不使用模型列表

### Argos Translate 模板
- 常见本地服务地址：`http://127.0.0.1:8000`
- 一般无需 API Key
- 不使用模型列表

> 可点击界面里的 `配置指引` 查看当前模板的详细提示。

---

## 3. 供应商配置导入/导出

- `导出配置`：导出供应商列表为 JSON
- `导入配置`：导入 JSON，若本地已有配置会弹窗让你选：
  - `合并`：按供应商名称合并，同名用导入内容覆盖
  - `覆盖`：用导入内容替换本地供应商列表

---

## 4. 从源码运行（开发/调试）

### 环境要求
- Windows
- Python 3.11 或 3.12（不建议 3.14）

### 安装与启动
```powershell
cd screenshot-translator
py -3.12 -m venv .venv312
.\.venv312\Scripts\activate
pip install -r requirements.txt
python main.py
```

---

## 5. 打包 EXE

```powershell
cd screenshot-translator
.\.venv312\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
python -m PyInstaller --noconfirm --clean ScreenshotTranslator.spec
```

产物路径：
- `dist\ScreenshotTranslator\ScreenshotTranslator.exe`

---

## 6. 配置文件位置

- `%APPDATA%\ScreenshotTranslator\config.json`

此文件保存你的热键、主题、供应商、模型和目录配置。

---

## 7. 常见问题

- 热键无效：尝试以管理员权限运行
- 翻译失败：检查模板与 API 地址是否匹配、密钥是否正确
- OpenAI 获取模型失败：确认接口支持 `models.list`
- Libre/Argos 无响应：确认服务已启动且地址可访问
