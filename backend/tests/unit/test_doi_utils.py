"""Tests for DOI normalization (FR-EXPV-02 dedup key)."""
import pytest

from app.utils.doi import DoiValidationError, normalize_doi


class TestNormalizeDoi:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("10.1519/JSC.0b013e31818546bb", "10.1519/jsc.0b013e31818546bb"),
            ("  10.1007/s00421-019-04218-y  ", "10.1007/s00421-019-04218-y"),
            ("https://doi.org/10.3390/sports5010025", "10.3390/sports5010025"),
            ("http://dx.doi.org/10.7717/peerj.708", "10.7717/peerj.708"),
            ("doi:10.1249/00005768-200106000-00001", "10.1249/00005768-200106000-00001"),
            ("DOI:10.1519/14513.1", "10.1519/14513.1"),
        ],
    )
    def test_normalizes(self, raw: str, expected: str) -> None:
        assert normalize_doi(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        ["", "   ", "not-a-doi", "10./missing-prefix", "10.12/short-prefix",
         "https://doi.org/", "10.1234/", "10.1234/has space"],
    )
    def test_rejects_malformed(self, raw: str) -> None:
        with pytest.raises(DoiValidationError):
            normalize_doi(raw)
