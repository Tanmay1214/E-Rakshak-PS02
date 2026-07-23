import json
import sqlite3
import tarfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from erakshak.acquisition.whatsapp_root import (
    acquire_whatsapp_from_import,
    acquire_whatsapp_rooted_device,
    detect_root_access,
    detect_whatsapp_packages,
    safe_extract_tar,
)
from erakshak.adb.client import ADBResult
from erakshak.case.case_folder import CaseFolder
from erakshak.case.hashing import hash_file
from erakshak.part_b.whatsapp_parse_pipeline import parse_decrypted_whatsapp
from erakshak.part_b.whatsapp_root_pipeline import (
    run_whatsapp_root_adb_pipeline,
    run_whatsapp_root_import_pipeline,
)


@pytest.fixture
def mock_adb_client() -> MagicMock:
    adb = MagicMock()
    adb.serial = "mock_serial"
    adb.adb_path = "adb"
    return adb


def make_adb_result(cmd: list[str], stdout: str = "", stderr: str = "", code: int = 0) -> ADBResult:
    return ADBResult(
        command=cmd,
        stdout=stdout,
        stderr=stderr,
        return_code=code,
        started_at="2026-07-24T00:00:00Z",
        completed_at="2026-07-24T00:00:00.100Z",
        duration_ms=100.0,
        timed_out=False,
    )


# ── 1. Root capability detection tests ──────────────────────────────────────

def test_detect_root_access_adb_root(mock_adb_client: MagicMock) -> None:
    """Test detect_root_access returns adb_root when shell id shows uid=0."""
    mock_adb_client.shell.side_effect = [
        make_adb_result(["id"], stdout="uid=0(root) gid=0(root) groups=0(root)\n")
    ]
    res = detect_root_access(mock_adb_client, "mock_serial")
    assert res["root_available"] is True
    assert res["method"] == "adb_root"
    assert "uid=0(root)" in res["raw_id"]


def test_detect_root_access_su(mock_adb_client: MagicMock) -> None:
    """Test detect_root_access returns su when su -c id shows uid=0."""
    mock_adb_client.shell.side_effect = [
        make_adb_result(["id"], stdout="uid=2000(shell) gid=2000(shell)\n"),
        make_adb_result(["su", "-c", "id"], stdout="uid=0(root) gid=0(root) groups=0(root)\n"),
    ]
    res = detect_root_access(mock_adb_client, "mock_serial")
    assert res["root_available"] is True
    assert res["method"] == "su"
    assert "uid=0(root)" in res["raw_id"]


def test_detect_root_access_none(mock_adb_client: MagicMock) -> None:
    """Test detect_root_access returns none when root is not available."""
    mock_adb_client.shell.side_effect = [
        make_adb_result(["id"], stdout="uid=2000(shell) gid=2000(shell)\n"),
        make_adb_result(["su", "-c", "id"], stderr="permission denied\n", code=1),
    ]
    res = detect_root_access(mock_adb_client, "mock_serial")
    assert res["root_available"] is False
    assert res["method"] == "none"


# ── 2. WhatsApp package detection tests ─────────────────────────────────────

def test_detect_whatsapp_packages_normal(mock_adb_client: MagicMock) -> None:
    """Test detect_whatsapp_packages finds com.whatsapp and parses dumpsys."""
    pm_out = "package:com.whatsapp\npackage:com.android.settings\n"
    dumpsys_out = """
    versionName=2.23.1.2
    versionCode=123456
    firstInstallTime=2026-01-01 12:00:00
    lastUpdateTime=2026-01-02 12:00:00
    dataDir=/data/data/com.whatsapp
    userId=10190
    pkgFlags=[ SYSTEM HAS_CODE ]
    """
    mock_adb_client.shell.side_effect = [
        make_adb_result(["pm", "list", "packages"], stdout=pm_out),
        make_adb_result(["dumpsys", "package", "com.whatsapp"], stdout=dumpsys_out),
    ]

    res = detect_whatsapp_packages(mock_adb_client, "mock_serial")
    assert len(res) == 1
    assert res[0]["package_name"] == "com.whatsapp"
    assert res[0]["version_name"] == "2.23.1.2"
    assert res[0]["version_code"] == "123456"
    assert res[0]["data_dir"] == "/data/data/com.whatsapp"
    assert res[0]["uid"] == "10190"
    assert res[0]["is_system_app"] is True


