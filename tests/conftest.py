"""Cấu hình pytest: Qt offscreen; QCoreApplication dùng chung cho test QThread."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp_core():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication
    return QCoreApplication.instance() or QCoreApplication([])
