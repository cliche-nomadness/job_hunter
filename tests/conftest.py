# tests/conftest.py —— 让 pytest 能找到 cli/ 里的模块（pytest 自动加载本文件）
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))
