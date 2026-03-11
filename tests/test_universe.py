"""
Unit tests for data/universe.py — static list integrity and deduplication logic.
"""

import pytest

from data.universe import (
    FX_PAIRS, EQUITY_INDICES, COMMODITIES, DJIA_30, FTSE_100, STOXX_50,
    get_universe, get_flat_universe,
)


class TestStaticLists:
    def test_fx_pairs_format(self):
        """FX tickers should end with =X."""
        for t in FX_PAIRS:
            assert t.endswith("=X"), f"{t} does not end with =X"

    def test_equity_indices_have_caret_or_suffix(self):
        """Index tickers start with ^ or have an exchange suffix."""
        for t in EQUITY_INDICES:
            assert t.startswith("^") or "." in t or t.endswith("SS"), \
                f"Unexpected index ticker format: {t}"

    def test_commodities_end_with_f(self):
        """Futures tickers end with =F."""
        for t in COMMODITIES:
            assert t.endswith("=F"), f"{t} does not end with =F"

    def test_djia_30_has_30_components(self):
        assert len(DJIA_30) == 30

    def test_ftse_has_at_least_80_components(self):
        assert len(FTSE_100) >= 80

    def test_stoxx_has_components(self):
        assert len(STOXX_50) >= 40

    def test_no_empty_strings(self):
        for lst in (FX_PAIRS, EQUITY_INDICES, COMMODITIES, DJIA_30, FTSE_100, STOXX_50):
            assert all(t for t in lst), "Empty ticker found in static list"


class TestGetUniverse:
    def test_returns_dict(self):
        u = get_universe(include_sp500=False, include_nasdaq=False)
        assert isinstance(u, dict)

    def test_categories_present(self):
        u = get_universe(
            include_sp500=False, include_nasdaq=False,
            include_djia=True, include_ftse=True, include_stoxx=True,
            include_fx=True, include_indices=True, include_commodities=True,
        )
        assert "DJIA" in u
        assert "FTSE100" in u
        assert "STOXX50" in u
        assert "FX" in u
        assert "Indices" in u
        assert "Commodities" in u

    def test_commodities_excluded_by_default(self):
        u = get_universe(include_sp500=False, include_nasdaq=False)
        assert "Commodities" not in u

    def test_commodities_included_when_requested(self):
        u = get_universe(
            include_sp500=False, include_nasdaq=False,
            include_commodities=True,
        )
        assert "Commodities" in u
        assert len(u["Commodities"]) > 0

    def test_disable_all_returns_empty(self):
        u = get_universe(
            include_sp500=False, include_nasdaq=False, include_djia=False,
            include_ftse=False, include_stoxx=False, include_fx=False,
            include_indices=False, include_commodities=False,
        )
        assert u == {}


class TestGetFlatUniverse:
    def test_returns_list(self):
        tickers = get_flat_universe(
            include_sp500=False, include_nasdaq=False, include_djia=True,
            include_ftse=False, include_stoxx=False, include_fx=False,
            include_indices=False,
        )
        assert isinstance(tickers, list)

    def test_no_duplicates(self):
        tickers = get_flat_universe(
            include_sp500=False, include_nasdaq=False,
            include_djia=True, include_ftse=False, include_stoxx=False,
            include_fx=True, include_indices=True, include_commodities=True,
        )
        assert len(tickers) == len(set(tickers)), "Duplicate tickers found in flat universe"

    def test_djia_tickers_present(self):
        tickers = get_flat_universe(
            include_sp500=False, include_nasdaq=False, include_djia=True,
            include_ftse=False, include_stoxx=False, include_fx=False,
            include_indices=False,
        )
        assert "AAPL" in tickers
        assert "MSFT" in tickers
