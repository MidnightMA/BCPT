"""Tests for permission inspection and capability guards."""

import pytest

from app.core.exceptions import PermissionDeniedError
from app.services.permission_service import PermissionService
from app.telegram.adapter import ChatPermissionsDTO


@pytest.mark.asyncio
async def test_permission_service_allowed(mock_adapter):
    """Verify operations succeed when permissions are granted."""
    mock_adapter.permissions = ChatPermissionsDTO(
        can_send_messages=True,
        can_send_media=True,
        can_delete_messages=True,
        can_pin_messages=True,
    )
    svc = PermissionService(mock_adapter)

    # These should not raise exceptions
    await svc.ensure_can_send(101)
    await svc.ensure_can_send_media(101)
    await svc.ensure_can_delete(101)
    await svc.ensure_can_pin(101)


@pytest.mark.asyncio
async def test_permission_service_denied(mock_adapter):
    """Verify PermissionDeniedError is raised when capability is revoked."""
    mock_adapter.permissions = ChatPermissionsDTO(
        can_send_messages=False,
        can_send_media=False,
        can_post_messages=False,
        can_delete_messages=False,
        can_pin_messages=False,
    )
    svc = PermissionService(mock_adapter)

    with pytest.raises(PermissionDeniedError, match="cannot send messages"):
        await svc.ensure_can_send(101)

    with pytest.raises(PermissionDeniedError, match="cannot send media"):
        await svc.ensure_can_send_media(101)

    with pytest.raises(PermissionDeniedError, match="cannot delete messages"):
        await svc.ensure_can_delete(101)

    with pytest.raises(PermissionDeniedError, match="cannot pin messages"):
        await svc.ensure_can_pin(101)
