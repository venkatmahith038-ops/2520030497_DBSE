"""Regression tests for the file-exposure fixes.

`/api/tg/uploads/{filename}` served any file the process could read, because it
had no auth dependency and `os.path.join` follows backslashes on Windows. The
scheduled-post `media_path` had the same shape of problem via Telegram upload.
"""
import os

import pytest

from backend.schemas import validate_batch_messages, validate_media_path
from backend.security import decrypt_secret, encrypt_secret, resolve_upload_path


@pytest.fixture
def upload_dir(tmp_path):
    base = tmp_path / "uploads" / "tg"
    base.mkdir(parents=True)
    (base / "abc123__photo.png").write_bytes(b"fake image")
    (tmp_path / "secret.env").write_text("API_SECRET_KEY=hunter2")
    return str(base)


@pytest.mark.parametrize("probe", [
    "..\\..\\secret.env",       # Windows separator — the original bug
    "../../secret.env",
    "..\\..\\..\\config.py",
    "....//secret.env",
    "..",
    "",
])
def test_traversal_is_refused(upload_dir, probe):
    assert resolve_upload_path(upload_dir, probe) is None


def test_absolute_path_is_refused(upload_dir):
    outside = os.path.join(os.path.dirname(os.path.dirname(upload_dir)), "secret.env")
    assert os.path.exists(outside)
    assert resolve_upload_path(upload_dir, outside) is None


def test_a_real_upload_still_resolves(upload_dir):
    resolved = resolve_upload_path(upload_dir, "abc123__photo.png")
    assert resolved is not None
    assert os.path.isfile(resolved)


def test_missing_file_returns_none(upload_dir):
    assert resolve_upload_path(upload_dir, "nope.png") is None


@pytest.mark.parametrize("probe", [
    "../../.env",
    "..\\..\\.env",
    "D:\\Automation\\Insta-Automate\\.env",
    "/etc/passwd",
    "sub/dir/file.png",
])
def test_media_path_rejects_paths(probe):
    with pytest.raises(ValueError):
        validate_media_path(probe)


@pytest.mark.parametrize("value", [
    "abc123__photo.png",
    "library_4_f57f40f2.png",
    "https://example.com/image.png",
    "",
    None,
])
def test_media_path_accepts_legitimate_values(value):
    assert validate_media_path(value) == value


def test_batch_messages_are_validated_too():
    with pytest.raises(ValueError):
        validate_batch_messages([{"content": "hi", "media_path": "../../.env"}])

    good = [{"content": "hi", "media_path": "abc123__photo.png"}, "not-a-dict"]
    assert validate_batch_messages(good) == good


def test_secrets_round_trip_and_are_not_stored_in_the_clear():
    token = "123456:ABC-DEF_ghijklmnopqrstuvwxyz"
    encrypted = encrypt_secret(token)

    assert encrypted != token
    assert token not in encrypted
    assert encrypted.startswith("enc:v1:")
    assert decrypt_secret(encrypted) == token


def test_decrypting_a_tampered_token_returns_none():
    encrypted = encrypt_secret("sensitive")
    assert decrypt_secret(encrypted[:-4] + "AAAA") is None
