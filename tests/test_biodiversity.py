import io
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import create_app
from app.services.biodiversity import BiodiversityService, BiodiversityUnavailable


def observation(id=1, taxon=10, license="cc-by", obscured=False, rank="species"):
    return {
        "id": id,
        "taxon": {"id": taxon, "name": "Testus animalis", "rank": rank},
        "geojson": {"coordinates": [-51.15, -29.79]},
        "obscured": obscured,
        "private_location": "NEVER STORE",
        "observed_on": "2025-01-02",
        "observation_photos": [
            {
                "photo": {
                    "url": "https://inaturalist-open-data.s3.amazonaws.com/photos/1/square.jpg",
                    "license_code": license,
                    "attribution": "Author (CC BY)",
                }
            }
        ],
    }


@pytest.fixture
def settings(tmp_path, monkeypatch):
    value = Settings(
        api_token="test-token", biodiversity_cache_path=str(tmp_path / "cache.sqlite3")
    )
    monkeypatch.setattr("app.security.get_settings", lambda: value)
    monkeypatch.setattr("app.api.biodiversity.get_settings", lambda: value)
    return value


def response(records):
    return io.BytesIO(json.dumps({"results": records, "total_results": len(records)}).encode())


def test_nearby_deduplicates_species_preserves_credit_and_ignores_unlicensed(settings):
    records = [
        observation(),
        observation(2),
        observation(3, 11, "all-rights-reserved"),
        observation(4, 12, obscured=True),
        observation(5, 13, rank="genus"),
    ]
    with patch("app.services.biodiversity.urlopen", return_value=response(records)) as upstream:
        result = BiodiversityService(settings).query(latitude=-29.79, longitude=-51.15)
    assert len(result["observations"]) == 2
    assert result["observations"][0]["distance_m"] == 0
    assert result["observations"][1]["approximate_location"]
    assert result["observations"][0]["photo_attribution"] == "Author (CC BY)"
    assert "private_location" not in json.dumps(result)
    assert "taxon_id=1" in upstream.call_args.args[0].full_url
    assert "per_page=200" in upstream.call_args.args[0].full_url


def test_cache_shared_between_instances_and_quota_shared_between_queries(settings):
    with patch(
        "app.services.biodiversity.urlopen", return_value=response([observation()])
    ) as upstream:
        service = BiodiversityService(settings)
        assert not service.query(latitude=0, longitude=0)["cached"]
        assert BiodiversityService(settings).query(latitude=0, longitude=0)["cached"]
        assert upstream.call_count == 1
        with pytest.raises(BiodiversityUnavailable):
            BiodiversityService(settings).query(latitude=0, longitude=0, radius_m=500)


def test_map_cap_and_nearby_cap(settings):
    records = [observation(i, i) for i in range(1, 151)]
    with patch("app.services.biodiversity.urlopen", return_value=response(records)):
        assert (
            len(
                BiodiversityService(settings).query(north=1, south=0, east=1, west=0)[
                    "observations"
                ]
            )
            == 100
        )
    settings.biodiversity_cache_path += "-nearby"
    with patch("app.services.biodiversity.urlopen", return_value=response(records)):
        result = BiodiversityService(settings).query(latitude=0, longitude=0)
        assert len(result["observations"]) == 12
        assert result["limited"]


def test_failures_not_cached(settings):
    with patch("app.services.biodiversity.urlopen", side_effect=TimeoutError):
        with pytest.raises(BiodiversityUnavailable):
            BiodiversityService(settings).query(latitude=0, longitude=0)


def test_endpoints_require_auth_validate_radius_bounds_and_return_schema(settings):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    client = TestClient(app)
    assert client.get("/biodiversity/nearby?latitude=0&longitude=0").status_code == 401
    headers = {"Authorization": "Bearer test-token"}
    for params in [
        "latitude=nan&longitude=0",
        "latitude=91&longitude=0",
        "latitude=0&longitude=0&radius_m=999",
    ]:
        assert client.get("/biodiversity/nearby?" + params, headers=headers).status_code == 422
    assert (
        client.get(
            "/biodiversity/observations?north=80&south=-80&east=180&west=-180", headers=headers
        ).status_code
        == 422
    )
    for radius in (500, 1000, 5000):
        with patch(
            "app.api.biodiversity.query_service",
            return_value={
                "source": "iNaturalist",
                "fetched_at": "2026-11-15T12:00:00Z",
                "cached": False,
                "radius_m": radius,
                "limit": 12,
                "sampled_records": 0,
                "total_matching_observations": 0,
                "limited": False,
                "observations": [],
            },
        ):
            assert (
                client.get(
                    f"/biodiversity/nearby?latitude=0&longitude=0&radius_m={radius}",
                    headers=headers,
                ).status_code
                == 200
            )


def test_upstream_outage_is_optional_503(settings):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    with patch("app.services.biodiversity.urlopen", side_effect=TimeoutError):
        assert (
            TestClient(app)
            .get(
                "/biodiversity/nearby?latitude=0&longitude=0",
                headers={"Authorization": "Bearer test-token"},
            )
            .status_code
            == 503
        )
