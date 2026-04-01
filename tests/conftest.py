from __future__ import annotations

import os
from tempfile import gettempdir


os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{gettempdir()}/lovepod-test-suite.db")
os.environ.setdefault("AUTO_CREATE_TABLES", "false")
os.environ.setdefault("DOCS_ENABLED", "true")
os.environ.setdefault("RATE_LIMIT_REQUESTS", "1000")
