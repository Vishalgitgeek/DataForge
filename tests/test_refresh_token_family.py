from sqlalchemy.dialects.postgresql import UUID

from app.models import Base, RefreshToken


def test_refresh_token_family_id_is_required_uuid_with_family_revocation_index() -> None:
    table = Base.metadata.tables["refresh_tokens"]
    family_id = table.c.family_id

    assert isinstance(family_id.type, UUID)
    assert family_id.nullable is False
    assert family_id.default is not None

    family_index = next(
        index
        for index in table.indexes
        if index.name == "ix_refresh_tokens_family_revoked"
    )
    assert [column.name for column in family_index.columns] == [
        "family_id",
        "revoked_at",
    ]


def test_refresh_token_existing_constraints_and_relationship_are_preserved() -> None:
    table = Base.metadata.tables["refresh_tokens"]

    assert "token_hash" in table.c
    assert table.c.token_hash.unique is True
    assert any(
        foreign_key.target_fullname == "users.id"
        for foreign_key in table.c.user_id.foreign_keys
    )
    assert RefreshToken.user.property.back_populates == "refresh_tokens"
