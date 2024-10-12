from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str

    SLEEP_TIME: list[int] = [3600, 4000]
    START_DELAY: list[int] = [5, 20]
    RANDOM_TAPS_COUNT: list[int] = [40, 55]
    MIN_ENERGY: int = 10
    REF_ID: str = 'cm91dGU9JTJGdGFwLWdhbWUlM0ZpbnZpdGVyVXNlcklkJTNENzI1MzY1MDQxMCUyNnJjb2RlJTNE'


settings = Settings()
