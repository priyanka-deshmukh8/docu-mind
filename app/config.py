from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://documind:documind@localhost:5432/documind"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    vector_table: str = "documind_vectors"
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 25

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