def test_detect_whatsapp_packages_w4b(mock_adb_client: MagicMock) -> None:
    """Test detect_whatsapp_packages finds com.whatsapp.w4b and parses dumpsys."""
    pm_out = "package:com.whatsapp.w4b\n"
    dumpsys_out = """
    versionName=2.23.2.3
    versionCode=7890
    dataDir=/data/data/com.whatsapp.w4b
    userId=10195
    """
    mock_adb_client.shell.side_effect = [
        make_adb_result(["pm", "list", "packages"], stdout=pm_out),
        make_adb_result(["dumpsys", "package", "com.whatsapp.w4b"], stdout=dumpsys_out),
    ]

    res = detect_whatsapp_packages(mock_adb_client, "mock_serial")
    assert len(res) == 1
    assert res[0]["package_name"] == "com.whatsapp.w4b"
    assert res[0]["version_name"] == "2.23.2.3"
    assert res[0]["version_code"] == "7890"
    assert res[0]["data_dir"] == "/data/data/com.whatsapp.w4b"
    assert res[0]["is_system_app"] is False


# ── 3. Imported filesystem acquisition tests ────────────────────────────────

def test_acquire_whatsapp_from_import(tmp_path: Path) -> None:
    """Test imported filesystem mode copies msgstore.db and wa.db and sidecars."""
    # Create fake import layout
    import_root = tmp_path / "import"
    wa_root = import_root / "data" / "data" / "com.whatsapp"
    wa_root.mkdir(parents=True)
    
    db_dir = wa_root / "databases"
    db_dir.mkdir()
    
    # Databases
    msgstore_db = db_dir / "msgstore.db"
    msgstore_db.write_text("fake sqlite magic", encoding="utf-8")
    msgstore_db_wal = db_dir / "msgstore.db-wal"
    msgstore_db_wal.write_text("fake msgstore wal", encoding="utf-8")
    msgstore_db_shm = db_dir / "msgstore.db-shm"
    msgstore_db_shm.write_text("fake msgstore shm", encoding="utf-8")
    
    wa_db = db_dir / "wa.db"
    wa_db.write_text("fake contacts sqlite magic", encoding="utf-8")
    wa_db_wal = db_dir / "wa.db-wal"
    wa_db_wal.write_text("fake wa wal", encoding="utf-8")
    
    # Files
    files_dir = wa_root / "files"
    files_dir.mkdir()
    key_file = files_dir / "key"
    key_file.write_bytes(b"\x01" * 32)

    # Shared media
    media_dir = import_root / "sdcard" / "WhatsApp"
    media_dir.mkdir(parents=True)
    media_file = media_dir / "Media" / "WhatsApp Audio" / "audio.opus"
    media_file.parent.mkdir(parents=True)
    media_file.write_text("opus audio stream", encoding="utf-8")

    output_root = tmp_path / "cases"

    res = acquire_whatsapp_from_import(
        case_id="CASE001",
        exhibit_id="EX001",
        import_root=import_root,
        output_root=output_root,
        package_name="com.whatsapp",
    )

    assert res["status"] == "success"
    
    # Check if files copied to correct raw folder
    raw_root = output_root / "CASE001" / "EX001" / "raw" / "apps" / "whatsapp" / "imported" / "com.whatsapp"
    assert (raw_root / "data" / "data" / "com.whatsapp" / "databases" / "msgstore.db").exists()
    assert (raw_root / "data" / "data" / "com.whatsapp" / "databases" / "msgstore.db-wal").exists()
    assert (raw_root / "data" / "data" / "com.whatsapp" / "databases" / "msgstore.db-shm").exists()
    assert (raw_root / "data" / "data" / "com.whatsapp" / "databases" / "wa.db").exists()
    assert (raw_root / "data" / "data" / "com.whatsapp" / "databases" / "wa.db-wal").exists()
    assert (raw_root / "data" / "data" / "com.whatsapp" / "files" / "key").exists()
    assert (raw_root / "sdcard" / "WhatsApp" / "Media" / "WhatsApp Audio" / "audio.opus").exists()


