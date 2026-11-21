from rest_framework import serializers

from .models import Claim, Profile, Report


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Profile
        fields = ('username', 'email', 'role', 'full_name', 'ram_id', 'student_id', 'phone')


class ReportSerializer(serializers.ModelSerializer):
    submitted_by = serializers.PrimaryKeyRelatedField(read_only=True)
    reference = serializers.CharField(read_only=True)

    class Meta:
        model = Report
        fields = '__all__'
        read_only_fields = ('reference', 'submitted_by', 'status', 'created_at', 'updated_at')

    def validate_incident_date(self, value):
        from django.utils import timezone
        if value > timezone.localdate():
            raise serializers.ValidationError('Incident date cannot be in the future.')
        return value

    def validate_liability_accepted(self, value):
        if not value:
            raise serializers.ValidationError('The liability notice must be accepted.')
        return value


class ClaimSerializer(serializers.ModelSerializer):
    claimant = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Claim
        fields = '__all__'
        read_only_fields = (
            'claimant', 'status', 'reviewed_by', 'reviewed_at',
            'staff_notes', 'created_at', 'updated_at',
        )
