"""Read Z3RO's explicit Windows app catalogue.

The catalogue is intentionally data-driven: the model can request only an
app name that exists in ``apps.txt``; it can never supply a program path or
command of its own.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


CATALOG_PATH = Path(__file__).with_name("apps.txt")
VALID_STATUSES = {"enabled", "blocked", "reference"}
VALID_KINDS = {"app_id", "path"}


@dataclass(frozen=True)
class CatalogApp:
    """One Start-menu application recorded in the catalogue."""

    name: str
    status: str
    kind: str
    target: str
    aliases: tuple[str, ...]


def _normalize(value: str) -> str:
    """Return a case-insensitive, whitespace-stable app name."""

    return " ".join(value.casefold().split())


@lru_cache(maxsize=1)
def load_catalog() -> tuple[CatalogApp, ...]:
    """Load and validate the checked-in application catalogue."""

    entries = []
    names = set()

    for line_number, raw_line in enumerate(
        CATALOG_PATH.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        parts = [part.strip() for part in line.split("|")]

        if len(parts) != 5:
            raise ValueError(
                f"Invalid catalog entry on line {line_number}."
            )

        status, name, kind, target, aliases_text = parts

        if status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status on line {line_number}: {status}."
            )

        if kind not in VALID_KINDS:
            raise ValueError(
                f"Invalid launch kind on line {line_number}: {kind}."
            )

        if not name or not target:
            raise ValueError(
                f"Name and target are required on line {line_number}."
            )

        normalized_name = _normalize(name)

        if normalized_name in names:
            raise ValueError(
                f"Duplicate app name on line {line_number}: {name}."
            )

        names.add(normalized_name)
        aliases = tuple(
            alias.strip()
            for alias in aliases_text.split(",")
            if alias.strip()
        )

        entries.append(
            CatalogApp(
                name=name,
                status=status,
                kind=kind,
                target=target,
                aliases=aliases,
            )
        )

    if not entries:
        raise ValueError("The app catalogue is empty.")

    return tuple(entries)


def find_app(query: str) -> CatalogApp | None:
    """Find an app by its recorded name or one of its aliases."""

    if not isinstance(query, str):
        return None

    normalized_query = _normalize(query)

    if not normalized_query:
        return None

    for app in load_catalog():
        if normalized_query == _normalize(app.name):
            return app

        if any(
            normalized_query == _normalize(alias)
            for alias in app.aliases
        ):
            return app

    return None


def enabled_apps() -> tuple[CatalogApp, ...]:
    """Return the apps Z3RO is currently allowed to launch."""

    return tuple(
        app
        for app in load_catalog()
        if app.status == "enabled"
    )


def app_catalog_prompt() -> str:
    """Give the local model the exact names it may use for ``open_app``."""

    app_names = "\n".join(
        f"- {app.name}"
        for app in enabled_apps()
    )

    return (
        "For open_app, use an app name from this exact "
        "approved catalogue. Never invent a name or path:\n"
        f"{app_names}"
    )
