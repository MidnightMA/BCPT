"""Tests for list pagination logic and edge cases."""

from app.utils.pagination import paginate_list


def test_empty_list_pagination():
    """Verify empty list produces 1 total page with empty items."""
    result = paginate_list([], page=1, per_page=10)
    assert result.items == []
    assert result.page == 1
    assert result.total_pages == 1
    assert result.total_items == 0
    assert result.has_prev is False
    assert result.has_next is False


def test_single_page_pagination():
    """Verify list with fewer items than per_page fits on page 1."""
    items = ["a", "b", "c"]
    result = paginate_list(items, page=1, per_page=5)
    assert result.items == ["a", "b", "c"]
    assert result.page == 1
    assert result.total_pages == 1
    assert result.has_prev is False
    assert result.has_next is False


def test_multi_page_pagination():
    """Verify multi-page list computes total pages and page slices properly."""
    items = list(range(25))  # 25 items, 10 per page -> 3 pages
    page1 = paginate_list(items, page=1, per_page=10)
    assert page1.items == list(range(10))
    assert page1.total_pages == 3
    assert page1.has_prev is False
    assert page1.has_next is True
    assert page1.next_page == 2

    page2 = paginate_list(items, page=2, per_page=10)
    assert page2.items == list(range(10, 20))
    assert page2.has_prev is True
    assert page2.has_next is True

    page3 = paginate_list(items, page=3, per_page=10)
    assert page3.items == list(range(20, 25))
    assert page3.has_prev is True
    assert page3.has_next is False


def test_page_clamping_boundary():
    """Verify out-of-range page numbers clamp to [1, total_pages]."""
    items = list(range(10))
    # Requesting negative or zero page clamps to 1
    res_low = paginate_list(items, page=0, per_page=5)
    assert res_low.page == 1

    # Requesting page beyond max clamps to total_pages
    res_high = paginate_list(items, page=999, per_page=5)
    assert res_high.page == 2
