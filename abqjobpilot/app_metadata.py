"""Static application metadata and GitHub remote normalization."""

from __future__ import annotations

import re
from urllib.parse import urlsplit


def github_url_from_remote(remote: str) -> str | None:
    value = remote.strip()
    if value.startswith("git@github.com:"):
        repository_path = value.removeprefix("git@github.com:")
    else:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.username or parsed.password:
            return None
        repository_path = parsed.path.lstrip("/")
    repository_path = repository_path.rstrip("/")
    if repository_path.endswith(".git"):
        repository_path = repository_path[:-4]
    parts = repository_path.split("/")
    if len(parts) != 2 or any(not re.fullmatch(r"[A-Za-z0-9_.-]+", part) or part in {".", ".."} for part in parts):
        return None
    return f"https://github.com/{parts[0]}/{parts[1]}"


# Verified from the stable checkout's origin fetch remote on 2026-10-02.
STABLE_GITHUB_URL = github_url_from_remote("https://github.com/BrunelXian/AbqJobPilot.git")
