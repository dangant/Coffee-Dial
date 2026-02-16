from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./coffee.db"
    app_title: str = "Coffee Brewing Tracker"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
