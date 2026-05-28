"""Tests for domains/coffee/sources/ice_coffee_c.py"""
from datetime import date
from unittest.mock import MagicMock, patch

import httpx
import pytest

from core.models.observation import MarketObservation
from core.models.source_run import RunStatus
from domains.coffee.sources import ice_coffee_c

_COLUMNS = [
    "Date", "Open", "High", "Low", "Last", "Change",
    "Settle", "Volume", "Previous Day Open Interest",
]

_GOOD_RESPONSE = {
    "dataset": {
        "column_names": _COLUMNS,
        "data": [
            ["2024-01-02", 175.00, 177.00, 174.50, 176.00, 1.00, 176.00, 10000, 50000],
            ["2024-01-03", 176.00, 178.00, 175.50, 177.00, 1.00, 177.00, 11000, 51000],
        ],
    }
}

_PARTIAL_RESPONSE = {
    "dataset": {
        "column_names": _COLUMNS,
        "data": [
            ["2024-01-02", 175.00, 177.00, 174.50, 176.00, 1.00, 176.00, 10000, 50000],
            ["2024-01-03", 176.00, 178.00, 175.50, 177.00, 1.00, None, 11000, 51000],  # null Settle
        ],
    }
}


def _mock_httpx_client(json_data: dict, status_code: int = 200) -> MagicMock:
    """Return a patched httpx.Client constructor that yields a mock returning json_data."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_data
    if status_code >= 400:
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message="error",
            request=MagicMock(),
            response=MagicMock(status_code=status_code, text="Unauthorized"),
        )
    else:
        mock_resp.raise_for_status.return_value = None

    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    return MagicMock(return_value=mock_client)


_PATCH = "domains.coffee.sources.ice_coffee_c.httpx.Client"


@pytest.fixture(autouse=True)
def set_api_key(monkeypatch):
    monkeypatch.setenv("NASDAQ_API_KEY", "test-key")


class TestFetchSuccess:
    def test_returns_market_observations(self):
        with patch(_PATCH, _mock_httpx_client(_GOOD_RESPONSE)):
            obs, run = ice_coffee_c.fetch(date(2024, 1, 1), date(2024, 1, 5))

        assert len(obs) == 2
        assert all(isinstance(o, MarketObservation) for o in obs)

    def test_observation_fields(self):
        with patch(_PATCH, _mock_httpx_client(_GOOD_RESPONSE)):
            obs, _ = ice_coffee_c.fetch(date(2024, 1, 1), date(2024, 1, 5))

        first = obs[0]
        assert first.asset_id == "coffee:benchmark:ice:arabica"
        assert first.observed_date == date(2024, 1, 2)
        assert first.value == 176.00
        assert first.unit == "USc/lb"
        assert first.source == "nasdaq:CHRIS/ICE_KC1"
        assert first.raw is not None
        assert first.raw["Settle"] == 176.00

    def test_source_run_success(self):
        with patch(_PATCH, _mock_httpx_client(_GOOD_RESPONSE)):
            _, run = ice_coffee_c.fetch(date(2024, 1, 1), date(2024, 1, 5))

        assert run.status == RunStatus.SUCCESS
        assert run.records_fetched == 2
        assert run.records_stored == 0
        assert run.error_message is None
        assert run.source_id == "coffee:ice_coffee_c"


class TestFetchPartial:
    def test_skips_malformed_row_and_returns_partial(self):
        with patch(_PATCH, _mock_httpx_client(_PARTIAL_RESPONSE)):
            obs, run = ice_coffee_c.fetch(date(2024, 1, 1), date(2024, 1, 5))

        assert len(obs) == 1
        assert obs[0].observed_date == date(2024, 1, 2)
        assert run.status == RunStatus.PARTIAL
        assert run.records_fetched == 1
        assert "skipped" in run.error_message


class TestFetchFailure:
    def test_http_401_returns_failed_run(self):
        with patch(
            "domains.coffee.sources.ice_coffee_c.httpx.Client",
            _mock_httpx_client({}, status_code=401),
        ):
            obs, run = ice_coffee_c.fetch(date(2024, 1, 1), date(2024, 1, 5))

        assert obs == []
        assert run.status == RunStatus.FAILED
        assert run.records_fetched == 0
        assert "401" in run.error_message

    def test_request_error_returns_failed_run(self):
        mock_client = MagicMock()
        mock_client.get.side_effect = httpx.ConnectError("connection refused")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch(
            "domains.coffee.sources.ice_coffee_c.httpx.Client",
            MagicMock(return_value=mock_client),
        ):
            obs, run = ice_coffee_c.fetch(date(2024, 1, 1), date(2024, 1, 5))

        assert obs == []
        assert run.status == RunStatus.FAILED
        assert run.error_message is not None


class TestParseResponse:
    def test_parse_extracts_settle_by_column_name(self):
        # Columns in different order — parser must look up by name, not position
        shuffled = {
            "dataset": {
                "column_names": ["Open", "Date", "Settle", "Volume"],
                "data": [
                    [175.00, "2024-03-01", 180.50, 9000],
                ],
            }
        }
        obs, errors = ice_coffee_c._parse_response(shuffled)
        assert errors == 0
        assert obs[0].value == 180.50
        assert obs[0].observed_date == date(2024, 3, 1)

    def test_missing_settle_column_raises(self):
        bad_schema = {
            "dataset": {
                "column_names": ["Date", "Close"],
                "data": [["2024-01-02", 175.00]],
            }
        }
        with pytest.raises(ValueError, match="Unexpected column layout"):
            ice_coffee_c._parse_response(bad_schema)
