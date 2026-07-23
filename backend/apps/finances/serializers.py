from rest_framework import serializers

from .models import CashbookEntry, ExpenseCategory


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ["id", "name", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class CashbookEntrySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    recorded_by_name = serializers.CharField(source="recorded_by.name", read_only=True, default=None)

    class Meta:
        model = CashbookEntry
        fields = [
            "id", "direction", "category", "category_name", "amount",
            "occurred_on", "description", "payment_method",
            "recorded_by", "recorded_by_name", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "recorded_by", "created_at", "updated_at"]

    def validate(self, attrs):
        direction = attrs.get("direction", getattr(self.instance, "direction", CashbookEntry.EXPENSE))
        category = attrs.get("category", getattr(self.instance, "category", None))
        # An income entry is uncategorised; an expense category on an
        # income row would be meaningless, so reject it early.
        if direction == CashbookEntry.INCOME and category is not None:
            raise serializers.ValidationError(
                {"category": "Income entries are not categorised."}
            )
        return attrs
