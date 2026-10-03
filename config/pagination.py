from django.core.paginator import Paginator


SUMMARY_LIST_PAGE_SIZE = 20


def paginate_summary_list(items, page_number, *, per_page=SUMMARY_LIST_PAGE_SIZE):
    return Paginator(items, per_page).get_page(page_number)
