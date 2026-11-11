import logging

logger = logging.getLogger(__name__)

_VISIBILITY_BY_ROLE = {
    "operator": ["public", "internal"],
    "compliance_lead": ["public", "internal", "compliance_only"],
    "risk_lead": ["public", "internal", "risk_only"],
    "admin": ["public", "internal", "risk_only", "compliance_only"],
}


def visible_to(role: str) -> list[str]:
    """Return only document visibility levels available to a role."""
    livelli = _VISIBILITY_BY_ROLE.get(role)
    if livelli is None:
        logger.warning("ruolo_sconosciuto", extra={"role": role})
        return ["public"]
    return livelli.copy()
