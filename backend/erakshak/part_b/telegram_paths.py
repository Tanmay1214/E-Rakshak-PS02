"""Telegram variant path registry for E-RAKSHAK Part B acquisition.

Defines the known Telegram package variants together with their:

- Android package name and human-readable display name.
- Absolute on-device private data root (root access required to read).
- Ordered list of candidate SQLite database groups, each consisting of a
  primary ``.db`` file and its implicit WAL/sidecar files.
- World-readable shared media roots accessible via ADB without root.

This module contains **only** registry data and lookup utilities.
No I/O, no ADB calls, no filesystem operations, no parsing logic.

Usage example::

    from erakshak.part_b.telegram_paths import get_profile, TELEGRAM_PROFILES

    profile = get_profile("org.telegram.messenger")
    if profile is not None:
        for db_group in profile.db_groups:
            print(db_group.relative_path)

Design notes
------------
- All registry entries are **immutable** (``frozen=True``) so callers can
  never accidentally mutate shared state.
- ``db_groups`` uses a ``tuple`` (not a ``list``) to enforce immutability on
  the outer container as well.
- To add a new Telegram variant, create a new :class:`TelegramProfile`
  instance below and append it to :data:`TELEGRAM_PROFILES`.  No other code
  needs to change.
- Multiple-account support is intentionally deferred.  The current registry
  targets the default/primary account only.  When multi-account support is
  added, the ``TelegramProfile`` dataclass should gain an ``account_slot``
  field or the registry should be parameterised over account slot paths.
"""

from __future__ import annotations

from dataclasses import dataclass


# ── SQLite sidecar extensions ─────────────────────────────────────────────────

# SQLite WAL (Write-Ahead Logging) mode produces two sidecar files alongside
# every ``*.db``: a ``.db-wal`` and a ``.db-shm``.  Rollback-journal mode
# produces a ``.db-journal``.  For forensic completeness all three must be
# acquired with the primary database as a single atomic group.
#
# These extensions are intentionally kept in this module so that the
# acquisition layer (Phase B.2.2) can import a single canonical definition
# rather than hard-coding extension lists in multiple places.
SQLITE_SIDECAR_EXTENSIONS: tuple[str, ...] = ("-wal", "-shm", "-journal")


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TelegramDbGroup:
    """One SQLite database file and its implicit sidecar files.

    Represents a single ``.db`` file that the acquisition layer should pull
    from the device.  Sidecar files (``.db-wal``, ``.db-shm``,
    ``.db-journal``) are always pulled alongside the primary file when
    they exist; their names are derived at acquisition time by appending each
    extension in :data:`SQLITE_SIDECAR_EXTENSIONS` to ``relative_path``.

    Parameters
    ----------
    relative_path:
        Path to the primary ``.db`` file, **relative to**
        :attr:`TelegramProfile.private_data_root`.  Must not start with
        ``/``.  Example: ``"files/cache4.db"``.
    description:
        Human-readable summary of what this database contains.  Recorded
        in the acquisition manifest for the investigator's benefit.
    required:
        When ``True``, the absence of this database is treated as a
        significant acquisition gap and must be recorded in the manifest
        with status ``not_accessible``.  When ``False``, absence is
        recorded as ``not_present`` and is not considered a failure.
    """

    relative_path: str
    description: str
    required: bool = True


@dataclass(frozen=True)
class TelegramProfile:
    """Acquisition targets for one Telegram package variant.

    Each registered Telegram variant (official, OEM web build, Telegram X)
    has exactly one :class:`TelegramProfile`.  The profile captures all the
    information the acquisition layer needs to attempt a forensic pull
    without the caller needing to know any Telegram-specific paths.

    Parameters
    ----------
    package:
        Android package name.  E.g. ``"org.telegram.messenger"``.
    display_name:
        Short human-readable label used in CLI output and manifest records.
    private_data_root:
        Absolute on-device path to the app's private data directory.
        Must start with ``/``.  Requires root access or a root/import
        acquisition lane to read.  Example:
        ``"/data/data/org.telegram.messenger"``.
    db_groups:
        Ordered tuple of :class:`TelegramDbGroup` instances describing
        the SQLite databases to acquire, listed in **acquisition priority
        order** (most important first).  The acquisition layer iterates
        this tuple in order and stops when the byte/time budget is
        exhausted.
    shared_media_roots:
        Tuple of absolute on-device paths that may contain world-readable
        shared media (images, video, documents) accessible via ADB *without*
        root.  Each path is attempted independently; missing paths are
        silently skipped.
    notes:
        Optional free-text notes about this variant — version-specific
        schema differences, deprecation status, known caveats, etc.
        Recorded in manifest metadata but not used programmatically.
    """

    package: str
    display_name: str
    private_data_root: str
    db_groups: tuple[TelegramDbGroup, ...]
    shared_media_roots: tuple[str, ...]
    notes: str = ""