def test_whatsapp_import_pipeline_e2e(tmp_path: Path) -> None:
    """Test imported filesystem pipeline stages manifest, hashes, and audit log."""
    # Create fake import layout
    import_root = tmp_path / "import"
    wa_root = import_root / "data" / "data" / "com.whatsapp"
    wa_root.mkdir(parents=True)
    
    db_dir = wa_root / "databases"
    db_dir.mkdir()
    (db_dir / "msgstore.db").write_text("msgstore database", encoding="utf-8")
    
    # Missing sidecars
    # Missing expected files like key, wa.db will create not_present manifest records.
    
    output_root = tmp_path / "cases"

    pipeline_res = run_whatsapp_root_import_pipeline(
        case_id="CASE001",
        exhibit_id="EX001",
        import_root=import_root,
        output_root=output_root,
        package_name="com.whatsapp",
    )

    assert pipeline_res["status"] == "success"

    exhibit_path = output_root / "CASE001" / "EX001"
    manifest_path = exhibit_path / "acquisition" / "acquisition_manifest.jsonl"
    sha256sums_path = exhibit_path / "hashes" / "sha256sums.txt"
    audit_path = exhibit_path / "acquisition" / "audit.jsonl"
    summary_path = exhibit_path / "derived" / "whatsapp_root_summary.json"

    # Check manifest records written
    assert manifest_path.is_file()
    manifest_lines = manifest_path.read_text(encoding="utf-8").splitlines()
    manifest_records = [json.loads(x) for x in manifest_lines]
    
    # Check that msgstore.db is marked as acquired
    msgstore_record = next((x for x in manifest_records if "msgstore.db" in x["source_path"]), None)
    assert msgstore_record is not None
    assert msgstore_record["status"] == "acquired"
    assert msgstore_record["artifact_class"] == "whatsapp_root_artifact"

    # Check that missing wa.db creates a not_present record
    wa_record = next((x for x in manifest_records if "wa.db" in x["source_path"]), None)
    assert wa_record is not None
    assert wa_record["status"] == "not_present"

    # Check hashes file
    assert sha256sums_path.is_file()
    assert len(sha256sums_path.read_text(encoding="utf-8").strip()) > 0

    # Check audit log contains correct actions
    assert audit_path.is_file()
    audit_lines = audit_path.read_text(encoding="utf-8").splitlines()
    actions = [json.loads(x)["action"] for x in audit_lines]
    assert "whatsapp_import_acquisition_started" in actions
    assert "whatsapp_import_acquisition_completed" in actions

    # Check summary json
    assert summary_path.is_file()
    summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary_data["databases_found"] == ["msgstore.db"]
    assert summary_data["key_file_found"] is False


# ── 4. Key file safety tests ───────────────────────────────────────────────

