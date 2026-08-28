from rest_framework.pagination import PageNumberPagination


class LimitPageNumberPagination(PageNumberPagination):
    """
    Кастомная пагинация с поддержкой параметра limit.
    """

    page_size_query_param = 'limit'
    page_query_param = 'page'
    max_page_size = 100
