from pydantic import BaseModel


class PageMeta(BaseModel):
    """一覧系レスポンスの meta (03_API仕様書 §1.4)。"""

    page: int
    per_page: int
    total: int