def test_whatsapp_key_file_safety(tmp_path: Path) -> None:
    """Test that key file contents are copied but never logged/exposed in audit logs or summary JSON."""
    import_root = tmp_path / "import"
    wa_root = import_root / "data" / "data" / "com.whatsapp"
    wa_root.mkdir(parents=True)
    
    db_dir = wa_root / "databases"
    db_dir.mkdir()
    (db_dir / "msgstore.db").write_text("msgstore db", encoding="utf-8")
    
    files_dir = wa_root / "files"
    files_dir.mkdir()
    key_file = files_dir / "key"
    secret_key_content = b"SECRET_WHATSAPP_ENCRYPTION_KEY_CONTENTS_DO_NOT_EXPOSE"
    key_file.write_bytes(secret_key_content)

    output_root = tmp_path / "cases"

    run_whatsapp_root_import_pipeline(
        case_id="CASE001",
        exhibit_id="EX001",
        import_root=import_root,
        output_root=output_root,
        package_name="com.whatsapp",
    )

    exhibit_path = output_root / "CASE001" / "EX001"
    audit_path = exhibit_path / "acquisition" / "audit.jsonl"
    summary_path = exhibit_path / "derived" / "whatsapp_root_summary.json"

    # 1. Assert contents copied
    raw_key_dest = exhibit_path / "raw" / "apps" / "whatsapp" / "imported" / "com.whatsapp" / "data" / "data" / "com.whatsapp" / "files" / "key"
    assert raw_key_dest.exists()
    assert raw_key_dest.read_bytes() == secret_key_content

    # 2. Assert key content is not in audit log
    audit_text = audit_path.read_text(encoding="utf-8")
    assert "SECRET_WHATSAPP_ENCRYPTION_KEY" not in audit_text
    
    # Check that audit log contains key metadata
    audit_events = [json.loads(x) for x in audit_text.splitlines()]
    key_acq_event = next((x for x in audit_events if x["action"] == "whatsapp_source_group_acquired"), None)
    assert key_acq_event is not None
    assert key_acq_event["details"]["key_file_acquired"] is True
    assert key_acq_event["details"]["key_file_hash"] == hash_file(raw_key_dest)
    assert "key" in key_acq_event["details"]["key_file_path"]

    # 3. Assert key content is not in summary json
    summary_text = summary_path.read_text(encoding="utf-8")
    assert "SECRET_WHATSAPP_ENCRYPTION_KEY" not in summary_text
    assert json.loads(summary_text)["key_file_found"] is True


# ── 5. Safe tar extraction tests ────────────────────────────────────────────

def test_safe_extract_tar_path_traversal(tmp_path: Path) -> None:
    """Test safe_extract_tar skips files attempting path traversal outside destination folder."""
    tar_path = tmp_path / "path_traversal.tar"
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    # Create tar with traversal path
    with tarfile.open(tar_path, "w") as tar:
        # Create a fake member
        info = tarfile.TarInfo(name="../../unsafe_outside.txt")
        info.size = 12
        import io
        tar.addfile(info, io.BytesIO(b"unsafe bytes"))

    warns = safe_extract_tar(tar_path, dest_dir)
    assert len(warns) == 1
    assert "traversal" in warns[0]
    assert not (tmp_path / "unsafe_outside.txt").exists()
    assert not (dest_dir / "unsafe_outside.txt").exists()


def test_safe_extract_tar_symlinks(tmp_path: Path) -> None:
    """Test safe_extract_tar skips symlinks and hardlinks."""
    tar_path = tmp_path / "links.tar"
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()

    with tarfile.open(tar_path, "w") as tar:
        # Symlink member
        info = tarfile.TarInfo(name="my_symlink.txt")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tar.addfile(info)

        # Hardlink member
        info2 = tarfile.TarInfo(name="my_hardlink.txt")
        info2.type = tarfile.LNKTYPE
        info2.linkname = "other_file.txt"
        tar.addfile(info2)

    warns = safe_extract_tar(tar_path, dest_dir)
    assert len(warns) == 2
    assert "symlink" in warns[0]
    assert "symlink" in warns[1] or "hardlink" in warns[1]
    assert not (dest_dir / "my_symlink.txt").exists()
    assert not (dest_dir / "my_hardlink.txt").exists()


# ── 6. Rooted ADB device pipeline & parser tests ────────────────────────────

def test_whatsapp_rooted_adb_pipeline_no_root(mock_adb_client: MagicMock, tmp_path: Path) -> None:
    """Test that live root pipeline fails clearly if root is unavailable."""
    # Mock no root
    mock_adb_client.shell.side_effect = [
        make_adb_result(["id"], stdout="uid=2000(shell) gid=2000(shell)\n"),
        make_adb_result(["su", "-c", "id"], stderr="permission denied\n", code=1),
    ]

    output_root = tmp_path / "cases"

    res = run_whatsapp_root_adb_pipeline(
        case_id="CASE001",
        exhibit_id="EX001",
        serial="mock_serial",
        output_root=output_root,
        adb_client=mock_adb_client,
    )

    assert res["status"] == "failed"
    assert "Root access is not available" in res["error"]


