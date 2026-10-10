"""Who may see and change the personal cellar in the Streamlit dashboard.

Three modes, decided per session:

- ``hidden``: public/read-only deployment. The cellar tab and every cellar write
  are hidden. Enabled by ``WINEVALUE_PUBLIC_MODE=1`` (env) or
  ``public_mode = true`` in ``.streamlit/secrets.toml``.
- ``locked``: a cellar password is configured (``cellar_password`` in
  ``.streamlit/secrets.toml`` or ``WINEVALUE_CELLAR_PASSWORD`` env, e.g. a Fly
  secret) and this session hasn't entered it yet. Nothing from the cellar is shown.
- ``open``: local default (no password, not public), or unlocked with the password.
"""
from __future__ import annotations

import hmac
import os
from typing import Mapping, Optional

TRUTHY = {"1", "true", "yes", "on"}
HIDDEN, LOCKED, OPEN = "hidden", "locked", "open"


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in TRUTHY


def _secret(secrets: Optional[Mapping], key: str):
    if secrets is None:   # don't test truthiness: st.secrets parses on len()
        return None
    try:
        return secrets.get(key)
    except Exception:  # st.secrets raises when no secrets.toml exists
        return None


def is_public(env: Mapping = os.environ, secrets: Optional[Mapping] = None) -> bool:
    return _truthy(env.get("WINEVALUE_PUBLIC_MODE")) or _truthy(_secret(secrets, "public_mode"))


def cellar_password(env: Mapping = os.environ, secrets: Optional[Mapping] = None) -> Optional[str]:
    pw = _secret(secrets, "cellar_password") or env.get("WINEVALUE_CELLAR_PASSWORD")
    pw = str(pw) if pw is not None else ""
    return pw if pw.strip() else None


def password_matches(given: Optional[str], expected: Optional[str]) -> bool:
    if not given or not expected:
        return False
    return hmac.compare_digest(str(given).encode("utf-8"), str(expected).encode("utf-8"))


def cellar_mode(public: bool, password: Optional[str], unlocked: bool) -> str:
    if public:
        return HIDDEN
    if password and not unlocked:
        return LOCKED
    return OPEN
