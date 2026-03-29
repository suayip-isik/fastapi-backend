"""BaseRepository.get_page() window function testleri."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.repositories.user import UserRepository

_PWD = hash_password("TestPass123!")


async def _create_users(repo: UserRepository, count: int, prefix: str = "user") -> None:
    """Verilen prefix ve sayıda test kullanıcısı oluşturur."""
    for i in range(count):
        await repo.create(
            email=f"{prefix}{i}@paginate.test",
            hashed_password=_PWD,
        )


class TestGetPage:
    async def test_empty_table_returns_empty_list_and_zero_total(
        self, db_session: AsyncSession
    ) -> None:
        """Tabloda hiç kayıt yokken get_page() → ([], 0) döndürmeli."""
        repo = UserRepository(db_session)
        items, total = await repo.get_page(offset=0, limit=20)
        assert items == []
        assert total == 0

    async def test_first_page_returns_correct_item_count(self, db_session: AsyncSession) -> None:
        """25 kayıt, limit=10 ile ilk sayfa → 10 item, total=25."""
        repo = UserRepository(db_session)
        await _create_users(repo, 25, prefix="p1_")
        items, total = await repo.get_page(offset=0, limit=10)
        assert len(items) == 10
        assert total == 25

    async def test_second_page_returns_correct_item_count(self, db_session: AsyncSession) -> None:
        """25 kayıt, limit=10 ile ikinci sayfa → 10 item, total=25."""
        repo = UserRepository(db_session)
        await _create_users(repo, 25, prefix="p2_")
        items, total = await repo.get_page(offset=10, limit=10)
        assert len(items) == 10
        assert total == 25

    async def test_last_page_returns_partial_results(self, db_session: AsyncSession) -> None:
        """25 kayıt, limit=10, offset=20 → son sayfada 5 item, total=25."""
        repo = UserRepository(db_session)
        await _create_users(repo, 25, prefix="p3_")
        items, total = await repo.get_page(offset=20, limit=10)
        assert len(items) == 5
        assert total == 25

    async def test_limit_larger_than_total_returns_all(self, db_session: AsyncSession) -> None:
        """5 kayıt, limit=100 → tümü döner, total=5."""
        repo = UserRepository(db_session)
        await _create_users(repo, 5, prefix="p4_")
        items, total = await repo.get_page(offset=0, limit=100)
        assert len(items) == 5
        assert total == 5

    async def test_total_is_consistent_across_pages(self, db_session: AsyncSession) -> None:
        """Window function sayesinde her sayfada total aynı olmalı."""
        repo = UserRepository(db_session)
        await _create_users(repo, 15, prefix="p5_")
        _, total_p1 = await repo.get_page(offset=0, limit=10)
        _, total_p2 = await repo.get_page(offset=10, limit=10)
        assert total_p1 == total_p2 == 15

    async def test_offset_beyond_total_returns_empty(self, db_session: AsyncSession) -> None:
        """Offset, toplam kayıt sayısını aşarsa → boş liste, total=0."""
        repo = UserRepository(db_session)
        await _create_users(repo, 5, prefix="p6_")
        items, total = await repo.get_page(offset=100, limit=10)
        assert items == []
        assert total == 0
