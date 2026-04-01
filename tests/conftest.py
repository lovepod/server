from __future__ import annotations

import os


os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///./test-suite.db")
os.environ.setdefault("AUTO_CREATE_TABLES", "false")
os.environ.setdefault("DOCS_ENABLED", "true")
os.environ.setdefault("RATE_LIMIT_REQUESTS", "1000")
