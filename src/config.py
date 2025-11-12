import os
import yaml
from dotenv import load_dotenv

def load_config():
    """Loads configuration from .env and config.yaml."""
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(dotenv_path=dotenv_path)

    config = {
        "environment": os.getenv("ENVIRONMENT", "development"),
        "api_base_url": os.getenv("API_BASE_URL"),
        "openapi_spec_path": os.getenv("OPENAPI_SPEC_PATH"),
        "llm_provider": os.getenv("LLM_PROVIDER", "openai"),
        "llm_model": os.getenv("LLM_MODEL", "gpt-4o"),
        "llm_temperature": float(os.getenv("LLM_TEMPERATURE", 0.0)),
        "session_timeout_minutes": int(os.getenv("SESSION_TIMEOUT_MINUTES", 10)),
        "enable_custom_tasks": os.getenv("ENABLE_CUSTOM_TASKS", "true").lower() == "true",
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "faq_path": os.getenv("FAQ_PATH", "./config/faq.md"),
        "rag_top_k": int(os.getenv("RAG_TOP_K", 3)),
        "vectorstore_path": os.getenv("VECTORSTORE_PATH", "./vectorstore"),
        "faq_vector_collection": os.getenv("FAQ_VECTOR_COLLECTION", "faqs"),
    }

    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            yaml_config = yaml.safe_load(f)
            if yaml_config:
                config.update(yaml_config)

    return config

APP_CONFIG = load_config()
