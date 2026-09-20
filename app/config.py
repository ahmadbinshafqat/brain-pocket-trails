from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Pocket Trails"
    database_url: str = "sqlite:///./pocket_trails.db"
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    user_agent: str = "PocketTrailsMVP/1.0"
    search_radius_m: int = 900

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
