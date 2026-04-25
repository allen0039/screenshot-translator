import io
import html
import json
import os
import re
import sys
import ctypes
from datetime import datetime
from urllib import error as urlerror
from urllib import parse as urlparse_lib
from urllib import request as urlrequest
from dataclasses import asdict, dataclass, field
from urllib.parse import urlparse

def _show_bootstrap_error(message: str):
    try:
        ctypes.windll.user32.MessageBoxW(0, message, "截图翻译工具", 0x10)
    except Exception:
        pass
    print(message)


if sys.version_info[:2] >= (3, 14):
    _show_bootstrap_error(
        "当前运行环境为 Python 3.14，依赖包与此版本不兼容。\n"
        "请改用 Python 3.11 或 3.12 重新创建虚拟环境并安装依赖。"
    )
    raise SystemExit(1)


try:
    import keyboard
    import numpy as np
    from openai import OpenAI
    from PIL import Image
    from rapidocr_onnxruntime import RapidOCR

    from PySide6.QtCore import QObject, QPoint, QRect, QRectF, Qt, Signal, QByteArray, QBuffer, QIODevice, QSize
    from PySide6.QtGui import (
        QAction,
        QColor,
        QCursor,
        QFont,
        QFontMetrics,
        QGuiApplication,
        QKeySequence,
        QTextDocument,
        QMouseEvent,
        QPainter,
        QPainterPath,
        QPen,
        QPixmap,
    )
    from PySide6.QtWidgets import (
        QApplication,
    QDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
        QLineEdit,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPushButton,
        QRubberBand,
        QSizeGrip,
        QStyle,
        QSystemTrayIcon,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError as ex:
    _show_bootstrap_error(
        f"缺少运行依赖：{ex.name}\n"
        "请先安装 requirements.txt 中的依赖后再运行。"
    )
    raise SystemExit(1)


APP_NAME = "截图翻译工具"
APP_VERSION = "v1.0.8"
APP_TITLE = f"{APP_NAME} {APP_VERSION}"
CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.getcwd()), "ScreenshotTranslator")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

PROVIDER_TEMPLATES = {
    "OpenAI": {
        "default_url": "https://api.openai.com/v1",
        "requires_api_key": True,
        "guide": "兼容 OpenAI Chat 接口。先填 Base URL + API Key，再获取模型；翻译走 chat.completions。",
    },
    "DeepL": {
        "default_url": "https://api-free.deepl.com/v2",
        "requires_api_key": True,
        "guide": "使用 DeepL /translate 接口。需填写 DeepL API Key；不需要模型列表。",
    },
    "LibreTranslate": {
        "default_url": "https://libretranslate.com",
        "requires_api_key": False,
        "guide": "使用 LibreTranslate /translate 接口。可不填 API Key；建议先测试连通性。",
    },
    "Argos Translate": {
        "default_url": "http://127.0.0.1:8000",
        "requires_api_key": False,
        "guide": "通常为本地部署服务（常见 127.0.0.1:8000）。无需模型列表，先确认本地服务已启动。",
    },
}


@dataclass
class AppConfig:
    hotkey: str = "ctrl+shift+q"
    cancel_hotkey: str = "esc"
    provider_name: str = "OpenAI"
    provider_template: str = "OpenAI"
    providers: list[dict] = field(
        default_factory=lambda: [
            {
                "name": "OpenAI",
                "template": "OpenAI",
                "base_url": "https://api.openai.com/v1",
                "api_key": "",
            }
        ]
    )
    model: str = "gpt-4o-mini"
    model_list: list[str] = field(default_factory=lambda: ["gpt-4o-mini"])
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    target_lang: str = "中文"
    save_dir: str = os.path.join(os.path.expanduser("~"), "Pictures", "Screenshots")
    theme: str = "dark"


class ConfigStore:
    @staticmethod
    def load() -> AppConfig:
        if not os.path.exists(CONFIG_PATH):
            return AppConfig()
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            model = data.get("model", "gpt-4o-mini")
            model_list = data.get("model_list", [model])
            if not isinstance(model_list, list):
                model_list = [model]
            model_list = [str(item).strip() for item in model_list if str(item).strip()]
            if not model_list:
                model_list = [model]

            providers = data.get("providers")
            if not isinstance(providers, list) or not providers:
                providers = [
                    {
                        "name": data.get("provider_name", "OpenAI"),
                        "template": data.get("provider_template", "OpenAI"),
                        "base_url": data.get("base_url", "https://api.openai.com/v1"),
                        "api_key": data.get("api_key", ""),
                    }
                ]
            provider_name = str(data.get("provider_name", "")).strip() or "OpenAI"
            provider_template = str(data.get("provider_template", "")).strip() or "OpenAI"
            matched = None
            normalized_providers = []
            for item in providers:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                template = str(item.get("template", "")).strip() or "OpenAI"
                if template not in PROVIDER_TEMPLATES:
                    template = "OpenAI"
                base_url = str(item.get("base_url", "")).strip()
                api_key = str(item.get("api_key", "")).strip()
                if not name:
                    continue
                entry = {"name": name, "template": template, "base_url": base_url, "api_key": api_key}
                normalized_providers.append(entry)
                if name == provider_name:
                    matched = entry
            if not normalized_providers:
                normalized_providers = [
                    {
                        "name": "OpenAI",
                        "template": "OpenAI",
                        "base_url": data.get("base_url", "https://api.openai.com/v1"),
                        "api_key": data.get("api_key", ""),
                    }
                ]
            if matched is None:
                matched = normalized_providers[0]
                provider_name = matched["name"]
            provider_template = matched.get("template", provider_template)

            return AppConfig(
                hotkey=data.get("hotkey", "ctrl+shift+q"),
                cancel_hotkey=data.get("cancel_hotkey", "esc"),
                provider_name=provider_name,
                provider_template=provider_template,
                providers=normalized_providers,
                model=model,
                model_list=model_list,
                base_url=matched.get("base_url", "https://api.openai.com/v1"),
                api_key=matched.get("api_key", ""),
                target_lang=data.get("target_lang", "中文"),
                save_dir=data.get("save_dir", os.path.join(os.path.expanduser("~"), "Pictures", "Screenshots")),
                theme=data.get("theme", "dark"),
            )
        except Exception as ex:
            QMessageBox.warning(None, "配置读取失败", f"配置文件读取失败，将使用默认配置。\n\n路径：{CONFIG_PATH}\n错误：{ex}")
            return AppConfig()

    @staticmethod
    def save(config: AppConfig):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        temp_path = f"{CONFIG_PATH}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(asdict(config), f, ensure_ascii=False, indent=2)
        os.replace(temp_path, CONFIG_PATH)


class ConfirmDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("截图翻译")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.label = QLabel("截图完成，是否立即翻译？")
        self.btn_translate = QPushButton("翻译")
        self.btn_cancel = QPushButton("取消")

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_translate)
        btn_layout.addWidget(self.btn_cancel)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self.btn_translate.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)


def _normalize_hotkey_text(hotkey: str) -> str:
    return (hotkey or "").strip().lower().replace(" ", "")


def _event_hotkey_text(event) -> str:
    key = event.key()
    modifiers = event.modifiers()

    if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
        return ""

    seq = QKeySequence(modifiers | key).toString().lower().replace(" ", "")
    if not seq:
        seq = QKeySequence(key).toString().lower().replace(" ", "")
    return seq


def _hotkey_matches_event(event, hotkey: str) -> bool:
    return _event_hotkey_text(event) == _normalize_hotkey_text(hotkey)


class RegionSelector(QWidget):
    region_selected = Signal(QRect)
    canceled = Signal()

    def __init__(self, background: QPixmap | None = None, cancel_hotkey: str = "esc"):
        super().__init__()
        self.setWindowTitle("选择截图区域")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowState(Qt.WindowFullScreen)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()

        self.background = background
        self.cancel_hotkey = cancel_hotkey or "esc"
        self.origin = QPoint()
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)

    def paintEvent(self, _):
        if self.background and not self.background.isNull():
            painter = QPainter(self)
            painter.drawPixmap(0, 0, self.background)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.origin = event.position().toPoint()
            self.rubber_band.setGeometry(QRect(self.origin, self.origin))
            self.rubber_band.show()

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.origin.isNull():
            rect = QRect(self.origin, event.position().toPoint()).normalized()
            self.rubber_band.setGeometry(rect)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            rect = self.rubber_band.geometry()
            self.rubber_band.hide()
            self.close()
            if rect.width() < 5 or rect.height() < 5:
                self.canceled.emit()
                return
            self.region_selected.emit(rect)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape or _hotkey_matches_event(event, self.cancel_hotkey):
            self.close()
            self.canceled.emit()


