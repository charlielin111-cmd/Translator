import os

# 需要 Qt 的測試（設定對話框）不開真實視窗
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
