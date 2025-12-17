from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class LocalConfig:
    # gitlab
    gitlab_url: str
    gitlab_oauth_url: str  # URL for OAuth redirects (accessible from browser)
    gitlab_admin_token: str

    # gitlab oauth2
    gitlab_client_id: str
    gitlab_client_secret: str

    @classmethod
    def from_env(cls) -> LocalConfig:
        gitlab_url = os.environ.get("GITLAB_URL", "https://gitlab.manytask.org")
        return cls(
            # gitlab
            gitlab_url=gitlab_url,
            gitlab_oauth_url=os.environ.get("GITLAB_OAUTH_URL", gitlab_url),  # fallback to GITLAB_URL if not set
            gitlab_admin_token=os.environ["GITLAB_ADMIN_TOKEN"],
            # gitlab oauth2
            gitlab_client_id=os.environ["GITLAB_CLIENT_ID"],
            gitlab_client_secret=os.environ["GITLAB_CLIENT_SECRET"],
        )


@dataclass
class DebugLocalConfig(LocalConfig):
    # gitlab
    gitlab_url: str = "https://gitlab.manytask.org"
    gitlab_oauth_url: str = "https://gitlab.manytask.org"
    gitlab_admin_token: str = ""

    # gitlab oauth2
    gitlab_client_id: str = ""
    gitlab_client_secret: str = ""

    show_allscores: bool = True

    @classmethod
    def from_env(cls) -> LocalConfig:
        return cls()


@dataclass
class TestConfig(DebugLocalConfig):
    show_allscores: bool = True
