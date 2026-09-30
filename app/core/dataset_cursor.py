import base64
import binascii
import json
import re
from datetime import UTC, datetime
from uuid import UUID

_CURSOR_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_MAX_CURSOR_LENGTH = 512


def encode_dataset_cursor(created_at: datetime, dataset_id: UUID) -> str:
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("Cursor timestamps must be timezone-aware.")

    payload = json.dumps(
        {
            "created_at": created_at.astimezone(UTC).isoformat(timespec="microseconds"),
            "id": str(dataset_id),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def decode_dataset_cursor(cursor: str) -> tuple[datetime, UUID]:
    if (
        not cursor
        or len(cursor) > _MAX_CURSOR_LENGTH
        or _CURSOR_PATTERN.fullmatch(cursor) is None
    ):
        raise ValueError("Invalid dataset cursor.")

    try:
        encoded = cursor.encode("ascii")
        payload = base64.b64decode(
            encoded + b"=" * (-len(encoded) % 4),
            altchars=b"-_",
            validate=True,
        )
        decoded = json.loads(payload)
        if not isinstance(decoded, dict) or set(decoded) != {"created_at", "id"}:
            raise ValueError("Invalid dataset cursor.")
        if not isinstance(decoded["created_at"], str) or not isinstance(
            decoded["id"], str
        ):
            raise ValueError("Invalid dataset cursor.")

        created_at = datetime.fromisoformat(decoded["created_at"])
        dataset_id = UUID(decoded["id"])
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("Invalid dataset cursor.")
        if encode_dataset_cursor(created_at, dataset_id) != cursor:
            raise ValueError("Invalid dataset cursor.")
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        binascii.Error,
        TypeError,
        ValueError,
    ) as error:
        raise ValueError("Invalid dataset cursor.") from error

    return created_at.astimezone(UTC), dataset_id
