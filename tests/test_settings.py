import pytest
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from config import Config
from settings import SettingsDialog, qt_to_spec, spec_to_qt


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("qt, spec", [
    ("Alt+`", "alt+`"), ("Ctrl+Shift+Q", "ctrl+shift+q"), ("Meta+Space", "win+space"),
    ("Ctrl+F5", "ctrl+f5"), ("Alt+Return", "alt+enter"),
])
def test_qt_to_spec(qt, spec):
    assert qt_to_spec(qt) == spec


@pytest.mark.parametrize("spec, qt", [
    ("alt+`", "Alt+`"), ("ctrl+shift+q", "Ctrl+Shift+Q"), ("win+space", "Meta+Space"),
    ("ctrl+f5", "Ctrl+F5"), ("alt+enter", "Alt+Return"),
])
def test_spec_to_qt(spec, qt):
    assert spec_to_qt(spec) == qt


def test_dialog_shows_current_values(qapp):
    d = SettingsDialog(Config(hotkey="ctrl+shift+q", font_size=18, popup_timeout_sec=7))
    assert d.font_spin.value() == 18 and d.timeout_spin.value() == 7
    assert d.hotkey_edit.keySequence().toString() == "Ctrl+Shift+Q"


def test_dialog_result_config_reflects_edits_and_keeps_other_fields(qapp):
    base = Config(copy_timeout_ms=1234, fallback_hotkeys=["alt+q"])
    d = SettingsDialog(base)
    d.hotkey_edit.setKeySequence(QKeySequence("Ctrl+Alt+D"))
    d.font_spin.setValue(20)
    d.timeout_spin.setValue(0)
    out = d.result_config()
    assert (out.hotkey, out.font_size, out.popup_timeout_sec) == ("ctrl+alt+d", 20, 0)
    assert out.copy_timeout_ms == 1234 and out.fallback_hotkeys == ["alt+q"]
    assert base.hotkey == "alt+`"                       # 不修改傳入的原設定物件


def test_dialog_rejects_hotkey_without_modifier(qapp, monkeypatch):
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a[2]))
    d = SettingsDialog(Config())
    d.hotkey_edit.setKeySequence(QKeySequence("Q"))
    d._accept()
    assert warned and d.result() != QDialog.DialogCode.Accepted


def test_dialog_accepts_valid_hotkey(qapp):
    d = SettingsDialog(Config())
    d._accept()
    assert d.result() == QDialog.DialogCode.Accepted
