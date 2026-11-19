from rest_framework import serializers

from .geo import validate_geometry


class AnalyzeSerializer(serializers.Serializer):
    geometry = serializers.JSONField()
    buffer_km = serializers.FloatField(min_value=3, max_value=5, default=5)
    nickname = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")

    def validate_geometry(self, value):
        try:
            validate_geometry(value)
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            raise serializers.ValidationError(str(exc))
        return value