class CaptureStickerWindow(QWidget):
    request_translate = Signal(object)
    request_recapture = Signal()

    def __init__(self, pixmap: QPixmap, top_left: QPoint | None = None, cancel_hotkey: str = "esc"):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setFocusPolicy(Qt.StrongFocus)

        self.drag_pos = None
        self.parent_controller = None
        self.cancel_hotkey = cancel_hotkey or "esc"
        self.capture_pixmap = pixmap
        self.current_pixmap = QPixmap(self.capture_pixmap)
        self.zoom_percent = 100

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(240, 140)

        self.btn_translate = QPushButton("翻译")
        self.btn_recapture = QPushButton("重截")
        self.btn_save = QPushButton("保存")
        self.btn_copy = QPushButton("复制")
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_out = QPushButton("-")
        self.zoom_label = QLabel("100%")
        self.btn_close = QPushButton("×")

        self.btn_translate.setFixedSize(60, 28)
        self.btn_recapture.setFixedSize(60, 28)
        self.btn_save.setFixedSize(60, 28)
        self.btn_copy.setFixedSize(60, 28)
        self.btn_zoom_in.setFixedSize(28, 28)
        self.btn_zoom_out.setFixedSize(28, 28)
        self.btn_close.setFixedSize(28, 28)

        self.btn_translate.clicked.connect(lambda: self.request_translate.emit(self))
        self.btn_recapture.clicked.connect(self._recapture)
        self.btn_save.clicked.connect(self._save_image)
        self.btn_copy.clicked.connect(self._copy_image)
        self.btn_zoom_in.clicked.connect(lambda: self.set_zoom(self.zoom_percent + 10))
        self.btn_zoom_out.clicked.connect(lambda: self.set_zoom(self.zoom_percent - 10))
        self.btn_close.clicked.connect(self.close)

        actions = QHBoxLayout()
        actions.setContentsMargins(10, 5, 10, 5)
        actions.setSpacing(6)
        actions.addWidget(self.btn_translate)
        actions.addWidget(self.btn_recapture)
        actions.addWidget(self.btn_save)
        actions.addWidget(self.btn_copy)
        actions.addStretch()
        actions.addWidget(self.btn_zoom_out)
        actions.addWidget(self.zoom_label)
        actions.addWidget(self.btn_zoom_in)
        actions.addWidget(self.btn_close)

        # 功能按键底部容器
        bottom_bar = QWidget()
        bottom_bar.setObjectName("bottomBar")
        bottom_bar.setLayout(actions)
        bottom_bar.setStyleSheet("""
            #bottomBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2d333b, stop:1 #22272e);
                border-top: 1px solid #444c56;
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
            }
            QPushButton {
                background: #373e47;
                color: #adbac7;
                border: 1px solid #444c56;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #444c56;
                color: #cdd9e5;
                border: 1px solid #768390;
            }
            QPushButton#closeBtn {
                background: #da3633;
                color: white;
            }
        """)

        image_wrap = QWidget()
        image_layout = QVBoxLayout(image_wrap)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.addWidget(self.image_label)

        self.size_grip = QSizeGrip(image_wrap)
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 0, 0)
        grip_row.addStretch()
        grip_row.addWidget(self.size_grip)
        image_layout.addLayout(grip_row)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(image_wrap)
        root.addWidget(bottom_bar)
        self.setLayout(root)

        self.setStyleSheet("""
            QWidget { background: #1c2128; border: 1px solid #444c56; border-radius: 10px; }
        """)

        self.resize(max(400, self.capture_pixmap.width() + 2), max(200, self.capture_pixmap.height() + 45))
        self._refresh_view()
        if top_left:
            self.move(top_left)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_view()

    def _recapture(self):
        self.request_recapture.emit()
        self.close()

    def set_zoom(self, value: int):
        self.zoom_percent = max(30, min(300, value))
        self.zoom_label.setText(f"{self.zoom_percent}%")
        self._refresh_view()

    def set_rendered_pixmap(self, pixmap: QPixmap):
        self.current_pixmap = pixmap
        self._refresh_view()

    def _refresh_view(self):
        if self.current_pixmap.isNull():
            return
        target_w = max(100, int(self.current_pixmap.width() * self.zoom_percent / 100))
        target_h = max(100, int(self.current_pixmap.height() * self.zoom_percent / 100))
        scaled = self.current_pixmap.scaled(
            QSize(target_w, target_h),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def _compose_pixmap(self) -> QPixmap:
        return QPixmap(self.current_pixmap)

    def _save_image(self):
        default_name = f"Capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        save_dir = os.path.join(os.path.expanduser("~"), "Pictures", "Screenshots")
        if self.parent_controller is not None:
            save_dir = self.parent_controller.config.save_dir or save_dir
        os.makedirs(save_dir, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "保存贴图", 
            os.path.join(save_dir, default_name), 
            "PNG 图片 (*.png)"
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        ok = self._compose_pixmap().save(path, "PNG")
        if ok:
            # 记录最后保存的目录（可选，这里保持配置目录）
            pass
        else:
            QMessageBox.critical(self, "保存失败", "文件保存失败，请检查路径权限。")

    def _copy_image(self):
        QApplication.clipboard().setPixmap(self._compose_pixmap())
        QMessageBox.information(self, "复制成功", "贴图已复制到剪贴板。")

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta > 0:
            self.set_zoom(self.zoom_percent + 10)
        elif delta < 0:
            self.set_zoom(self.zoom_percent - 10)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.drag_pos = None
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape or _hotkey_matches_event(event, self.cancel_hotkey):
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)


class HotkeyEdit(QLineEdit):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setObjectName("hotkeyEdit")
        self.setReadOnly(True)
        self.setPlaceholderText("点击并按下快捷键...")

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        
        if key == Qt.Key_Escape:
            self.clear()
            return
            
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return

        parts = []
        if modifiers & Qt.ControlModifier: parts.append("ctrl")
        if modifiers & Qt.ShiftModifier: parts.append("shift")
        if modifiers & Qt.AltModifier: parts.append("alt")
        
        # 转换键名
        key_str = QKeySequence(key).toString().lower()
        if key_str:
            parts.append(key_str)
            self.setText("+".join(parts))

class CollapsibleWidget(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.toggle_btn = QPushButton(f"▶ {title}")
        self.toggle_btn.setObjectName("collapsibleToggle")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(False)
        self.toggle_btn.setStyleSheet("text-align: left; padding: 6px 8px;")

        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_area.setVisible(False)

        self.layout.addWidget(self.toggle_btn)
        self.layout.addWidget(self.content_area)

        self.toggle_btn.clicked.connect(self.toggle)

    def toggle(self):
        checked = self.toggle_btn.isChecked()
        self.content_area.setVisible(checked)
        self.toggle_btn.setText(f"{'▼' if checked else '▶'} {self.toggle_btn.text()[2:]}")

class MainController(QObject):
    request_capture = Signal()

    def __init__(self, app: QApplication, config: AppConfig):
        super().__init__()
        self.app = app
        self.config = config

        self.ocr_engine = RapidOCR()
        self.client = None

        self.selector = None
        self.fullscreen_shot = None
        self.stickers = []
        self.hotkey_handler = None
        self.fetched_models = []

        self.request_capture.connect(self.capture_flow)
        self.theme_items = [("深色", "dark"), ("浅色", "light")]

        self.main_window = QMainWindow()
        self.main_window.setWindowTitle(APP_TITLE)
        self.main_window.resize(640, 360)

        center = QWidget()
        self.main_window.setCentralWidget(center)
        root = QVBoxLayout(center)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(15)

        title = QLabel(APP_TITLE)
        title.setObjectName("title")
        root.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        
        self.base_url_input = QLineEdit(self.config.base_url)
        self.api_key_input = QLineEdit(self.config.api_key)
        self.api_key_input.setEchoMode(QLineEdit.Password)
        
        self.model_input = QComboBox()
        self.model_input.setEditable(True)
        self.model_input.setInsertPolicy(QComboBox.NoInsert)
        self.model_input.addItems(self._normalized_model_list(self.config.model_list))
        self.model_input.setCurrentText(self.config.model)
        
        self.btn_fetch_models = QPushButton("获取")
        self.btn_add_model = QPushButton("添加")
        self.btn_remove_model = QPushButton("删除")

        self.provider_input = QComboBox()
        self.provider_input.setEditable(True)
        self.provider_input.setMinimumWidth(150)
        self.provider_input.setMaximumWidth(260)
        self.provider_input.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.provider_input.setMinimumContentsLength(18)
        self.provider_input.setToolTip("可输入自定义供应商名称")
        provider_names = [item.get("name", "") for item in self.config.providers if item.get("name")]
        if not provider_names:
            provider_names = ["OpenAI"]
        self.provider_input.addItems(provider_names)
        self.provider_input.setCurrentText(self.config.provider_name)
        self.provider_template_input = QComboBox()
        self.provider_template_input.addItems(list(PROVIDER_TEMPLATES.keys()))
        self.provider_template_input.setCurrentText(
            self.config.provider_template
            if self.config.provider_template in PROVIDER_TEMPLATES
            else "OpenAI"
        )
        self.btn_quick_add_template = QPushButton("模板建档")
        self.btn_provider_guide = QPushButton("配置指引")
        self.btn_export_providers = QPushButton("导出配置")
        self.btn_import_providers = QPushButton("导入配置")
        self.btn_rename_provider = QPushButton("重命名")
        self.btn_add_provider = QPushButton("新增")
        self.btn_remove_provider = QPushButton("移除")

        self.target_lang_input = QComboBox()
        self.target_lang_input.setEditable(True)
        common_langs = [
            "中文",
            "English",
            "日本語",
            "한국어",
            "Français",
            "Deutsch",
            "Español",
            "Português",
            "Русский",
            "Italiano",
            "Türkçe",
            "Tiếng Việt",
            "ไทย",
            "العربية",
            "Hindi",
        ]
        self.target_lang_input.addItems(common_langs)
        self.target_lang_input.setCurrentText(self.config.target_lang)
        self.hotkey_input = HotkeyEdit(self.config.hotkey)
        self.cancel_hotkey_input = HotkeyEdit(self.config.cancel_hotkey)
        self.theme_input = QComboBox()
        for label, value in self.theme_items:
            self.theme_input.addItem(label, value)
        
        # 待选列表折叠容器
        self.collapsible_models = CollapsibleWidget("点击展开待选模型列表")
        self.fetched_model_list = QListWidget()
        self.fetched_model_list.setSelectionMode(QListWidget.MultiSelection)
        self.fetched_model_list.setFixedHeight(120)
        self.collapsible_models.content_layout.addWidget(self.fetched_model_list)
        
        # 路径设置
        path_row = QWidget()
        path_layout = QHBoxLayout(path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        self.save_dir_input = QLineEdit(self.config.save_dir)
        self.btn_browse_dir = QPushButton("浏览")
        path_layout.addWidget(self.save_dir_input)
        path_layout.addWidget(self.btn_browse_dir)

        form.addRow("API 地址", self.base_url_input)
        form.addRow("API 密钥", self.api_key_input)

        provider_ops = QHBoxLayout()
        provider_ops.addWidget(self.provider_input)
        provider_ops.addWidget(self.btn_quick_add_template)
        provider_ops.addWidget(self.btn_provider_guide)
        provider_ops.addWidget(self.btn_export_providers)
        provider_ops.addWidget(self.btn_import_providers)
        provider_ops.addWidget(self.btn_rename_provider)
        provider_ops.addWidget(self.btn_add_provider)
        provider_ops.addWidget(self.btn_remove_provider)
        form.addRow("模型供应商", provider_ops)
        form.addRow("供应商模板", self.provider_template_input)
        self.provider_guide_label = QLabel("")
        self.provider_guide_label.setObjectName("hintLabel")
        self.provider_guide_label.setWordWrap(True)
        form.addRow("模板说明", self.provider_guide_label)
        
        model_ops = QHBoxLayout()
        model_ops.addWidget(self.model_input)
        model_ops.addWidget(self.btn_fetch_models)
        model_ops.addWidget(self.btn_add_model)
        model_ops.addWidget(self.btn_remove_model)
        form.addRow("模型管理", model_ops)
        form.addRow("待选列表", self.collapsible_models)
        
        form.addRow("目标语言", self.target_lang_input)
        form.addRow("界面主题", self.theme_input)
        form.addRow("截图热键", self.hotkey_input)
        form.addRow("退出热键", self.cancel_hotkey_input)
        form.addRow("保存目录", path_row)
        root.addLayout(form)

        self.status_label = QLabel("状态：就绪")
        self.status_label.setObjectName("statusLabel")
        root.addWidget(self.status_label)

        self.config_hint_label = QLabel()
        self.config_hint_label.setWordWrap(True)
        self.config_hint_label.setObjectName("hintLabel")
        root.addWidget(self.config_hint_label)

        btn_row = QHBoxLayout()
        self.btn_save = QPushButton("保存设置")
        self.btn_reset = QPushButton("恢复默认")
        self.btn_test = QPushButton("单模型测试")
        self.btn_test_batch = QPushButton("批量测试模型")
        self.btn_capture = QPushButton("开始截图")
        self.btn_capture.setObjectName("primaryBtn")
        
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_reset)
        btn_row.addWidget(self.btn_test)
        btn_row.addWidget(self.btn_capture)
        root.addLayout(btn_row)

        self.btn_save.clicked.connect(self.save_settings)
        self.btn_reset.clicked.connect(self.reset_settings)
        self.btn_test.clicked.connect(self.test_translate)
        self.btn_capture.clicked.connect(self.capture_flow)
        self.btn_fetch_models.clicked.connect(self.fetch_models)
        self.btn_add_model.clicked.connect(self.add_selected_models)
        self.btn_remove_model.clicked.connect(self.remove_current_model)
        self.btn_browse_dir.clicked.connect(self.browse_save_dir)
        self.btn_add_provider.clicked.connect(self.add_provider)
        self.btn_remove_provider.clicked.connect(self.remove_provider)
        self.btn_quick_add_template.clicked.connect(self.quick_add_provider_from_template)
        self.btn_provider_guide.clicked.connect(self.show_provider_guide_dialog)
        self.btn_export_providers.clicked.connect(self.export_providers_config)
        self.btn_import_providers.clicked.connect(self.import_providers_config)
        self.btn_rename_provider.clicked.connect(self.rename_current_provider)
        self.provider_input.currentTextChanged.connect(self.on_provider_changed)
        self.provider_template_input.currentTextChanged.connect(self.on_provider_template_changed)
        self.theme_input.currentIndexChanged.connect(self.on_theme_changed)

        if self.provider_input.lineEdit() is not None:
            self.provider_input.lineEdit().textChanged.connect(self._adjust_provider_text_font)

        tip = QLabel("使用方式：点击“开始截图”或按全局热键，框选区域后可确认翻译。")
        tip.setObjectName("hintLabel")
        root.addWidget(tip)

        self._apply_config_to_ui()
        self._apply_theme(self.config.theme)
        self._update_provider_ui_state()
        self._adjust_provider_text_font()

        self._init_tray()
        self._register_hotkey()
        self._refresh_status()

    def _init_tray(self):
        self.tray = QSystemTrayIcon(self.main_window)
        icon = self.main_window.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray.setIcon(icon)
        self.main_window.setWindowIcon(icon)
        self.tray.setToolTip(APP_TITLE)

        menu = QMenu()
        action_capture = QAction("立即截图", menu)
        action_capture.triggered.connect(self.capture_flow)
        menu.addAction(action_capture)

        action_show = QAction("显示主窗口", menu)
        action_show.triggered.connect(self.main_window.showNormal)
        menu.addAction(action_show)

        action_exit = QAction("退出", menu)
        action_exit.triggered.connect(self.shutdown)
        menu.addAction(action_exit)

        self.tray.setContextMenu(menu)
        self.tray.show()

    def _register_hotkey(self):
        try:
            if self.hotkey_handler is not None:
                keyboard.remove_hotkey(self.hotkey_handler)
                self.hotkey_handler = None
            self.hotkey_handler = keyboard.add_hotkey(
                self.config.hotkey, lambda: self.request_capture.emit()
            )
        except Exception as ex:
            QMessageBox.warning(self.main_window, "热键错误", str(ex))
        finally:
            self._refresh_status()

    def _rebuild_client(self):
        if not self._has_required_config(self.config):
            self.client = None
            return
        template = self._current_template(self.config)
        if template == "OpenAI":
            self.client = OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        else:
            self.client = None

    def _theme_stylesheet(self, theme: str) -> str:
        if theme == "light":
            return """
                QMainWindow { background-color: #f5f7fb; }
                QWidget { color: #1f2937; font-family: 'Microsoft YaHei UI'; }
                QLabel#title { color: #111827; font-size: 20px; font-weight: bold; margin-bottom: 10px; }
                QLabel#statusLabel { color: #374151; }
                QLabel#hintLabel { color: #6b7280; }
                QLineEdit, QComboBox, QListWidget {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    padding: 5px;
                    color: #111827;
                }
                QLineEdit#hotkeyEdit {
                    background-color: #e0e7ff;
                    color: #1e3a8a;
                    border: 1px solid #818cf8;
                    font-weight: 700;
                }
                QLineEdit#hotkeyEdit:focus {
                    background-color: #c7d2fe;
                    color: #1e3a8a;
                    border: 1px solid #4f46e5;
                }
                QPushButton {
                    background-color: #e5e7eb;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    padding: 6px 12px;
                    color: #111827;
                    font-weight: 600;
                }
                QPushButton:hover { background-color: #dbe2ea; border-color: #94a3b8; }
                QPushButton#primaryBtn { background-color: #2563eb; color: white; border-color: #1d4ed8; }
                QPushButton#primaryBtn:hover { background-color: #1d4ed8; }
                QPushButton#collapsibleToggle {
                    background-color: #e2e8f0;
                    color: #0f172a;
                    border: 1px solid #94a3b8;
                    font-weight: 700;
                }
                QPushButton#collapsibleToggle:hover {
                    background-color: #cbd5e1;
                    color: #020617;
                    border-color: #64748b;
                }
            """
        return """
            QMainWindow { background-color: #1c2128; }
            QWidget { color: #adbac7; font-family: 'Microsoft YaHei UI'; }
            QLabel#title { color: #cdd9e5; font-size: 20px; font-weight: bold; margin-bottom: 10px; }
            QLabel#statusLabel { color: #9ca3af; }
            QLabel#hintLabel { color: #7b8592; }
            QLineEdit, QComboBox, QListWidget {
                background-color: #22272e;
                border: 1px solid #444c56;
                border-radius: 6px;
                padding: 5px;
                color: #adbac7;
            }
            QLineEdit#hotkeyEdit {
                background-color: #1f2a44;
                color: #bfdbfe;
                border: 1px solid #3b82f6;
                font-weight: 700;
            }
            QLineEdit#hotkeyEdit:focus {
                background-color: #1e3a5f;
                color: #dbeafe;
                border: 1px solid #60a5fa;
            }
            QPushButton {
                background-color: #373e47;
                border: 1px solid #444c56;
                border-radius: 6px;
                padding: 6px 12px;
                color: #adbac7;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #444c56; border-color: #768390; }
            QPushButton#primaryBtn { background-color: #238636; color: white; border-color: #2ea043; }
            QPushButton#primaryBtn:hover { background-color: #2ea043; }
            QPushButton#collapsibleToggle {
                background-color: #2d333b;
                color: #cdd9e5;
                border: 1px solid #5a6673;
                font-weight: 700;
            }
            QPushButton#collapsibleToggle:hover {
                background-color: #3a444f;
                color: #f8fafc;
                border-color: #7d8b99;
            }
        """

    def _apply_theme(self, theme: str):
        if theme not in {"dark", "light"}:
            theme = "dark"
        self.main_window.setStyleSheet(self._theme_stylesheet(theme))

    def on_theme_changed(self, _):
        theme_value = self.theme_input.currentData()
        self._apply_theme(theme_value or "dark")

    def _update_provider_ui_state(self):
        template = self.provider_template_input.currentText().strip() or "OpenAI"
        supports_models = template == "OpenAI"
        self.btn_fetch_models.setEnabled(supports_models)
        self.fetched_model_list.setEnabled(supports_models)
        self.btn_add_model.setEnabled(supports_models)
        self.collapsible_models.toggle_btn.setEnabled(supports_models)
        if not supports_models:
            self.fetched_model_list.clear()
            self.collapsible_models.content_area.setVisible(False)
            self.collapsible_models.toggle_btn.setChecked(False)
        guide = PROVIDER_TEMPLATES.get(template, {}).get("guide", "")
        self.provider_guide_label.setText(guide)

    def browse_save_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self.main_window, "选择保存目录", self.save_dir_input.text())
        if dir_path:
            self.save_dir_input.setText(dir_path)

    def _normalize_providers(self, providers: list[dict]) -> list[dict]:
        result = []
        seen = set()
        for item in providers or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            result.append(
                {
                    "name": name,
                    "template": str(item.get("template", "OpenAI")).strip() or "OpenAI",
                    "base_url": str(item.get("base_url", "")).strip(),
                    "api_key": str(item.get("api_key", "")).strip(),
                }
            )
        if not result:
            result = [{"name": "OpenAI", "template": "OpenAI", "base_url": "https://api.openai.com/v1", "api_key": ""}]
        return result

    def _current_provider_entry(self, config: AppConfig):
        for item in config.providers:
            if item.get("name") == config.provider_name:
                return item
        return config.providers[0] if config.providers else {"name": "OpenAI", "template": "OpenAI", "base_url": config.base_url, "api_key": config.api_key}

    def _current_template(self, config: AppConfig) -> str:
        provider = self._current_provider_entry(config)
        template = str(provider.get("template", "OpenAI")).strip() or "OpenAI"
        if template not in PROVIDER_TEMPLATES:
            template = "OpenAI"
        return template

    def _provider_by_name(self, name: str):
        for item in self.config.providers:
            if item.get("name") == name:
                return item
        return None

    def add_provider(self):
        name = self.provider_input.currentText().strip()
        if not name:
            QMessageBox.information(self.main_window, "提示", "请先输入供应商名称。")
            return
        providers = self._normalize_providers(self.config.providers)
        if any(item.get("name") == name for item in providers):
            QMessageBox.information(self.main_window, "提示", "该供应商已存在。")
            return
        template = self.provider_template_input.currentText().strip() or "OpenAI"
        if template not in PROVIDER_TEMPLATES:
            template = "OpenAI"
        providers.append(
            {
                "name": name,
                "template": template,
                "base_url": self.base_url_input.text().strip() or PROVIDER_TEMPLATES[template]["default_url"],
                "api_key": self.api_key_input.text().strip(),
            }
        )
        self.config.providers = providers
        self.config.provider_name = name
        self.config.provider_template = providers[-1]["template"]
        self.provider_input.addItem(name)
        self.provider_input.setCurrentText(name)
        self._adjust_provider_text_font()
        self.status_label.setText(f"状态：已新增供应商 {name}")

    def rename_current_provider(self):
        index = self.provider_input.currentIndex()
        if index < 0:
            QMessageBox.information(self.main_window, "提示", "当前没有可重命名的供应商。")
            return

        old_name = self.provider_input.itemText(index).strip()
        new_name = self.provider_input.currentText().strip()
        if not new_name:
            QMessageBox.information(self.main_window, "提示", "供应商名称不能为空。")
            return
        if new_name == old_name:
            return

        existing = {self.provider_input.itemText(i).strip() for i in range(self.provider_input.count()) if i != index}
        if new_name in existing:
            QMessageBox.information(self.main_window, "提示", "名称已存在，请使用其他名称。")
            return

        for item in self.config.providers:
            if item.get("name") == old_name:
                item["name"] = new_name
                break
        if self.config.provider_name == old_name:
            self.config.provider_name = new_name

        self.provider_input.setItemText(index, new_name)
        self.provider_input.setCurrentText(new_name)
        self._adjust_provider_text_font()
        self.status_label.setText(f"状态：已将供应商重命名为 {new_name}")

    def quick_add_provider_from_template(self):
        template = self.provider_template_input.currentText().strip() or "OpenAI"
        if template not in PROVIDER_TEMPLATES:
            template = "OpenAI"

        providers = self._normalize_providers(self.config.providers)
        existing_names = {item.get("name", "") for item in providers}

        base_name = template
        name = base_name
        suffix = 2
        while name in existing_names:
            name = f"{base_name}-{suffix}"
            suffix += 1

        default_url = PROVIDER_TEMPLATES[template]["default_url"]
        provider = {
            "name": name,
            "template": template,
            "base_url": default_url,
            "api_key": "",
        }
        providers.append(provider)

        self.config.providers = providers
        self.config.provider_name = name
        self.config.provider_template = template

        self.provider_input.blockSignals(True)
        self.provider_input.clear()
        self.provider_input.addItems([item.get("name", "") for item in providers])
        self.provider_input.setCurrentText(name)
        self.provider_input.blockSignals(False)

        self.base_url_input.setText(default_url)
        self.api_key_input.setText("")
        self._update_provider_ui_state()
        self.status_label.setText(f"状态：已按模板创建供应商 {name}")

    def export_providers_config(self):
        providers = self._normalize_providers(self.config.providers)
        export_providers = []
        for item in providers:
            sanitized = dict(item)
            sanitized["api_key"] = ""
            export_providers.append(sanitized)
        default_name = f"providers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "导出供应商配置",
            os.path.join(self.config.save_dir or os.getcwd(), default_name),
            "JSON 文件 (*.json)",
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"

        payload = {
            "version": 1,
            "provider_name": self.provider_input.currentText().strip() or self.config.provider_name,
            "provider_template": self.provider_template_input.currentText().strip() or self.config.provider_template,
            "providers": export_providers,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self.status_label.setText(f"状态：供应商配置已导出到 {path}")
        QMessageBox.information(
            self.main_window,
            "导出成功",
            f"已导出到：\n{path}\n\n为保护隐私，导出文件中的 API Key 已清空。导入后请手动填写。",
        )

    def import_providers_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "导入供应商配置",
            self.config.save_dir or os.getcwd(),
            "JSON 文件 (*.json)",
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            imported_providers = self._normalize_providers(payload.get("providers", []))
            if not imported_providers:
                raise RuntimeError("文件中未找到有效的供应商配置。")

            provider_name = str(payload.get("provider_name", "")).strip()
            provider_template = str(payload.get("provider_template", "")).strip() or "OpenAI"
            if provider_template not in PROVIDER_TEMPLATES:
                provider_template = "OpenAI"

            existing_providers = self._normalize_providers(self.config.providers)
            has_local_data = any(
                p.get("name") != "OpenAI" or p.get("api_key") or p.get("base_url") != "https://api.openai.com/v1"
                for p in existing_providers
            )

            final_providers = imported_providers
            if has_local_data:
                msg = QMessageBox(self.main_window)
                msg.setWindowTitle("导入方式")
                msg.setIcon(QMessageBox.Question)
                msg.setText("检测到本地已有供应商配置，请选择导入方式：")
                btn_merge = msg.addButton("合并", QMessageBox.AcceptRole)
                btn_overwrite = msg.addButton("覆盖", QMessageBox.DestructiveRole)
                btn_cancel = msg.addButton("取消", QMessageBox.RejectRole)
                msg.exec()

                clicked = msg.clickedButton()
                if clicked == btn_cancel:
                    return
                if clicked == btn_merge:
                    merged = {item.get("name", ""): item for item in existing_providers}
                    for item in imported_providers:
                        merged[item.get("name", "")] = item
                    final_providers = self._normalize_providers(list(merged.values()))
                elif clicked == btn_overwrite:
                    final_providers = imported_providers
                else:
                    return

            names = [item.get("name", "") for item in final_providers]
            if provider_name not in names:
                provider_name = names[0]

            self.config.providers = final_providers
            self.config.provider_name = provider_name
            current_entry = next((x for x in final_providers if x.get("name") == provider_name), final_providers[0])
            self.config.provider_template = current_entry.get("template", provider_template)
            if self.config.provider_template not in PROVIDER_TEMPLATES:
                self.config.provider_template = "OpenAI"
            self.config.base_url = current_entry.get("base_url", "") or PROVIDER_TEMPLATES[self.config.provider_template]["default_url"]
            self.config.api_key = current_entry.get("api_key", "")

            self._apply_config_to_ui()
            self._rebuild_client()
            ConfigStore.save(self.config)
            self.status_label.setText(f"状态：已导入供应商配置（{len(final_providers)} 个）")
            QMessageBox.information(self.main_window, "导入成功", f"已导入 {len(final_providers)} 个供应商。")
        except Exception as ex:
            QMessageBox.critical(self.main_window, "导入失败", f"读取或解析失败：{ex}")

    def remove_provider(self):
        name = self.provider_input.currentText().strip()
        providers = self._normalize_providers(self.config.providers)
        if len(providers) <= 1:
            QMessageBox.information(self.main_window, "提示", "至少保留一个供应商。")
            return
        providers = [item for item in providers if item.get("name") != name]
        self.config.providers = providers
        self.provider_input.clear()
        self.provider_input.addItems([item.get("name", "") for item in providers])
        self.provider_input.setCurrentIndex(0)
        self.on_provider_changed(self.provider_input.currentText())
        self._adjust_provider_text_font()
        self.status_label.setText(f"状态：已移除供应商 {name}")

    def on_provider_changed(self, name: str):
        item = self._provider_by_name(name.strip())
        if not item:
            return
        self.base_url_input.setText(item.get("base_url", ""))
        self.api_key_input.setText(item.get("api_key", ""))
        template = item.get("template", "OpenAI")
        if template not in PROVIDER_TEMPLATES:
            template = "OpenAI"
        self.provider_template_input.blockSignals(True)
        self.provider_template_input.setCurrentText(template)
        self.provider_template_input.blockSignals(False)
        self._update_provider_ui_state()
        self._adjust_provider_text_font()

    def _adjust_provider_text_font(self):
        line_edit = self.provider_input.lineEdit()
        if line_edit is None:
            return

        text = (line_edit.text() or self.provider_input.currentText() or "").strip()
        if not text:
            return

        if not hasattr(self, "_provider_base_font"):
            self._provider_base_font = QFont(line_edit.font())

        base_font = QFont(self._provider_base_font)
        size = max(9.0, base_font.pointSizeF() if base_font.pointSizeF() > 0 else 10.0)
        available = max(80, line_edit.width() - 14)

        fitted = QFont(base_font)
        while size >= 8.0:
            fitted.setPointSizeF(size)
            if QFontMetrics(fitted).horizontalAdvance(text) <= available:
                break
            size -= 0.5

        line_edit.setFont(fitted)

    def on_provider_template_changed(self, template: str):
        template = (template or "OpenAI").strip()
        if template not in PROVIDER_TEMPLATES:
            return
        default_url = PROVIDER_TEMPLATES[template]["default_url"]
        current_url = self.base_url_input.text().strip()
        if not current_url or current_url in [v["default_url"] for v in PROVIDER_TEMPLATES.values()]:
            self.base_url_input.setText(default_url)
        name = self.provider_input.currentText().strip()
        for item in self.config.providers:
            if item.get("name") == name:
                item["template"] = template
                item["base_url"] = self.base_url_input.text().strip() or default_url
                item["api_key"] = self.api_key_input.text().strip()
                break
        self._update_provider_ui_state()

    def show_provider_guide_dialog(self):
        template = self.provider_template_input.currentText().strip() or "OpenAI"
        meta = PROVIDER_TEMPLATES.get(template, PROVIDER_TEMPLATES["OpenAI"])
        requires = "需要" if meta.get("requires_api_key", True) else "可选"
        tips = [
            f"模板：{template}",
            f"默认地址：{meta.get('default_url', '')}",
            f"API Key：{requires}",
            f"说明：{meta.get('guide', '')}",
        ]
        if template == "OpenAI":
            tips.append("建议：先点击“获取”拉取模型，再把可用模型添加到列表。")
        elif template == "DeepL":
            tips.append("建议：目标语言优先使用标准代码，如 ZH/EN/JA。")
        else:
            tips.append("建议：先确认服务可访问，再进行翻译测试。")
        QMessageBox.information(self.main_window, "供应商配置指引", "\n".join(tips))

    def _read_ui_config(self) -> AppConfig:
        providers = self._normalize_providers(self.config.providers)
        current_provider = self.provider_input.currentText().strip() or providers[0]["name"]
        current_template = self.provider_template_input.currentText().strip() or "OpenAI"
        if current_template not in PROVIDER_TEMPLATES:
            current_template = "OpenAI"
        existing = None
        for item in providers:
            if item["name"] == current_provider:
                existing = item
                break
        if existing is None:
            existing = {"name": current_provider, "template": current_template, "base_url": "", "api_key": ""}
            providers.append(existing)
        existing["template"] = current_template
        default_url = PROVIDER_TEMPLATES[current_template]["default_url"]
        existing["base_url"] = self.base_url_input.text().strip() or default_url
        existing["api_key"] = self.api_key_input.text().strip()

        models = self._normalized_model_list(
            [self.model_input.itemText(i) for i in range(self.model_input.count())]
        )
        current_model = self.model_input.currentText().strip() or (models[0] if models else "gpt-4o-mini")
        if current_model not in models:
            models.insert(0, current_model)
        return AppConfig(
            hotkey=self.hotkey_input.text().strip() or "ctrl+shift+q",
            cancel_hotkey=self.cancel_hotkey_input.text().strip() or "esc",
            provider_name=current_provider,
            provider_template=current_template,
            providers=providers,
            model=current_model,
            model_list=models,
            base_url=existing["base_url"],
            api_key=existing["api_key"],
            target_lang=self.target_lang_input.currentText().strip() or "中文",
            save_dir=self.save_dir_input.text().strip(),
            theme=self.theme_input.currentData() or "dark",
        )

    def _apply_config_to_ui(self):
        self.base_url_input.setText(self.config.base_url)
        self.api_key_input.setText(self.config.api_key)
        providers = self._normalize_providers(self.config.providers)
        self.provider_input.blockSignals(True)
        self.provider_input.clear()
        self.provider_input.addItems([item.get("name", "") for item in providers])
        self.provider_input.setCurrentText(self.config.provider_name)
        self.provider_input.blockSignals(False)
        self._adjust_provider_text_font()
        self.provider_template_input.blockSignals(True)
        self.provider_template_input.setCurrentText(
            self.config.provider_template if self.config.provider_template in PROVIDER_TEMPLATES else "OpenAI"
        )
        self.provider_template_input.blockSignals(False)
        models = self._normalized_model_list(self.config.model_list)
        self.model_input.clear()
        self.model_input.addItems(models)
        self.model_input.setCurrentText(self.config.model)
        self.fetched_model_list.clear()
        self.target_lang_input.setCurrentText(self.config.target_lang)
        self.hotkey_input.setText(self.config.hotkey)
        self.cancel_hotkey_input.setText(self.config.cancel_hotkey)
        self.save_dir_input.setText(self.config.save_dir)
        theme_index = max(0, self.theme_input.findData(self.config.theme))
        self.theme_input.blockSignals(True)
        self.theme_input.setCurrentIndex(theme_index)
        self.theme_input.blockSignals(False)
        self._apply_theme(self.theme_input.currentData() or "dark")
        self._update_provider_ui_state()

    def _normalized_model_list(self, models: list[str]) -> list[str]:
        result = []
        seen = set()
        for raw in models or []:
            model = str(raw).strip()
            if not model or model in seen:
                continue
            seen.add(model)
            result.append(model)
        if not result:
            result = ["gpt-4o-mini"]
        return result

    def _sync_model_combo(self, models: list[str], keep_current: bool = True):
        models = self._normalized_model_list(models)
        current = self.model_input.currentText().strip()
        self.model_input.blockSignals(True)
        self.model_input.clear()
        self.model_input.addItems(models)
        if keep_current and current in models:
            self.model_input.setCurrentText(current)
        else:
            self.model_input.setCurrentIndex(0)
        self.model_input.blockSignals(False)

    def add_selected_models(self):
        selected = self.fetched_model_list.selectedItems()
        if not selected:
            QMessageBox.information(self.main_window, "提示", "请先在“获取到的模型”里选择要添加的模型。")
            return
        current_models = [self.model_input.itemText(i) for i in range(self.model_input.count())]
        current_models.extend(item.text().strip() for item in selected)
        self._sync_model_combo(current_models)
        self.status_label.setText(f"状态：已添加 {len(selected)} 个模型到可用列表")

    def remove_current_model(self):
        current = self.model_input.currentText().strip()
        models = [self.model_input.itemText(i) for i in range(self.model_input.count())]
        if len(models) <= 1:
            QMessageBox.information(self.main_window, "提示", "至少保留一个模型。")
            return
        models = [m for m in models if m != current]
        self._sync_model_combo(models, keep_current=False)
        self.status_label.setText("状态：已从可用列表删除当前模型")

    def _create_client(self, config: AppConfig) -> OpenAI:
        return OpenAI(api_key=config.api_key, base_url=config.base_url)

    def _fetch_model_ids(self, client: OpenAI):
        resp = client.models.list()
        data = getattr(resp, "data", [])
        ids = sorted({item.id for item in data if getattr(item, "id", None)})
        return ids

    def _has_required_config(self, config: AppConfig) -> bool:
        template = self._current_template(config)
        key_ok = bool(config.api_key.strip()) if PROVIDER_TEMPLATES.get(template, {}).get("requires_api_key", True) else True
        return bool(
            config.base_url.strip()
            and key_ok
            and config.model.strip()
            and self._normalized_model_list(config.model_list)
        )

    def _has_connection_config(self, config: AppConfig) -> bool:
        return bool(config.base_url.strip() and config.api_key.strip())

    def _validate_config(self, config: AppConfig):
        template = self._current_template(config)
        if not config.base_url.strip():
            raise RuntimeError("请在软件中填写 OpenAI Base URL。")
        if PROVIDER_TEMPLATES.get(template, {}).get("requires_api_key", True) and not config.api_key.strip():
            raise RuntimeError("请在软件中填写 OpenAI API Key。")
        if not config.model.strip():
            raise RuntimeError("请在软件中填写模型名称。")
        if not self._normalized_model_list(config.model_list):
            raise RuntimeError("请至少添加一个模型。")
        parsed = urlparse(config.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError("OpenAI Base URL 格式不正确，请填写完整地址，例如 https://api.openai.com/v1")

    def _refresh_status(self):
        if self._has_required_config(self.config):
            masked_key = f"{self.config.api_key[:6]}..." if len(self.config.api_key) > 6 else "已填写"
            self.status_label.setText(f"状态：配置已保存，热键 {self.config.hotkey}")
            self.config_hint_label.setText(
                f"当前配置：{self.config.model} | {self.config.target_lang} | 截图:{self.config.hotkey} 退出:{self.config.cancel_hotkey} | {masked_key}"
            )
            self.btn_test.setEnabled(True)
            self.btn_test_batch.setEnabled(True)
            self.btn_capture.setEnabled(True)
            self.btn_fetch_models.setEnabled(True)
        else:
            self.status_label.setText("状态：请先在软件内填写接口配置")
            self.config_hint_label.setText(
                "请在本窗口填写 Base URL、API Key 和模型名称，点击“保存设置”后即可直接测试或截图翻译。"
            )
            self.btn_test.setEnabled(False)
            self.btn_test_batch.setEnabled(False)
            self.btn_capture.setEnabled(False)
            self.btn_fetch_models.setEnabled(self._has_connection_config(self.config))
        self._update_provider_ui_state()

    def fetch_models(self):
        try:
            temp_config = self._read_ui_config()
            template = self._current_template(temp_config)
            if template != "OpenAI":
                QMessageBox.information(
                    self.main_window,
                    "提示",
                    "当前模板不支持模型列表接口，请手动在“模型管理”中输入模型名称。",
                )
                self.fetched_model_list.clear()
                return
            if not temp_config.base_url.strip() or not temp_config.api_key.strip():
                raise RuntimeError("请先填写 Base URL 和 API Key，再获取模型。")
            parsed = urlparse(temp_config.base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise RuntimeError("Base URL 格式不正确。")

            client = self._create_client(temp_config)
            model_ids = self._fetch_model_ids(client)
            if not model_ids:
                raise RuntimeError("接口没有返回可用模型。")

            self.fetched_models = model_ids
            self.fetched_model_list.clear()
            self.fetched_model_list.addItems(model_ids)

            QMessageBox.information(
                self.main_window,
                "获取成功",
                f"已获取 {len(model_ids)} 个模型，请在列表中手动选择后点击“添加”。",
            )
            self.status_label.setText(f"状态：已获取 {len(model_ids)} 个模型")
        except Exception as ex:
            QMessageBox.critical(self.main_window, "获取模型失败", self._format_api_error(ex))

    def _format_api_error(self, ex: Exception) -> str:
        message = str(ex).strip() or ex.__class__.__name__
        lower = message.lower()
        if "image.png" in lower or "does not support image input" in lower:
            return (
                "当前接口把这次请求当成了图片输入，但你选择的模型不支持图片。"
                "请在软件里检查模型名称和 Base URL，优先使用支持文本对话的 OpenAI 兼容模型。"
            )
        if "401" in lower or "invalid api key" in lower or "incorrect api key" in lower:
            return "API Key 无效，请在软件里重新填写后保存。"
        if ("404" in lower) or ("model" in lower and "not found" in lower):
            return "模型名称不存在，请在软件里检查模型名称是否与接口服务商提供的一致。"
        if "timeout" in lower:
            return "请求超时，请检查网络连接，或稍后重试。"
        if "connection" in lower or "dns" in lower or "name resolution" in lower:
            return "无法连接到接口地址，请检查 Base URL 是否正确、网络是否可用。"
        return f"接口调用失败：{message}"

    def save_settings(self):
        try:
            new_config = self._read_ui_config()
            self._validate_config(new_config)
            self.config = new_config
            ConfigStore.save(self.config)
            self._rebuild_client()
            self._register_hotkey()
            QMessageBox.information(self.main_window, "成功", "设置已保存。")
        except Exception as ex:
            QMessageBox.critical(self.main_window, "保存失败", str(ex))
            self._refresh_status()

    def reset_settings(self):
        self.config = AppConfig()
        self._apply_config_to_ui()
        self._refresh_status()

    def test_translate(self):
        try:
            self.config = self._read_ui_config()
            self._validate_config(self.config)
            self._rebuild_client()
            text = self._translate("Hello world, this is a translation test.")
            QMessageBox.information(self.main_window, "测试成功", f"返回：{text}")
        except Exception as ex:
            QMessageBox.critical(self.main_window, "测试失败", self._format_api_error(ex))
        finally:
            self._refresh_status()

    def test_translate_batch(self):
        try:
            self.config = self._read_ui_config()
            if not self._has_connection_config(self.config):
                raise RuntimeError("请先填写 Base URL 和 API Key。")
            client = self._create_client(self.config)

            model_ids = self._normalized_model_list(self.config.model_list)
            if not model_ids:
                raise RuntimeError("没有可测试的模型。")

            ok_models = []
            failed_models = []
            sample = "Translate this sentence to Chinese: Hello world"

            QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
            for model_id in model_ids:
                try:
                    resp = client.chat.completions.create(
                        model=model_id,
                        messages=[{"role": "user", "content": sample}],
                        temperature=0.1,
                    )
                    text = (resp.choices[0].message.content or "").strip()
                    if text:
                        ok_models.append(model_id)
                    else:
                        failed_models.append((model_id, "返回为空"))
                except Exception as ex:
                    failed_models.append((model_id, self._format_api_error(ex)))
            QApplication.restoreOverrideCursor()

            lines = [f"总数：{len(model_ids)}", f"成功：{len(ok_models)}", f"失败：{len(failed_models)}"]
            if ok_models:
                lines.append("\n成功模型（前20个）：")
                lines.extend(ok_models[:20])
            if failed_models:
                lines.append("\n失败模型（前20个）：")
                for model_id, err in failed_models[:20]:
                    lines.append(f"- {model_id}: {err}")
            QMessageBox.information(self.main_window, "批量测试结果", "\n".join(lines))
        except Exception as ex:
            QMessageBox.critical(self.main_window, "批量测试失败", self._format_api_error(ex))
        finally:
            QApplication.restoreOverrideCursor()
            self._refresh_status()

    def show(self):
        self.main_window.show()

    def shutdown(self):
        try:
            if self.hotkey_handler is not None:
                keyboard.remove_hotkey(self.hotkey_handler)
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self.app.quit()

    def capture_flow(self):
        try:
            self.config = self._read_ui_config()
            self._validate_config(self.config)
            self._rebuild_client()
        except Exception as ex:
            QMessageBox.information(self.main_window, "请先完成设置", str(ex))
            self.main_window.showNormal()
            self.main_window.activateWindow()
            self._refresh_status()
            return

        screen = QGuiApplication.primaryScreen()
        if not screen:
            QMessageBox.critical(None, "错误", "未找到可用屏幕。")
            return

        self.fullscreen_shot = screen.grabWindow(0)
        self.selector = RegionSelector(self.fullscreen_shot, self.config.cancel_hotkey)
        self.selector.region_selected.connect(self._on_region_selected)
        self.selector.canceled.connect(lambda: None)
        self.selector.show()

    def _on_region_selected(self, rect: QRect):
        if self.fullscreen_shot is None:
            return

        dpr = self.fullscreen_shot.devicePixelRatio()
        if dpr and dpr != 1.0:
            px_rect = QRect(
                int(rect.x() * dpr),
                int(rect.y() * dpr),
                int(rect.width() * dpr),
                int(rect.height() * dpr),
            )
            cropped = QPixmap.fromImage(self.fullscreen_shot.copy(px_rect).toImage())
            cropped.setDevicePixelRatio(1.0)
        else:
            cropped = self.fullscreen_shot.copy(rect)
            cropped.setDevicePixelRatio(1.0)

        sticker = CaptureStickerWindow(cropped, rect.topLeft(), self.config.cancel_hotkey)
        sticker.parent_controller = self # 注入以便访问配置
        sticker.request_translate.connect(self._translate_sticker)
        sticker.request_recapture.connect(self.capture_flow)
        sticker.show()
        sticker.activateWindow()
        sticker.setFocus()
        self.stickers.append(sticker)

    def _translate_sticker(self, sticker: CaptureStickerWindow):
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            regions = self._ocr_regions(sticker.capture_pixmap)
            if not regions:
                QMessageBox.information(None, "提示", "OCR 未识别到文本。")
                return

            source_lines = [text for _, text in regions]
            translated_lines = self._translate_lines(source_lines)
            rendered = self._render_translation_on_image(
                sticker.capture_pixmap,
                [rect for rect, _ in regions],
                translated_lines,
            )
            sticker.set_rendered_pixmap(rendered)
        except Exception as ex:
            QMessageBox.critical(None, "翻译失败", self._format_api_error(ex))
        finally:
            QApplication.restoreOverrideCursor()

    def _ocr_regions(self, pixmap: QPixmap) -> list[tuple[QRectF, str]]:
        ba = QByteArray()
        buffer_device = QBuffer(ba)
        buffer_device.open(QIODevice.WriteOnly)
        pixmap.save(buffer_device, "PNG")

        pil_img = Image.open(io.BytesIO(ba.data())).convert("RGB")
        arr = np.array(pil_img)

        result, _ = self.ocr_engine(arr)
        if not result:
            return []

        regions = []
        for item in result:
            if len(item) >= 2:
                text = self._sanitize_ocr_text(str(item[1]))
                if not text:
                    continue
                rect = self._ocr_box_to_rect(item[0])
                if rect.width() < 2 or rect.height() < 2:
                    continue
                regions.append((rect, text))
        return regions

    def _sanitize_ocr_text(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text or "").strip()
        if not cleaned:
            return ""

        tokens = []
        for token in cleaned.split(" "):
            t = token.strip()
            if not t:
                continue
            if re.fullmatch(r"[\W_]+", t):
                continue
            if len(t) == 1 and t.isascii() and t.upper() not in {"A", "I"} and not t.isdigit():
                continue
            tokens.append(t)

        cleaned = " ".join(tokens).strip()
        if not cleaned:
            return ""
        if len(cleaned) == 1 and cleaned.isascii() and cleaned.upper() not in {"A", "I"}:
            return ""
        return cleaned

    def _ocr_box_to_rect(self, box) -> QRectF:
        if not box:
            return QRectF()
        xs = []
        ys = []
        for point in box:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                xs.append(float(point[0]))
                ys.append(float(point[1]))
        if not xs or not ys:
            return QRectF()
        
        # 针对 OCR 返回的坐标做缩放补偿（如果图像被强制设为 DPR=1.0）
        left = min(xs)
        top = min(ys)
        right = max(xs)
        bottom = max(ys)
        return QRectF(left, top, max(1.0, right - left), max(1.0, bottom - top))

    def _translate_lines(self, lines: list[str]) -> list[str]:
        if not lines:
            return []
        template = self._current_template(self.config)

        if template == "DeepL":
            return self._translate_lines_deepl(lines)
        if template in {"LibreTranslate", "Argos Translate"}:
            return self._translate_lines_libre(lines)
        if not self.client:
            raise RuntimeError("请先在软件中保存完整的接口配置。")

        glossary = {
            "Runtime": "运行时",
            "Interface": "接口",
            "Backend": "后端",
            "Frontend": "前端",
            "API": "API",
            "SDK": "SDK",
            "Link": "链接",
        }
        payload = json.dumps(
            {"target_lang": self.config.target_lang, "lines": lines, "glossary": glossary},
            ensure_ascii=False,
        )
        prompt = (
            "You are a UI localization translator. Translate each line in the JSON payload. "
            "Strict rules: (1) return ONLY a JSON array of strings; "
            "(2) keep same order and same length as input lines; "
            "(3) use glossary terms first when applicable; "
            "(4) remove OCR noise characters and meaningless isolated symbols/letters; "
            "(5) keep technical style concise, no explanations. "
            f"Payload: {payload}"
        )

        resp = self.client.chat.completions.create(
            model=self.config.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        content = (resp.choices[0].message.content or "").strip()
        content = self._extract_json_array_text(content)

        try:
            arr = json.loads(content)
            if isinstance(arr, list):
                out = [str(x).strip() for x in arr]
                if len(out) == len(lines):
                    return out
        except Exception:
            pass

        fallback = [seg.strip() for seg in content.splitlines() if seg.strip()]
        if len(fallback) == len(lines):
            return fallback

        return [content or src for src in lines]

    def _normalize_lang_code(self, lang: str) -> str:
        raw = (lang or "").strip().lower()
        mapping = {
            "中文": "zh",
            "english": "en",
            "日本語": "ja",
            "한국어": "ko",
            "français": "fr",
            "deutsch": "de",
            "español": "es",
            "português": "pt",
            "русский": "ru",
            "italiano": "it",
            "türkçe": "tr",
            "tiếng việt": "vi",
            "ไทย": "th",
            "العربية": "ar",
            "hindi": "hi",
        }
        if raw in mapping:
            return mapping[raw]
        if re.fullmatch(r"[a-z]{2}(-[a-z]{2})?", raw):
            return raw
        return "zh"

    def _post_json(self, url: str, payload: dict, headers: dict | None = None) -> dict:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)
        req = urlrequest.Request(url, data=body, headers=req_headers, method="POST")
        try:
            with urlrequest.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
                return json.loads(text) if text else {}
        except urlerror.HTTPError as ex:
            detail = ex.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {ex.code}: {detail or ex.reason}")
        except urlerror.URLError as ex:
            raise RuntimeError(f"网络错误: {ex.reason}")

    def _translate_lines_deepl(self, lines: list[str]) -> list[str]:
        if not self.config.api_key.strip():
            raise RuntimeError("DeepL 需要 API Key。")
        target = self._normalize_lang_code(self.config.target_lang).upper()
        if target == "ZH":
            target = "ZH"
        url = self.config.base_url.rstrip("/") + "/translate"
        data = urlparse_lib.urlencode(
            [("text", line) for line in lines] + [("target_lang", target)]
        ).encode("utf-8")
        req = urlrequest.Request(
            url,
            data=data,
            headers={"Authorization": f"DeepL-Auth-Key {self.config.api_key}"},
            method="POST",
        )
        try:
            with urlrequest.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
        except urlerror.HTTPError as ex:
            detail = ex.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"DeepL 调用失败: HTTP {ex.code} {detail}")
        translations = payload.get("translations", []) if isinstance(payload, dict) else []
        out = [str(item.get("text", "")).strip() for item in translations if isinstance(item, dict)]
        if len(out) == len(lines):
            return out
        return out + lines[len(out):]

    def _translate_lines_libre(self, lines: list[str]) -> list[str]:
        source = "auto"
        target = self._normalize_lang_code(self.config.target_lang)
        url = self.config.base_url.rstrip("/") + "/translate"
        out = []
        for line in lines:
            payload = {"q": line, "source": source, "target": target, "format": "text"}
            if self.config.api_key.strip():
                payload["api_key"] = self.config.api_key.strip()
            resp = self._post_json(url, payload)
            text = str(resp.get("translatedText", "")).strip()
            out.append(text or line)
        return out

    def _extract_json_array_text(self, content: str) -> str:
        body = (content or "").strip()
        if body.startswith("```"):
            body = body.strip("`")
            body = body.replace("json", "", 1).strip()
        match = re.search(r"\[[\s\S]*\]", body)
        if match:
            return match.group(0).strip()
        return body

    def _render_translation_on_image(self, src: QPixmap, boxes: list[QRectF], lines: list[str]) -> QPixmap:
        out = QPixmap(src)
        painter = QPainter(out)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        src_img = src.toImage()

        count = min(len(boxes), len(lines))
        for idx in range(count):
            rect = self._normalized_rect(boxes[idx], src_img.width(), src_img.height())
            text = lines[idx].strip()
            if not text:
                continue

            fill_color = self._sample_box_background_color(src_img, rect)
            bg = QPainterPath()
            bg.addRoundedRect(rect, 2, 2)
            painter.fillPath(bg, fill_color)
            painter.setPen(QColor(20, 20, 20))

            text_rect = rect.adjusted(2, 1, -2, -1)
            self._draw_text_fit(painter, text_rect, text, vertical_center=True)

        painter.end()
        return out

    def _normalized_rect(self, rect: QRectF, img_w: int, img_h: int) -> QRectF:
        left = max(0.0, min(rect.left(), img_w - 1.0))
        top = max(0.0, min(rect.top(), img_h - 1.0))
        right = max(left + 1.0, min(rect.right(), img_w - 1.0))
        bottom = max(top + 1.0, min(rect.bottom(), img_h - 1.0))
        return QRectF(left, top, right - left, bottom - top)

    def _sample_box_background_color(self, image, rect: QRectF) -> QColor:
        if image.isNull():
            return QColor(248, 248, 248, 245)
        w = image.width()
        h = image.height()

        left = max(0, int(rect.left()))
        top = max(0, int(rect.top()))
        right = min(w - 1, int(rect.right()))
        bottom = min(h - 1, int(rect.bottom()))
        cx = int(rect.center().x())
        cy = int(rect.center().y())

        sample_points = [
            (cx, max(top, cy - 2)),
            (cx, min(bottom, cy + 2)),
            (max(left, cx - 2), cy),
            (min(right, cx + 2), cy),
        ]

        samples = []
        for x, y in sample_points:
            x = min(max(0, x), w - 1)
            y = min(max(0, y), h - 1)
            samples.append(image.pixelColor(x, y))

        if not samples:
            return QColor(248, 248, 248, 245)

        base = QColor(
            int(sum(c.red() for c in samples) / len(samples)),
            int(sum(c.green() for c in samples) / len(samples)),
            int(sum(c.blue() for c in samples) / len(samples)),
        )

        return QColor(base.red(), base.green(), base.blue(), 242)

    def _draw_text_fit(self, painter: QPainter, rect: QRectF, text: str, vertical_center: bool = False):
        if rect.width() < 12 or rect.height() < 12:
            return

        min_size = 9
        max_size = min(28, max(10, int(rect.height() * 0.88)))
        font_size = max_size

        while font_size >= min_size:
            font = QFont("Microsoft YaHei UI", font_size)
            font.setLetterSpacing(QFont.PercentageSpacing, 104)
            painter.setFont(font)

            doc = QTextDocument()
            doc.setDefaultFont(font)
            doc.setDocumentMargin(0)
            doc.setTextWidth(rect.width())
            safe_text = html.escape(text)
            doc.setHtml(f"<div style='line-height:1.22'>{safe_text}</div>")
            if doc.size().height() <= rect.height() + 0.5:
                draw_y = rect.top()
                if vertical_center:
                    draw_y = rect.top() + (rect.height() - doc.size().height()) / 2.0
                painter.save()
                painter.translate(rect.left(), draw_y)
                clip = QRectF(0, 0, rect.width(), rect.height())
                doc.drawContents(painter, clip)
                painter.restore()
                return
            font_size -= 1

        font = QFont("Microsoft YaHei UI", min_size)
        font.setLetterSpacing(QFont.PercentageSpacing, 102)
        painter.setFont(font)
        align = Qt.AlignLeft | (Qt.AlignVCenter if vertical_center else Qt.AlignTop)
        painter.drawText(rect, Qt.TextWordWrap | align, text)

    def _translate(self, text: str) -> str:
        if not self.client:
            raise RuntimeError("请先在软件中保存完整的接口配置。")

        # 极端简化：不使用 system prompt，只发一句话
        # 很多劣质中转网关处理多消息 (system+user) 时会崩溃
        prompt = f"Translate the following text to {self.config.target_lang}, only output translation: {text}"

        try:
            resp = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            print(f"API Error: {e}")
            raise e

def main():
    app = QApplication(sys.argv)
    cfg = ConfigStore.load()
    controller = MainController(app, cfg)
    controller.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