# ── Profile definitions ───────────────────────────────────────────────────────
#
# Each profile is defined as a module-level private constant and then
# collected into TELEGRAM_PROFILES.  Adding a new variant is a two-step
# process: (1) define a new _TELEGRAM_<NAME> constant, (2) append it to the
# TELEGRAM_PROFILES tuple.  No other code needs to change.

_TELEGRAM_OFFICIAL = TelegramProfile(
    package="org.telegram.messenger",
    display_name="Telegram",
    private_data_root="/data/data/org.telegram.messenger",
    db_groups=(
        TelegramDbGroup(
            relative_path="files/cache4.db",
            description=(
                "Primary message and chat cache database (Telegram 4.x+). "
                "Contains messages, chats, contacts, and media metadata."
            ),
            required=True,
        ),
    ),
    shared_media_roots=(
        # Legacy shared storage path — Android 10 and below.
        "/sdcard/Telegram",
        # Scoped storage path — Android 11+ (SDK >= 30).
        # Telegram migrated to this path with scoped storage enforcement.
        "/sdcard/Android/media/org.telegram.messenger",
    ),
    notes=(
        "Official Telegram client. "
        "cache4.db is the primary forensic target, containing messages, "
        "chats, user/group data, and references to media files. "
        "Versions older than 4.0 used 'cache.db' (not targeted this sprint). "
        "Private data is sandbox-protected; root or import lane required."
    ),
)

_TELEGRAM_WEB = TelegramProfile(
    package="org.telegram.messenger.web",
    display_name="Telegram (OEM/Web variant)",
    private_data_root="/data/data/org.telegram.messenger.web",
    db_groups=(
        TelegramDbGroup(
            relative_path="files/cache4.db",
            description=(
                "Primary message and chat cache database. "
                "Shares the same schema as org.telegram.messenger."
            ),
            required=True,
        ),
    ),
    shared_media_roots=(
        # Shared storage path for this package variant.
        "/sdcard/Telegram",
        "/sdcard/Android/media/org.telegram.messenger.web",
    ),
    notes=(
        "OEM-bundled or web-linked variant of the official Telegram client. "
        "Functionally identical to org.telegram.messenger; "
        "uses the same database schema. "
        "Found on some Samsung and Huawei devices pre-installed."
    ),
)

_TELEGRAM_X = TelegramProfile(
    package="org.thunderdog.challegram",
    display_name="Telegram X (Challegram)",
    private_data_root="/data/data/org.thunderdog.challegram",
    db_groups=(
        TelegramDbGroup(
            relative_path="files/cache4.db",
            description=(
                "Primary message and chat cache database (Challegram). "
                "Compatible with Telegram's schema but independently maintained; "
                "internal table structure may differ across versions."
            ),
            required=True,
        ),
    ),
    shared_media_roots=(
        # Challegram uses the same /sdcard/Telegram shared folder.
        "/sdcard/Telegram",
        "/sdcard/Android/media/org.thunderdog.challegram",
    ),
    notes=(
        "Telegram X / Challegram — an alternative open-source Telegram client. "
        "Uses a compatible but independently maintained codebase. "
        "Database schema may diverge from the official client across versions. "
        "Deep message decoding requires schema verification against the "
        "installed app version."
    ),
)


# ── Registry ──────────────────────────────────────────────────────────────────

# Master registry: listed in order of prevalence (most common variant first).
# The acquisition layer iterates this tuple in order when scanning for
# installed Telegram variants; first match wins for shared resources.
TELEGRAM_PROFILES: tuple[TelegramProfile, ...] = (
    _TELEGRAM_OFFICIAL,
    _TELEGRAM_WEB,
    _TELEGRAM_X,
)


# ── Lookup utilities ──────────────────────────────────────────────────────────

def get_profile(package: str) -> TelegramProfile | None:
    """Return the :class:`TelegramProfile` for *package*, or ``None``.

    Performs an exact match on the ``package`` field.  Partial matches
    (e.g. ``"org.telegram"`` matching ``"org.telegram.messenger"``) are
    intentionally rejected to prevent false positives.

    Parameters
    ----------
    package:
        Android package name to look up.  Must be an exact match.

    Returns
    -------
    TelegramProfile or None
        The first :class:`TelegramProfile` in :data:`TELEGRAM_PROFILES`
        whose ``package`` field equals *package*, or ``None`` if no match
        is found.

    Examples
    --------
    >>> profile = get_profile("org.telegram.messenger")
    >>> profile is not None
    True
    >>> profile.display_name
    'Telegram'

    >>> get_profile("com.unknown.app") is None
    True
    """
    for profile in TELEGRAM_PROFILES:
        if profile.package == package:
            return profile
    return None

