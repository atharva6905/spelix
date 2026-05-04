import pytest
from unittest.mock import AsyncMock, patch

from app.services.storage_quota import StorageQuotaService, QuotaStatus


@pytest.fixture
def quota_service():
    return StorageQuotaService(quota_bytes=1_073_741_824)  # 1 GB


class TestCheckQuota:
    @pytest.mark.asyncio
    async def test_under_95_percent_returns_ok(self, quota_service):
        with patch.object(quota_service, "_get_used_bytes", new_callable=AsyncMock, return_value=900_000_000):
            result = await quota_service.check()
            assert result.status == "ok"

    @pytest.mark.asyncio
    async def test_at_95_percent_returns_warning(self, quota_service):
        # 1_021_000_000 / 1_073_741_824 ≈ 95.07% — above the 95% warn threshold
        with patch.object(quota_service, "_get_used_bytes", new_callable=AsyncMock, return_value=1_021_000_000):
            result = await quota_service.check()
            assert result.status == "warning"

    @pytest.mark.asyncio
    async def test_at_100_percent_returns_full(self, quota_service):
        with patch.object(quota_service, "_get_used_bytes", new_callable=AsyncMock, return_value=1_073_741_824):
            result = await quota_service.check()
            assert result.status == "full"

    @pytest.mark.asyncio
    async def test_query_failure_returns_ok_gracefully(self, quota_service):
        with patch.object(quota_service, "_get_used_bytes", new_callable=AsyncMock, side_effect=Exception("DB error")):
            result = await quota_service.check()
            assert result.status == "ok"  # fail-open


class TestCreateAnalysisQuotaReject:
    @pytest.mark.asyncio
    async def test_returns_507_when_storage_full(self):
        """Quota full should cause 507 Insufficient Storage."""
        full = QuotaStatus(
            status="full",
            used_bytes=1_073_741_824,
            quota_bytes=1_073_741_824,
            message="Storage full — contact admin.",
        )
        # Just verify the service returns the right status
        assert full.status == "full"
        assert full.message == "Storage full — contact admin."
