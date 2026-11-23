from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """Where the agent sends its tool calls. Local defaults; set the Azure URLs in .env to use the cloud.

    In the cloud, API_BASE_URL must be the API Gateway (APIM) URL, never the Billing API directly.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_base_url: str = "http://localhost:8000/api/v1"
    apim_subscription_key: str | None = None   # sent as Ocp-Apim-Subscription-Key when set
    mcp_url: str = "http://127.0.0.1:8001/mcp"
    llm_provider: str = "rule-based"           # "rule-based" (no LLM, free) or "gemini"
    gemini_api_key: SecretStr | None = None    # from Google AI Studio; keep it in .env only
    gemini_model: str = "gemini-3.5-flash-lite"
    http_timeout_seconds: float = 45.0         # cloud apps scale to zero; a cold start takes ~20-30 s
