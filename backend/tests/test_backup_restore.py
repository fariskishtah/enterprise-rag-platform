from __future__ import annotations

import json
import sqlite3
import stat
from pathlib import Path

import pytest

from app.core.config import Settings
from scripts.production_backup import create_backup, restore_backup, verify_backup


def backup_settings(tmp_path: Path) -> Settings:
    database = tmp_path / "data" / "enterprise_rag.db"
    database.parent.mkdir()
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE records (value TEXT NOT NULL)")
        connection.execute("INSERT INTO records VALUES ('before backup')")
    storage = tmp_path / "data" / "uploads"
    storage.mkdir()
    (storage / "source.txt").write_text("source before backup", encoding="utf-8")
    return Settings(
        database_url=f"sqlite:///{database}",
        storage_path=storage,
        backup_dir=tmp_path / "backups",
        session_secret="super-secret-value-that-must-not-leak",
        demo_password_hash="$2b$12$must-not-leak",
    )


def test_backup_is_sqlite_safe_private_verifiable_and_contains_no_secrets(
    tmp_path: Path,
) -> None:
    settings = backup_settings(tmp_path)
    backup = create_backup(settings, settings.backup_dir)
    manifest = verify_backup(backup)
    all_text = "\n".join(
        value.read_text(encoding="utf-8")
        for value in backup.iterdir()
        if value.suffix in {".json", ".template"}
    )

    assert manifest["backup_id"] == backup.name
    assert settings.session_secret not in all_text
    assert settings.demo_password_hash not in all_text
    assert "ENTERPRISE_RAG_SESSION_SECRET=" in all_text
    for filename in manifest["files"]:
        mode = stat.S_IMODE((backup / filename).stat().st_mode)
        assert mode == 0o600
    with sqlite3.connect(backup / "enterprise_rag.db") as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_restore_requires_confirmation_and_restores_database_and_uploads(tmp_path: Path) -> None:
    settings = backup_settings(tmp_path)
    backup = create_backup(settings, settings.backup_dir)
    database = Path(settings.database_url.removeprefix("sqlite:///"))
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE records SET value = 'after backup'")
    (settings.storage_path / "source.txt").write_text("after backup", encoding="utf-8")
    (settings.storage_path / "new.txt").write_text("remove on restore", encoding="utf-8")

    with pytest.raises(RuntimeError, match="requires --confirm"):
        restore_backup(settings, backup, confirmed=False)
    restore_backup(settings, backup, confirmed=True)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM records").fetchone() == ("before backup",)
    assert (settings.storage_path / "source.txt").read_text(encoding="utf-8") == (
        "source before backup"
    )
    assert not (settings.storage_path / "new.txt").exists()
    assert stat.S_IMODE(database.stat().st_mode) == 0o600
    assert stat.S_IMODE(settings.storage_path.stat().st_mode) == 0o700


def test_backup_verification_detects_tampering(tmp_path: Path) -> None:
    settings = backup_settings(tmp_path)
    backup = create_backup(settings, settings.backup_dir)
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    target = backup / next(iter(manifest["files"]))
    target.write_bytes(target.read_bytes() + b"tampered")

    with pytest.raises(RuntimeError, match="verification failed"):
        verify_backup(backup)
