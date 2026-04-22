from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App config
    APP_NAME: str = "Docmatch AI"

    # API Keys
    GROQ_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    GOOGLE_MAPS_API_KEY: str = ""

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    # This tells Pydantic to read from the .env file
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
