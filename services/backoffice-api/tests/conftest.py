"""Variables minimas para que `Settings` valide en tests."""

import os

os.environ.setdefault("DATABASE_URL", "postgres://user:pass@localhost/test")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-123456")
os.environ.setdefault("LOG_JSON", "false")
