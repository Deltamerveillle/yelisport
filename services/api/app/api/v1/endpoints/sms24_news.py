"""Public read-only feed of explicitly published SMS24 news articles."""
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.sports_news import SportsNewsArticle
from app.models.sports_live import SportsDataSource

router = APIRouter(prefix="/sms24", tags=["sms24-news"])


class SMS24NewsItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    excerpt: str | None
    source_url: str
    publisher_name: str | None
    image_url: str | None
    published_at: datetime | None
    fetched_at: datetime
    source_name: str


@router.get("/news", response_model=list[SMS24NewsItem])
async def list_news(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[SMS24NewsItem]:
    """No pending/withheld article can reach the public feed."""
    rows = (await session.execute(
        select(SportsNewsArticle, SportsDataSource.name)
        .join(SportsDataSource, SportsDataSource.id == SportsNewsArticle.source_id)
        .where(SportsNewsArticle.publication_status == "published")
        .order_by(
            SportsNewsArticle.published_at.desc().nullslast(),
            SportsNewsArticle.fetched_at.desc(),
            SportsNewsArticle.id,
        )
        .limit(limit)
        .offset(offset)
    )).all()
    return [
        SMS24NewsItem(
            id=article.id,
            title=article.title,
            excerpt=article.excerpt,
            source_url=article.source_url,
            publisher_name=article.publisher_name,
            image_url=article.image_url,
            published_at=article.published_at,
            fetched_at=article.fetched_at,
            source_name=source_name,
        )
        for article, source_name in rows
    ]
