"""Signal Android path registry for E-RAKSHAK Part B acquisition.

Signal Android stores message data in its private app sandbox. These paths are
not readable through normal unrooted ADB; acquisition succeeds only on rooted,
imported, test, or otherwise authorized evidence sources where the files are
actually accessible.
"""

from __future__ import annotations

from dataclasses import dataclass


SQLITE_SIDECAR_EXTENSIONS: tuple[str, ...] = ("-wal", "-shm", "-journal")


@dataclass(frozen=True)
class SignalDbGroup:
    """One Signal SQLite database and its sidecars."""

    relative_path: str
    description: str
    required: bool = True
    parse_messages: bool = True


@dataclass(frozen=True)
class SignalProfile:
    """Acquisition targets for one Signal Android package variant."""

    package: str
    display_name: str
    private_data_root: str
    db_groups: tuple[SignalDbGroup, ...]
    shared_media_roots: tuple[str, ...]
    notes: str = ""


_SIGNAL_STABLE = SignalProfile(
    package="org.thoughtcrime.securesms",
    display_name="Signal",
    private_data_root="/data/data/org.thoughtcrime.securesms",
    db_groups=(
        SignalDbGroup(
            relative_path="databases/signal.db",
            description="Primary Signal message database. Usually SQLCipher-encrypted on Android.",
            required=True,
        ),
        SignalDbGroup(
            relative_path="databases/signal-key-value.db",
            description="Signal key-value support database. Preserved to support later key/schema analysis.",
            required=False,
            parse_messages=False,
        ),
    ),
    shared_media_roots=(
        "/sdcard/Android/media/org.thoughtcrime.securesms",
    ),
    notes="Private app data requires root/import access; normal ADB should report permission_denied.",
)


_SIGNAL_BETA = SignalProfile(
    package="org.thoughtcrime.securesms.beta",
    display_name="Signal Beta",
    private_data_root="/data/data/org.thoughtcrime.securesms.beta",
    db_groups=(
        SignalDbGroup(
            relative_path="databases/signal.db",
            description="Primary Signal Beta message database. Usually SQLCipher-encrypted on Android.",
            required=True,
        ),
        SignalDbGroup(
            relative_path="databases/signal-key-value.db",
            description="Signal Beta key-value support database. Preserved to support later key/schema analysis.",
            required=False,
            parse_messages=False,
        ),
    ),
    shared_media_roots=(
        "/sdcard/Android/media/org.thoughtcrime.securesms.beta",
    ),
    notes="Beta package variant; schema may differ from stable Signal.",
)


SIGNAL_PROFILES: tuple[SignalProfile, ...] = (_SIGNAL_STABLE, _SIGNAL_BETA)


def get_profile(package: str) -> SignalProfile | None:
    """Return the registered Signal profile for *package*, if any."""
    for profile in SIGNAL_PROFILES:
        if profile.package == package:
            return profile
    return None
