"""
Standard pagination for all list endpoints. Page size kept modest
(low-bandwidth optimisation — design doc Section 14).
"""
from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
