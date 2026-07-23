"""Tests for erakshak.part_b.telegram_paths — Telegram path registry."""
from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError

from erakshak.part_b.telegram_paths import (
    TelegramDbGroup,
    TelegramProfile,
    TELEGRAM_PROFILES,
    SQLITE_SIDECAR_EXTENSIONS,
    get_profile,
)


def test_telegram_db_group_immutability() -> None:
    """Verify TelegramDbGroup is immutable (frozen dataclass)."""
    group = TelegramDbGroup(
        relative_path="files/cache4.db",
        description="Test DB",
        required=True,
    )
    with pytest.raises(FrozenInstanceError):
        group.relative_path = "changed"  # type: ignore[misc]


def test_telegram_profile_immutability() -> None:
    """Verify TelegramProfile is immutable (frozen dataclass)."""
    profile = TelegramProfile(
        package="test.package",
        display_name="Test Profile",
        private_data_root="/data/data/test.package",
        db_groups=(),
        shared_media_roots=(),
        notes="Test note",
    )
    with pytest.raises(FrozenInstanceError):
        profile.package = "changed"  # type: ignore[misc]


def test_get_profile_known_packages() -> None:
    """Verify get_profile returns correct profile for all registered packages."""
    for profile in TELEGRAM_PROFILES:
        res = get_profile(profile.package)
        assert res is not None
        assert res.package == profile.package
        assert res.display_name == profile.display_name


def test_get_profile_unknown_packages() -> None:
    """Verify get_profile returns None for unknown or empty package names."""
    assert get_profile("unknown.package") is None
    assert get_profile("") is None
    assert get_profile("org.telegram") is None  # partial match


def test_profile_fields_validity() -> None:
    """Verify validity of fields in every registered Telegram profile."""
    for profile in TELEGRAM_PROFILES:
        assert profile.package != ""
        assert profile.display_name != ""
        
        # Absolute private data root
        assert profile.private_data_root.startswith("/")
        
        # Relative database paths
        assert len(profile.db_groups) > 0
        for db_group in profile.db_groups:
            assert db_group.relative_path != ""
            assert not db_group.relative_path.startswith("/")
            assert db_group.description != ""
            
        # Absolute shared media roots
        for media_root in profile.shared_media_roots:
            assert media_root.startswith("/")


def test_sqlite_sidecar_extensions() -> None:
    """Verify SQLITE_SIDECAR_EXTENSIONS contents match exactly."""
    assert set(SQLITE_SIDECAR_EXTENSIONS) == {"-wal", "-shm", "-journal"}
    assert len(SQLITE_SIDECAR_EXTENSIONS) == 3


def test_no_duplicate_package_names() -> None:
    """Verify no duplicate package names exist in TELEGRAM_PROFILES."""
    packages = [profile.package for profile in TELEGRAM_PROFILES]
    assert len(packages) == len(set(packages))


def test_no_duplicate_databases_within_profile() -> None:
    """Verify no duplicate database relative paths exist within any profile."""
    for profile in TELEGRAM_PROFILES:
        paths = [db_group.relative_path for db_group in profile.db_groups]
        assert len(paths) == len(set(paths))


def test_no_duplicate_media_roots_within_profile() -> None:
    """Verify no duplicate shared media roots exist within any profile."""
    for profile in TELEGRAM_PROFILES:
        roots = list(profile.shared_media_roots)
        assert len(roots) == len(set(roots))
