"""OpenDoc - Application settings via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Google AI
    google_api_key: str

    # Database
    database_url: str = "postgresql://opendoc:changeme@localhost:5432/opendoc"

    # Application
    app_env: str = "development"
    log_level: str = "INFO"

    # SAT Portal Navigator
    sat_download_dir: str = "/app/data/sat_downloads"
    sat_screenshot_dir: str = "/app/data/sat_screenshots"
    sat_audit_dir: str = "/app/data/sat_audit"
    sat_session_timeout: int = 300
    sat_headless: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
