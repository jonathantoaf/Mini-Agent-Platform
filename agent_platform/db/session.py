from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    def __init__(self, db_url: str, pool_size: int, max_overflow: int, debug: bool) -> None:
        self._engine = create_async_engine(
            db_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            echo=debug,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a per-request session. Commits on success, rolls back on error."""
        session: AsyncSession = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:  # pragma: no cover — DB error safety net
            await session.rollback()
            raise
        finally:
            await session.close()

    async def dispose(self) -> None:
        await self._engine.dispose()
