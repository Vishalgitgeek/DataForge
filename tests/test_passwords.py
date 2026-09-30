from app.core.passwords import hash_password, verify_password


def test_password_hash_is_not_plaintext_and_can_be_verified() -> None:
    password = "correct horse battery staple"

    password_hash = hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$argon2id$")
    assert verify_password(password, password_hash) is True
    assert verify_password("wrong password", password_hash) is False
