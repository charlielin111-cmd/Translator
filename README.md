# HotkeyDict

在任何程式反白一個英文單字，按下全域快捷鍵，滑鼠旁會出現不搶焦點的浮窗，顯示 KK 音標與繁體中文釋義。完全離線，僅支援 Windows。

## 使用

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
# 下載 ecdict.csv 與 cmudict.dict 到 data/raw/（來源見下），然後建立字典庫：
.venv\Scripts\python tools\build_db.py
.venv\Scripts\python main.py
```

- 預設快捷鍵 **Alt+`**（反引號鍵）。被占用時依序嘗試 `Ctrl+`` 與 `Alt+Q`，實際使用的組合會顯示在系統匣選單。
- 點擊浮窗外部或按 Esc 關閉浮窗。系統匣圖示右鍵 → 結束。
- 浮窗右上角的 ☆/★ 可加入或移除**生字本**（存在 `%APPDATA%/HotkeyDict/vocab.db`）；系統匣右鍵 → 匯出生字本… 可輸出 CSV（UTF-8 含 BOM，Excel 可直接開啟）。
- 設定檔：`%APPDATA%\HotkeyDict\config.json`；記錄檔：`%APPDATA%\HotkeyDict\hotkeydict.log`（含各階段耗時）。

## 資料來源

- 釋義：[ECDICT](https://github.com/skywind3000/ECDICT)（MIT），建庫時以 OpenCC `s2twp` 轉為繁體。
- KK 音標：[CMUdict](https://github.com/cmusphinx/cmudict)（BSD）的 ARPAbet 依規則轉 KK；CMUdict 沒有的字改用 ECDICT 的 IPA 近似轉換，浮窗以 `≈` 標示。

## 已知限制

- 以系統管理員身分執行的程式收不到本工具送出的 Ctrl+C（UIPI）；需要時請也以系統管理員身分執行本工具。
- 反白的那個字仍會出現在 Win+V 剪貼簿歷史；本工具還原剪貼簿時已要求歷史與雲端同步忽略。
- 剪貼簿備份上限為 16MB / 100ms，超過時只保留優先格式（純文字最優先）。
- 掃描圖片型 PDF 沒有可反白的文字，不支援。

## 測試

```powershell
.venv\Scripts\python -m pytest -q
```

`tests/test_clipboard.py` 會使用真實剪貼簿，測試期間會暫時改動內容，結束後還原。
