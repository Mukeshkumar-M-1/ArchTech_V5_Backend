"""
Settings routes — Per-project LLM configuration.

GET  /settings/{project_id}/models — List the project's LLM models. Fetched from the
                                     provider on first use and stored in settings.json;
                                     refreshed on later calls when the provider is reachable.
GET  /settings/{project_id}   — Read the project's saved LLM settings
POST /settings/{project_id}   — Save LLM settings to .ArchTech/{project_id}/settings.json
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()
log = logging.getLogger(__name__)


class LLMSettingsRequest(BaseModel):
    api_url: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    default_model: str = Field("sonnet46")


def _fetch_provider_models(project_llm_settings: dict) -> list | None:
    """Query the provider's OpenAI-compatible /models endpoint.

    Uses the project's saved api_url/api_key (falling back to the global
    defaults in system_config). Returns a list of
    {"key", "display_name", "description"} dicts, or None when the provider
    is unreachable.
    """
    from openai import OpenAI

    from system_config import API_URL, API_KEY, API_TIME_OUT

    raw_api_url = str(project_llm_settings.get("api_url") or API_URL).strip()
    if raw_api_url:
        if not raw_api_url.endswith("/"):
            if raw_api_url.endswith("v1"):
                raw_api_url += "/"
            else:
                raw_api_url += "/v1/"
        else:
            if not raw_api_url.endswith("v1/"):
                raw_api_url += "v1/"

    models_client = OpenAI(
        api_key=str(project_llm_settings.get("api_key") or API_KEY),
        base_url=raw_api_url,
        timeout=float(project_llm_settings.get("timeout") or API_TIME_OUT),
        max_retries=0,
        default_headers={"Connection": "close"}
    )
    try:
        provider_models = models_client.models.list().data
    except Exception as provider_error:
        log.warning(f"[Settings] Failed to list provider models: {provider_error}")
        return None

    return [
        {
            "key": provider_model.id,
            "display_name": provider_model.id,
            "description": "",
        }
        for provider_model in provider_models
    ]


def _persist_project_models(project_id: str, model_list: list) -> None:
    """Store the model list in .ArchTech/{project_id}/settings.json,
    preserving the project's other saved settings."""
    from system_config import get_project_settings_path

    project_settings_file_path = get_project_settings_path(project_id)
    existing_project_settings = {}
    if project_settings_file_path.exists():
        try:
            existing_project_settings = json.loads(
                project_settings_file_path.read_text(encoding="utf-8")
            )
        except Exception:
            existing_project_settings = {}
    if not isinstance(existing_project_settings, dict):
        existing_project_settings = {}

    existing_project_settings["models"] = model_list
    project_settings_file_path.parent.mkdir(parents=True, exist_ok=True)
    project_settings_file_path.write_text(
        json.dumps(existing_project_settings, indent=2), encoding="utf-8"
    )


@router.get("/settings/{project_id}/models")
def get_project_models(project_id: str):
    """Return the project's LLM model list, with settings.json as the store.

    First call (no stored list): fetches the provider's models and persists
    them to settings.json. Later calls: refreshes the stored list from the
    provider when reachable; when the provider is unreachable, returns the
    stored list unchanged.

    Also registers the project as active in ProjectContext.
    """
    from system_config import load_project_settings
    from project_context import ProjectContext

    ProjectContext.set(project_id)

    project_llm_settings = load_project_settings(project_id)
    stored_model_list = project_llm_settings.get("models") or []

    refreshed_model_list = _fetch_provider_models(project_llm_settings)
    if refreshed_model_list is None:
        if stored_model_list:
            log.warning(
                f"[Settings] Provider unreachable for project '{project_id}' — "
                "serving the stored model list from settings.json"
            )
            return stored_model_list
        return []

    _persist_project_models(project_id, refreshed_model_list)
    return refreshed_model_list


@router.get("/settings/{project_id}")
def get_project_settings(project_id: str):
    """Return the project's saved LLM settings.

    Returns {} when no settings.json exists yet.

    Also registers the project as active in ProjectContext, so the LLM
    client picks up this project's saved settings.
    """
    from system_config import load_project_settings
    from project_context import ProjectContext

    ProjectContext.set(project_id)

    return load_project_settings(project_id)


@router.post("/settings/{project_id}")
def save_project_settings(project_id: str, settings_request: LLMSettingsRequest):
    """Persist the project's LLM settings to .ArchTech/{project_id}/settings.json.

    Also registers the project as active in ProjectContext, so the LLM
    client immediately uses the freshly saved settings.
    """
    from system_config import API_TIME_OUT, get_project_settings_path, load_project_settings
    from project_context import ProjectContext

    ProjectContext.set(project_id)

    project_settings_file_path = get_project_settings_path(project_id)
    existing_project_settings = load_project_settings(project_id)
    settings_payload = {
        "api_url": settings_request.api_url.strip(),
        "api_key": settings_request.api_key.strip(),
        "timeout": API_TIME_OUT,
        "default_model": settings_request.default_model.strip(),
    }
    # Preserve the model list stored by GET /settings/{project_id}/models
    if existing_project_settings.get("models"):
        settings_payload["models"] = existing_project_settings["models"]

    project_settings_file_path.parent.mkdir(parents=True, exist_ok=True)
    project_settings_file_path.write_text(
        json.dumps(settings_payload, indent=2),
        encoding="utf-8",
    )
    log.info(f"[Settings] Saved LLM settings for project '{project_id}' to {project_settings_file_path}")
    return {"status": "ok", "project_id": project_id, "message": "Settings saved"}
