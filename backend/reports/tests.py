from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .models import Claim, Profile, Report


class ReportDatabaseTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='R01234567',
            email='student@farmingdale.edu',
            password='TestPassword123',
        )
        Profile.objects.create(
            user=self.user,
            full_name='Test Student',
            ram_id='R01234567',
        )
        self.client.force_login(self.user)

    def report_data(self, report_type='lost'):
        return {
            'report_type': report_type,
            'full_name': 'Test Student',
            'email': 'student@farmingdale.edu',
            'student_id': '2048',
            'phone': '',
            'category': 'Electronics',
            'item_name': 'Black smartphone',
            'description': 'Black phone in a protective case.',
            'estimated_value': '500.00',
            'incident_date': timezone.localdate().isoformat(),
            'incident_time': None,
            'campus_location': 'Campus Center',
            'location_details': 'Near the entrance',
            'liability_accepted': True,
        }

    def test_report_is_linked_to_authenticated_user(self):
        response = self.client.post(
            '/api/reports/',
            data=self.report_data(),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        report = Report.objects.get(reference=response.json()['reference'])
        self.assertEqual(report.submitted_by, self.user)
        self.assertTrue(report.reference.startswith('LF-'))

    def test_password_is_hashed(self):
        self.assertTrue(self.user.check_password('TestPassword123'))
        self.assertNotEqual(self.user.password, 'TestPassword123')

    def test_claim_is_linked_to_user_and_report(self):
        report = Report.objects.create(
            submitted_by=self.user,
            **{key: value for key, value in self.report_data().items()
               if key != 'incident_time'},
            incident_time=None,
        )
        claim = Claim.objects.create(
            report=report,
            claimant=self.user,
            verification_answers={'detail': 'A distinctive sticker'},
        )

        self.assertEqual(claim.report, report)
        self.assertEqual(claim.claimant, self.user)

    def test_future_report_date_is_rejected(self):
        from datetime import timedelta
        data = self.report_data()
        data['incident_date'] = (timezone.localdate() + timedelta(days=1)).isoformat()

        response = self.client.post(
            '/api/reports/',
            data=data,
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
