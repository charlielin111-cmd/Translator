"""設定讀寫：%APPDATA%/HotkeyDict/config.json。缺少的欄位以預設值補齊。"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


def app_dir() -> Path:
    """程式所在目錄（PyInstaller 打包後為 exe 所在目錄）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def user_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / "HotkeyDict"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Config:
    hotkey: str = "alt+`"
    fallback_hotkeys: list[str] = field(default_factory=lambda: ["ctrl+`", "alt+q"])
    font_size: int = 14
    popup_timeout_sec: int = 0          # 0 = 不自動關閉
    db_path: str = ""                   # 空字串 = <app_dir>/data/dict.db

    def resolved_db_path(self) -> Path:
        return Path(self.db_path) if self.db_path else app_dir() / "data" / "dict.db"


def load(path: Path | None = None) -> Config:
    path = path or user_dir() / "config.json"
    cfg = Config()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for key, value in data.items():
                if hasattr(cfg, key):
                    setattr(cfg, key, value)
        except (OSError, ValueError) as exc:
            log.warning("config unreadable (%s), using defaults", exc)
    else:
        save(cfg, path)
    return cfg


def save(cfg: Config, path: Path | None = None) -> None:
    path = path or user_dir() / "config.json"
    path.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")
