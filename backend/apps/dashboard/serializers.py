"""
These serializers only ever wrap plain dicts built from aggregate
querysets in views.py — none of them are bound to a model or a
queryset directly, since every endpoint in this app reads across
Sale / SaleLineItem / Purchase / Product from other apps rather than
owning its own table. All monetary fields are IntegerField, matching
the rest of the schema — XAF has no subunit (apps.core.utils.xaf).
"""
from rest_framework import serializers


class DashboardSummarySerializer(serializers.Serializer):
    period = serializers.CharField()
    revenue = serializers.IntegerField()
    revenue_change_pct = serializers.FloatField(allow_null=True)
    transaction_count = serializers.IntegerField()
    transaction_count_change = serializers.IntegerField()
    average_sale = serializers.IntegerField()
    top_product_name = serializers.CharField(allow_null=True)


class TopProductSerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    units_sold = serializers.IntegerField()
    revenue = serializers.IntegerField()


class PaymentBreakdownSerializer(serializers.Serializer):
    payment_method = serializers.CharField()
    revenue = serializers.IntegerField()
    transaction_count = serializers.IntegerField()


class SalesChartPointSerializer(serializers.Serializer):
    label = serializers.CharField()
    revenue = serializers.IntegerField()


class StockAlertSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    stock_level = serializers.IntegerField()
    low_stock_threshold = serializers.IntegerField()
    status = serializers.CharField()  # "low" | "out"
