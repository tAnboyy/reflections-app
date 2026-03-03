from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


@contextmanager
def workspace_temp_dir():
    root = Path(__file__).resolve().parents[1] / ".tmp-tests"
    root.mkdir(parents=True, exist_ok=True)
    temp_path = root / f"tmp-{uuid4().hex}"
    temp_path.mkdir(parents=True, exist_ok=False)
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)
