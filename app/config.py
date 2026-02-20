from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./coffee.db"
    app_title: str = "Coffee Brewing Tracker"
    secret_key: str = "change-me-in-production"
    app_password: str = "coffee4data"
    port: int = 8000
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
