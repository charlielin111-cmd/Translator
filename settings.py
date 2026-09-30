"""設定對話框：快捷鍵、字體大小、浮窗停留秒數。"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QKeySequenceEdit, QLabel,
                               QMessageBox, QSpinBox, QVBoxLayout)

from config import Config
from hotkey import parse_hotkey

_QT_TO_SPEC = {"meta": "win", "return": "enter", "control": "ctrl"}
_SPEC_TO_QT = {"win": "Meta", "enter": "Return", "esc": "Esc"}


def qt_to_spec(text: str) -> str:
    """Qt 的 'Ctrl+Shift+Q' → 設定檔格式 'ctrl+shift+q'。"""
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    if text.endswith("++"):                      # 主鍵是 '+' 本身
        parts = [p.strip().lower() for p in text[:-2].split("+") if p.strip()] + ["+"]
    return "+".join(_QT_TO_SPEC.get(p, p) for p in parts)


def spec_to_qt(spec: str) -> str:
    """設定檔格式 'alt+`' → Qt 的 'Alt+`'（給 QKeySequenceEdit 顯示）。"""
    parts = [p.strip() for p in spec.split("+") if p.strip()]
    return "+".join(_SPEC_TO_QT.get(p.lower(), p.capitalize() if len(p) > 1 else p.upper())
                    for p in parts)


class SettingsDialog(QDialog):
    def __init__(self, cfg: Config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HotkeyDict 設定")
        self._cfg = cfg

        self.hotkey_edit = QKeySequenceEdit(QKeySequence.fromString(spec_to_qt(cfg.hotkey)))
        self.hotkey_edit.setMaximumSequenceLength(1)
        self.font_spin = QSpinBox()
        self.font_spin.setRange(10, 28)
        self.font_spin.setSuffix(" pt")
        self.font_spin.setValue(cfg.font_size)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(0, 120)
        self.timeout_spin.setSuffix(" 秒")
        self.timeout_spin.setSpecialValueText("不自動關閉")
        self.timeout_spin.setValue(cfg.popup_timeout_sec)

        form = QFormLayout()
        form.addRow("快捷鍵（點一下後直接按下組合鍵）", self.hotkey_edit)
        form.addRow("浮窗字體大小", self.font_spin)
        form.addRow("浮窗停留時間", self.timeout_spin)
        hint = QLabel("快捷鍵需包含 Alt / Ctrl / Shift / Win 其中一個修飾鍵。")
        hint.setStyleSheet("color:gray")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)

    def _spec(self) -> str:
        return qt_to_spec(self.hotkey_edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText))

    def _accept(self) -> None:
        try:
            parse_hotkey(self._spec())
        except ValueError as exc:
            QMessageBox.warning(self, "快捷鍵無效", str(exc))
            return
        self.accept()

    def result_config(self) -> Config:
        return replace(self._cfg, hotkey=self._spec(), font_size=self.font_spin.value(),
                       popup_timeout_sec=self.timeout_spin.value())
