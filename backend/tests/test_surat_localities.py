"""Tests for Surat offline nearest-locality lookup in E-RAKSHAK."""

from erakshak.acquisition.location_evidence import nearest_surat_locality


def test_nearest_surat_locality_within_threshold() -> None:
    # Coordinate very close to Varachha (21.215, 72.865)
    # E.g. (21.216, 72.866)
    res = nearest_surat_locality(21.216, 72.866, threshold_km=1.0)
    assert res is not None
    assert res["name"] == "Varachha"
    assert res["distance_km"] < 1.0


def test_nearest_surat_locality_outside_threshold() -> None:
    # Coordinate in New York
    res = nearest_surat_locality(40.7128, -74.0060, threshold_km=5.0)
    assert res is None
