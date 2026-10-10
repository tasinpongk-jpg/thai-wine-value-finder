import access


def test_public_mode_from_env_or_secrets():
    assert access.is_public({"WINEVALUE_PUBLIC_MODE": "1"})
    assert access.is_public({"WINEVALUE_PUBLIC_MODE": "true"})
    assert not access.is_public({"WINEVALUE_PUBLIC_MODE": "0"})
    assert not access.is_public({})
    assert access.is_public({}, {"public_mode": True})


def test_password_from_secrets_beats_env_and_blank_is_none():
    assert access.cellar_password({"WINEVALUE_CELLAR_PASSWORD": "env"}) == "env"
    assert access.cellar_password({"WINEVALUE_CELLAR_PASSWORD": "env"},
                                  {"cellar_password": "sec"}) == "sec"
    assert access.cellar_password({"WINEVALUE_CELLAR_PASSWORD": "  "}) is None
    assert access.cellar_password({}) is None


def test_broken_secrets_object_is_ignored():
    class Exploding:
        def get(self, key):
            raise FileNotFoundError("no secrets.toml")

        def __len__(self):
            raise FileNotFoundError("no secrets.toml")

    assert not access.is_public({}, Exploding())
    assert access.cellar_password({}, Exploding()) is None


def test_password_matches():
    assert access.password_matches("s3cret", "s3cret")
    assert not access.password_matches("nope", "s3cret")
    assert not access.password_matches("", "s3cret")
    assert not access.password_matches("x", None)


def test_cellar_mode():
    assert access.cellar_mode(public=True, password="pw", unlocked=True) == access.HIDDEN
    assert access.cellar_mode(public=False, password="pw", unlocked=False) == access.LOCKED
    assert access.cellar_mode(public=False, password="pw", unlocked=True) == access.OPEN
    assert access.cellar_mode(public=False, password=None, unlocked=False) == access.OPEN
