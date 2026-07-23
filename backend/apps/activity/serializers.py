from rest_framework import serializers

from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.name", read_only=True, default=None)

    class Meta:
        model = ActivityLog
        fields = [
            "id", "action", "summary", "is_major", "actor", "actor_name",
            "target_type", "target_id", "metadata", "created_at",
        ]
        read_only_fields = fields
