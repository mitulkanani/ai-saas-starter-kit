from app.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_is_salted_and_verifiable():
    a = hash_password("a-very-long-password")
    b = hash_password("a-very-long-password")
    assert a != b
    assert verify_password("a-very-long-password", a)
    assert not verify_password("wrong-password", a)


def test_access_token_round_trip():
    token = create_access_token("user-123", "owner@example.com")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["email"] == "owner@example.com"