def test_whatsapp_rooted_adb_pipeline_success(mock_adb_client: MagicMock, tmp_path: Path) -> None:
    """Test successful run_whatsapp_root_adb_pipeline staging."""
    # Root available, com.whatsapp found
    pm_out = "package:com.whatsapp\n"
    dumpsys_out = "versionName=2.23.1.2\nuserId=10190\n"
    ls_out = "/data/data/com.whatsapp/databases\n"
    
    def adb_shell_side_effect(cmd, **kwargs):
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        if "id" in cmd_str:
            return make_adb_result(cmd, stdout="uid=0(root)\n")
        elif "pm" in cmd_str:
            return make_adb_result(cmd, stdout=pm_out)
        elif "dumpsys" in cmd_str:
            return make_adb_result(cmd, stdout=dumpsys_out)
        elif "ls" in cmd_str:
            if "databases" in cmd_str or "shared_prefs" in cmd_str:
                return make_adb_result(cmd, stdout=ls_out)
            else:
                return make_adb_result(cmd, stderr="not found\n", code=1)
        return make_adb_result(cmd)

    mock_adb_client.shell.side_effect = adb_shell_side_effect

    # Mock pull to copy database
    def mock_pull(src, dest, **kwargs):
        dest_path = Path(dest) / Path(src).name
        dest_path.mkdir(parents=True, exist_ok=True)
        if Path(src).name == "databases":
            (dest_path / "msgstore.db").write_text("rooted sql database contents", encoding="utf-8")
        elif Path(src).name == "shared_prefs":
            (dest_path / "some_pref.xml").write_text("<map></map>", encoding="utf-8")
        
        res = MagicMock()
        res.ok = True
        return res
    mock_adb_client.pull.side_effect = mock_pull

    output_root = tmp_path / "cases"

    res = run_whatsapp_root_adb_pipeline(
        case_id="CASE001",
        exhibit_id="EX001",
        serial="mock_serial",
        output_root=output_root,
        package_name="com.whatsapp",
        include_cache=False,
        include_files=False,
        include_shared_media=False,
        adb_client=mock_adb_client,
    )

    assert res["status"] == "success" or res["status"] == "partial"
    
    # Check parser-ready folder created in processed
    processed_dir = output_root / "CASE001" / "EX001" / "processed" / "apps" / "whatsapp" / "rooted" / "com.whatsapp"
    assert (processed_dir / "msgstore.db").is_file()
    assert processed_dir.name == "com.whatsapp"


@patch("erakshak.part_b.whatsapp_parse_pipeline.run_whatsapp_chat_exporter")
def test_parse_whatsapp_source_rooted(mock_run_exporter: MagicMock, tmp_path: Path) -> None:
    """Test parse_decrypted_whatsapp resolves rooted directory correctly when source is rooted."""
    exhibit_path = tmp_path / "CASE001" / "EX001"
    
    # Create fake parser-ready folder
    rooted_dir = exhibit_path / "processed" / "apps" / "whatsapp" / "rooted" / "com.whatsapp"
    rooted_dir.mkdir(parents=True)
    (rooted_dir / "msgstore.db").write_text("msgstore plain text", encoding="utf-8")
    (rooted_dir / "wa.db").write_text("wa plain text", encoding="utf-8")
    (rooted_dir / "media").mkdir()

    mock_run_exporter.return_value = {
        "status": "success",
        "html_output_dir": str(exhibit_path / "derived" / "whatsapp_exporter" / "html"),
        "json_output_path": str(exhibit_path / "derived" / "whatsapp_exporter" / "result.json"),
        "generated_file_count": 5,
        "wa_db": str(rooted_dir / "wa.db"),
        "media_dir": str(rooted_dir / "media"),
    }

    # Execute parser
    res = parse_decrypted_whatsapp(
        case_id="CASE001",
        exhibit_id="EX001",
        output_root=tmp_path,
        source="rooted",
        package="com.whatsapp",
    )

    assert res["status"] == "success"
    
    # Check that exporter was called with input_dir pointing to the rooted processed dir
    mock_run_exporter.assert_called_once()
    kwargs = mock_run_exporter.call_args[1]
    assert kwargs["input_dir"] == rooted_dir
    assert kwargs["wa_db"] == rooted_dir / "wa.db"
    assert kwargs["media_dir"] == rooted_dir / "media"
