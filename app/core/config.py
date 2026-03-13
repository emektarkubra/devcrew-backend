from pydantic_settings import BaseSettings, SettingsConfigDict
 
class Settings(BaseSettings): # env variables okuyup Python objesine çeviren sınıf (settings.DATABASE_URL)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore") # .env dosyasından oku #Fazladan gelen değişken varsa ignore et
 
    DATABASE_URL: str
    SECRET_KEY: str
    GITHUB_CLIENT_ID: str
    GITHUB_CLIENT_SECRET: str
    FASTAPI_PORT: int = 8000
 
settings = Settings()