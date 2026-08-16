from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """環境変数から読み込む設定 (.env は §3 の定義を正とする)。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://eventdeck:eventdeck@db:5432/eventdeck"
    redis_url: str = "redis://redis:6379/0"
    session_secret: str = "dev-secret-change-in-prod"

    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    mail_from: str = "noreply@eventdeck.local"
    base_url: str = "http://localhost"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    fcm_credentials_json: str = ""

    app_env: str = "dev"

    cookie_secure: bool | None = None
    """セッションCookieの Secure フラグ。未指定なら app_env != 'dev' で自動判定。
    HTTPSなしのIP直アクセスでデモする場合は COOKIE_SECURE=false を指定する。"""

    @property
    def session_cookie_secure(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.app_env != "dev"


settings = Settings()
