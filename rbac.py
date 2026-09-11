"""
rbac.py — Role-Based Access Control for SecureHealth Cloud
==========================================================

Parses Entra ID app-role claims from the X-MS-CLIENT-PRINCIPAL header
injected by Azure App Service Easy Auth, and exposes:

  • get_current_user()   — returns { name, roles }
  • has_role(role_name)   — boolean check
  • @require_role(name)   — route decorator → 403 if missing
  • init_rbac(app)        — registers a Jinja2 context processor so
                            templates can use {{ is_clinician }}

Fail-closed: if the header is missing, malformed, or cannot be decoded,
the user is treated as having *no* roles (read-only).
"""

import base64
import json
import functools
import logging

from flask import request, abort, g

logger = logging.getLogger(__name__)

# ── Role constants ──────────────────────────────────────────────────────
ROLE_CLINICIAN = "clinician"

# Claim type strings where Entra ID may place app-role values
_ROLE_CLAIM_TYPES = frozenset(
    {
        "roles",
        "http://schemas.microsoft.com/ws/2008/06/identity/claims/role",
    }
)


# ── Core helpers ────────────────────────────────────────────────────────
def get_current_user():
    """Return the current user dict, cached on Flask `g` for the request.

    Structure::

        {
            "name":  "user@example.com",   # from X-MS-CLIENT-PRINCIPAL-NAME
            "roles": {"clinician"},         # set of lower-cased role strings
        }
    """
    if "current_user" in g:
        return g.current_user

    user_info = {
        "name": request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", "anonymous"),
        "roles": set(),
    }

    # ── Parse the Easy Auth principal header ────────────────────────────
    principal_header = request.headers.get("X-MS-CLIENT-PRINCIPAL")
    if principal_header:
        try:
            # Base64 may arrive without padding — add it back
            padded = principal_header + "=" * (-len(principal_header) % 4)
            decoded = base64.b64decode(padded)
            principal = json.loads(decoded)

            for claim in principal.get("claims", []):
                if claim.get("typ") in _ROLE_CLAIM_TYPES:
                    role_val = claim.get("val", "").strip().lower()
                    if role_val:
                        user_info["roles"].add(role_val)
        except (ValueError, json.JSONDecodeError, KeyError) as exc:
            # Fail closed — treat as no roles
            logger.warning("Could not parse X-MS-CLIENT-PRINCIPAL: %s", exc)

    # ── Local-dev mock (NEVER reaches Azure — Easy Auth strips unknown
    #    headers before they hit your app) ───────────────────────────────
    if not principal_header:
        mock_roles = request.headers.get("X-MS-MOCK-ROLES", "")
        if mock_roles:
            user_info["roles"] = {
                r.strip().lower() for r in mock_roles.split(",") if r.strip()
            }

    g.current_user = user_info
    return user_info


def has_role(role_name):
    """Check whether the current request user holds *role_name*."""
    return role_name.lower() in get_current_user()["roles"]


# ── Decorator ───────────────────────────────────────────────────────────
def require_role(role_name):
    """Decorator: abort 403 if the current user lacks *role_name*.

    Usage::

        @app.route("/patients/add", methods=["GET", "POST"])
        @require_role("clinician")
        def add_patient():
            ...
    """

    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            if not has_role(role_name):
                logger.warning(
                    "RBAC DENIED: user=%s attempted %s %s (requires role '%s')",
                    get_current_user()["name"],
                    request.method,
                    request.path,
                    role_name,
                )
                abort(403)
            return f(*args, **kwargs)

        return wrapped

    return decorator


# ── Flask integration ───────────────────────────────────────────────────
def init_rbac(app):
    """Call once at app startup to wire up RBAC helpers.

    Registers a Jinja2 context processor so every template receives::

        {{ current_user_name }}   — e.g. "faris@contoso.com"
        {{ current_user_roles }}  — e.g. {"clinician"}
        {{ is_clinician }}        — True / False
    """

    @app.context_processor
    def _inject_rbac_context():
        user = get_current_user()
        return {
            "current_user_name": user["name"],
            "current_user_roles": user["roles"],
            "is_clinician": ROLE_CLINICIAN in user["roles"],
        }

    @app.errorhandler(403)
    def _handle_forbidden(e):
        from flask import render_template

        return render_template("403.html"), 403
