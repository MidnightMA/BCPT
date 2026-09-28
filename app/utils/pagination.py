"""Generic pagination helpers for lists, dialogs, and messages."""

import math
from dataclasses import dataclass
from typing import Generic, List, TypeVar

T = TypeVar("T")


@dataclass
class PaginatedResult(Generic[T]):
    """Container holding a slice of items along with pagination metadata."""
    items: List[T]
    page: int
    per_page: int
    total_items: int
    total_pages: int

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def prev_page(self) -> int:
        return max(1, self.page - 1)

    @property
    def next_page(self) -> int:
        return min(self.total_pages, self.page + 1)


def paginate_list(items: List[T], page: int = 1, per_page: int = 10) -> PaginatedResult[T]:
    """
    Paginate an in-memory list with boundary safety.
    Guarantees page is at least 1 and total_pages is at least 1.
    """
    per_page = max(1, per_page)
    total_items = len(items)
    total_pages = max(1, math.ceil(total_items / per_page))

    # Clamp page into valid range [1, total_pages]
    clamped_page = max(1, min(page, total_pages))

    start_idx = (clamped_page - 1) * per_page
    end_idx = start_idx + per_page
    page_items = items[start_idx:end_idx]

    return PaginatedResult(
        items=page_items,
        page=clamped_page,
        per_page=per_page,
        total_items=total_items,
        total_pages=total_pages,
    )
