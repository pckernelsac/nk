"""Flask-SQLAlchemy–compatible pagination for plain SQLAlchemy queries."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any


class Pagination:
    def __init__(self, page: int, per_page: int, total: int, items: list[Any]):
        self.page = max(1, int(page))
        self.per_page = max(1, int(per_page))
        self.total = int(total)
        self.items = items
        self.pages = (self.total + self.per_page - 1) // self.per_page if self.per_page else 0
        self.has_prev = self.page > 1
        self.has_next = self.page < self.pages
        self.prev_num = self.page - 1 if self.has_prev else None
        self.next_num = self.page + 1 if self.has_next else None

    def iter_pages(
        self,
        left_edge: int = 2,
        left_current: int = 2,
        right_current: int = 5,
        right_edge: int = 2,
    ) -> Iterator[int | None]:
        last = 0
        for num in range(1, self.pages + 1):
            if (
                num <= left_edge
                or (self.page - left_current - 1 < num < self.page + right_current)
                or num > self.pages - right_edge
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num


def paginate_query(query, page: int, per_page: int, *, error_out: bool = False) -> Pagination:
    page = max(1, int(page))
    per_page = max(1, int(per_page))
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return Pagination(page=page, per_page=per_page, total=total, items=items)
