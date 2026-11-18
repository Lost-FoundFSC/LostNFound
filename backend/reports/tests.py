import re
import shutil
import tempfile
from datetime import timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APITestCase

from .archive import find_report
from .models import (
    ArchivedReport, ArchivedReportImage, FoundReport, FoundReportImage,
    LostReport, LostReportImage, normalize_form_id, semester_for,
)
from .permissions import CAMPUS_SECURITY_GROUP


def payload(**overrides):
    data = {
        'reportType': 'lost',
        'fullName': 'Jane Doe',
        'email': 'doej@farmingdale.edu',
        'studentId': 'R01234567',
        'phone': '516-555-1234',
        'category': 'Electronics',
        'itemName': 'Black AirPods case',
        'description': 'Scratch on lid',
        'estimatedValue': '',
        'incidentDate': timezone.localdate().isoformat(),
        'incidentTime': '',
        'campusLocation': 'Greenley Library',
        'locationDetails': '2nd floor',
        'liabilityAccepted': True,
    }
    data.update(overrides)
    return data


def form_payload(**overrides):
    """payload() as multipart form fields (what a FormData submission sends)."""
    data = payload(**overrides)
    data['liabilityAccepted'] = 'true' if data['liabilityAccepted'] else 'false'
    return data


def make_photo(name='photo.jpg', image_format='JPEG', size=(40, 30), with_gps=False):
    image = Image.new('RGB', size, 'red')
    buffer = BytesIO()
    kwargs = {}
    if with_gps:
        exif = Image.Exif()
        exif[0x8825] = {1: 'N', 2: (40.0, 45.0, 0.0)}  # GPSInfo
        kwargs['exif'] = exif
    image.save(buffer, format=image_format, **kwargs)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=f'image/{image_format.lower()}')


class TempMediaMixin:
    """Keeps uploaded test photos out of the real media folder."""

    def setUp(self):
        super().setUp()
        cache.clear()  # reset rate limits between tests
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()


class UsersMixin:
    def make_users(self):
        User = get_user_model()
        self.security = User.objects.create_user('officer', password='x')
        self.security.groups.add(Group.objects.get(name=CAMPUS_SECURITY_GROUP))
        self.student = User.objects.create_user(
            'student', password='x', email='doej@farmingdale.edu')
        self.other_student = User.objects.create_user(
            'other', password='x', email='someoneelse@farmingdale.edu')

    def submit(self, images=None, **overrides):
        if images is None:
            return self.client.post(reverse('report-submit'), payload(**overrides), format='json')
        data = form_payload(**overrides)
        data['images'] = images
        return self.client.post(reverse('report-submit'), data, format='multipart')

    def set_status(self, form_id, new_status):
        self.client.force_authenticate(self.security)
        response = self.client.patch(
            reverse('report-detail', args=[form_id]), {'status': new_status}, format='json')
        self.client.force_authenticate(None)
        return response


# ---------------------------------------------------------------- form IDs

class FormIdTests(TestCase):

    def test_normalize(self):
        self.assertEqual(normalize_form_id('l384834901'), 'L#384834901')
        self.assertEqual(normalize_form_id(' F#238832420 '), 'F#238832420')
        self.assertIsNone(normalize_form_id('X#384834901'))
        self.assertIsNone(normalize_form_id('L#123'))
        self.assertIsNone(normalize_form_id(''))

    def test_semester(self):
        self.assertEqual(semester_for(timezone.datetime(2026, 3, 1)), 'Spring 2026')
        self.assertEqual(semester_for(timezone.datetime(2026, 7, 1)), 'Summer 2026')
        self.assertEqual(semester_for(timezone.datetime(2026, 11, 17)), 'Fall 2026')


# ---------------------------------------------------------------- submitting

class SubmitReportTests(TempMediaMixin, APITestCase):
    url = reverse('report-submit')

    def test_lost_report_gets_L_form_id(self):
        response = self.client.post(self.url, payload(), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertRegex(response.data['formId'], r'^L#\d{9}$')
        self.assertEqual(LostReport.objects.get().form_id, response.data['formId'])
        self.assertEqual(FoundReport.objects.count(), 0)

    def test_found_report_gets_F_form_id(self):
        response = self.client.post(self.url, payload(reportType='found'), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertRegex(response.data['formId'], r'^F#\d{9}$')
        self.assertEqual(LostReport.objects.count(), 0)

    def test_form_ids_are_unique(self):
        ids = {self.client.post(self.url, payload(), format='json').data['formId'] for _ in range(20)}
        self.assertEqual(len(ids), 20)

    def test_new_report_status_is_reported(self):
        response = self.client.post(self.url, payload(), format='json')
        self.assertEqual(response.data['status'], 'reported')

    def test_full_ram_id_stored_uppercase(self):
        self.client.post(self.url, payload(studentId=' r01234567 '), format='json')
        self.assertEqual(LostReport.objects.get().student_id, 'R01234567')

    def test_invalid_ram_id_rejected(self):
        response = self.client.post(self.url, payload(studentId='12345'), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('studentId', response.data)

    def test_phone_required(self):
        for phone in ('', '   '):
            response = self.client.post(self.url, payload(phone=phone), format='json')
            self.assertEqual(response.status_code, 400, phone)
            self.assertIn('phone', response.data)

    def test_phone_must_be_10_digits(self):
        response = self.client.post(self.url, payload(phone='555-1234'), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('10-digit', str(response.data['phone']))

    def test_phone_stored_in_one_format(self):
        for raw in ('5165512685', '(516) 551-2685', '+1 516 551 2685'):
            response = self.client.post(self.url, payload(phone=raw), format='json')
            self.assertEqual(response.status_code, 201, raw)
            report = LostReport.objects.get(form_id=response.data['formId'])
            self.assertEqual(report.phone, '(516) 551-2685')

    def test_name_and_email_required(self):
        response = self.client.post(self.url, payload(fullName='', email=''), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('fullName', response.data)
        self.assertIn('email', response.data)

    def test_ram_id_optional(self):
        response = self.client.post(self.url, payload(studentId=''), format='json')
        self.assertEqual(response.status_code, 201)

    def test_empty_optional_fields_accepted(self):
        response = self.client.post(self.url, payload(), format='json')
        report = LostReport.objects.get(form_id=response.data['formId'])
        self.assertIsNone(report.estimated_value)
        self.assertIsNone(report.incident_time)

    def test_invalid_report_type_rejected(self):
        response = self.client.post(self.url, payload(reportType='stolen'), format='json')
        self.assertEqual(response.status_code, 400)

    def test_future_date_rejected(self):
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        response = self.client.post(self.url, payload(incidentDate=tomorrow), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('incidentDate', response.data)

    def test_date_and_location_optional(self):
        response = self.client.post(
            self.url, payload(incidentDate='', campusLocation=''), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        report = LostReport.objects.get(form_id=response.data['formId'])
        self.assertIsNone(report.incident_date)
        self.assertEqual(report.campus_location, '')

    def test_date_and_location_can_be_left_out(self):
        data = payload()
        del data['incidentDate'], data['campusLocation']
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def test_liability_must_be_accepted(self):
        response = self.client.post(self.url, payload(liabilityAccepted=False), format='json')
        self.assertEqual(response.status_code, 400)

    def test_unknown_category_rejected(self):
        response = self.client.post(self.url, payload(category='Pets'), format='json')
        self.assertEqual(response.status_code, 400)


class MapPinTests(TempMediaMixin, UsersMixin, APITestCase):
    """Map fields reserved for the upcoming campus map feature."""

    def setUp(self):
        super().setUp()
        self.make_users()

    def test_map_pin_optional(self):
        response = self.submit()
        self.assertEqual(response.status_code, 201)
        report = LostReport.objects.get()
        self.assertIsNone(report.map_latitude)
        self.assertIsNone(report.map_longitude)

    def test_empty_strings_from_form_treated_as_no_pin(self):
        response = self.submit(images=[], mapLatitude='', mapLongitude='')
        self.assertEqual(response.status_code, 201, response.data)

    def test_map_pin_saved_and_shown_to_security(self):
        form_id = self.submit(mapLatitude='40.752114', mapLongitude='-73.427983').data['formId']
        self.client.force_authenticate(self.security)
        data = self.client.get(reverse('report-detail', args=[form_id])).data
        self.assertEqual(str(data['mapLatitude']), '40.752114')
        self.assertEqual(str(data['mapLongitude']), '-73.427983')

    def test_map_pin_kept_in_archive(self):
        form_id = self.submit(mapLatitude='40.752114', mapLongitude='-73.427983').data['formId']
        self.set_status(form_id, 'returned')
        self.assertEqual(str(ArchivedReport.objects.get().map_latitude), '40.752114')

    def test_needs_both_coordinates(self):
        response = self.submit(mapLatitude='40.752114')
        self.assertEqual(response.status_code, 400)
        self.assertIn('mapLatitude', response.data)

    def test_out_of_range_rejected(self):
        response = self.submit(mapLatitude='95', mapLongitude='-73.4')
        self.assertEqual(response.status_code, 400)

    def test_map_pin_not_in_public_progress(self):
        form_id = self.submit(mapLatitude='40.752114', mapLongitude='-73.427983').data['formId']
        data = self.client.get(reverse('report-progress', args=[form_id])).data
        self.assertNotIn('mapLatitude', data)


# ------------------------------------------------------------------ photos

class ImageUploadTests(TempMediaMixin, UsersMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.make_users()

    def test_found_report_with_photos(self):
        response = self.submit([make_photo('a.jpg'), make_photo('b.png', 'PNG')], reportType='found')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['imageCount'], 2)
        self.assertEqual(FoundReportImage.objects.count(), 2)

    def test_lost_report_without_photo(self):
        response = self.client.post(reverse('report-submit'), form_payload(), format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['imageCount'], 0)

    def test_original_file_name_not_kept(self):
        self.submit([make_photo('Matthew_Quin_RAM_R12345678.jpg')])
        stored = LostReportImage.objects.get().image.name
        self.assertNotIn('Matthew', stored)
        self.assertTrue(stored.startswith('report_images/lost/'))

    def test_gps_metadata_removed(self):
        self.submit([make_photo(with_gps=True)])
        with Image.open(LostReportImage.objects.get().image.path) as saved:
            self.assertNotIn(0x8825, saved.getexif())

    def test_too_many_photos_rejected(self):
        response = self.submit([make_photo(f'{i}.jpg') for i in range(6)])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(LostReport.objects.count(), 0)

    def test_fake_image_rejected_and_report_not_saved(self):
        fake = SimpleUploadedFile('virus.jpg', b'not really an image', content_type='image/jpeg')
        response = self.submit([make_photo(), fake])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(LostReport.objects.count(), 0)
        self.assertEqual(LostReportImage.objects.count(), 0)

    def test_unsupported_format_rejected(self):
        self.assertEqual(self.submit([make_photo('a.gif', 'GIF')]).status_code, 400)

    def test_oversized_photo_rejected(self):
        big = SimpleUploadedFile('big.jpg', b'0' * (5 * 1024 * 1024 + 1), content_type='image/jpeg')
        self.assertEqual(self.submit([big]).status_code, 400)

    def test_security_can_open_photo(self):
        form_id = self.submit([make_photo()], reportType='found').data['formId']
        self.client.force_authenticate(self.security)
        detail = self.client.get(reverse('report-detail', args=[form_id])).data
        self.assertEqual(len(detail['images']), 1)
        photo = self.client.get(detail['images'][0]['url'])
        self.assertEqual(photo.status_code, 200)
        self.assertEqual(b''.join(photo.streaming_content)[:2], b'\xff\xd8')  # JPEG header

    def test_photos_hidden_from_students_and_public(self):
        form_id = self.submit([make_photo()], reportType='found').data['formId']
        url = reverse('report-image', args=[form_id, FoundReportImage.objects.get().id])
        self.assertIn(self.client.get(url).status_code, (401, 403))
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_photo_must_belong_to_report(self):
        first = self.submit([make_photo()], reportType='found').data['formId']
        self.submit([make_photo()], reportType='found')
        other_image = FoundReportImage.objects.exclude(report__form_id=first).get().id
        self.client.force_authenticate(self.security)
        url = reverse('report-image', args=[first, other_image])
        self.assertEqual(self.client.get(url).status_code, 404)


# ------------------------------------------------------- progress (public)

class ProgressTests(TempMediaMixin, UsersMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.make_users()
        self.form_id = self.submit().data['formId']

    def progress(self, form_id):
        return self.client.get(reverse('report-progress', args=[form_id]))

    def test_progress_by_form_id(self):
        response = self.progress(self.form_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['formId'], self.form_id)
        self.assertEqual(response.data['status'], 'reported')
        self.assertEqual(response.data['statusLabel'], 'Reported')
        self.assertTrue(response.data['isActive'])

    def test_url_without_hash_and_lowercase_work(self):
        digits = self.form_id[2:]
        for value in (f'L{digits}', f'l{digits}', f'L%23{digits}'):
            response = self.client.get(f'/api/reports/progress/{value}/')
            self.assertEqual(response.status_code, 200, value)

    def test_progress_hides_personal_details(self):
        data = self.progress(self.form_id).data
        for hidden in ('fullName', 'email', 'studentId', 'phone', 'description', 'images'):
            self.assertNotIn(hidden, data)

    def test_progress_follows_status_changes(self):
        self.set_status(self.form_id, 'possible_match')
        self.assertEqual(self.progress(self.form_id).data['statusLabel'], 'Possible match')

    def test_progress_still_works_after_archive(self):
        self.set_status(self.form_id, 'returned')
        data = self.progress(self.form_id).data
        self.assertEqual(data['status'], 'returned')
        self.assertFalse(data['isActive'])
        self.assertIsNotNone(data['archiveSemester'])

    def test_progress_without_date_or_location(self):
        form_id = self.submit(incidentDate='', campusLocation='').data['formId']
        data = self.progress(form_id).data
        self.assertIsNone(data['incidentDate'])
        self.assertEqual(data['campusLocation'], '')

    def test_unknown_form_id_404(self):
        self.assertEqual(self.progress('L#000000001').status_code, 404)

    @override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'report-progress': '3/minute'}})
    def test_rate_limited(self):
        from rest_framework.settings import api_settings
        from rest_framework.throttling import ScopedRateThrottle
        original = ScopedRateThrottle.THROTTLE_RATES
        ScopedRateThrottle.THROTTLE_RATES = api_settings.DEFAULT_THROTTLE_RATES
        try:
            codes = [self.progress('L#000000001').status_code for _ in range(4)]
        finally:
            ScopedRateThrottle.THROTTLE_RATES = original
        self.assertEqual(codes[-1], 429)


# ------------------------------------------------------- student dashboard

class MyReportsTests(TempMediaMixin, UsersMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.make_users()
        self.lost_id = self.submit().data['formId']
        self.found_id = self.submit(reportType='found').data['formId']
        self.returned_id = self.submit(itemName='Umbrella').data['formId']
        self.set_status(self.returned_id, 'returned')
        self.submit(email='someoneelse@farmingdale.edu')
        self.url = reverse('my-reports')

    def test_requires_login(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))

    def test_lists_own_open_and_archived_reports(self):
        self.client.force_authenticate(self.student)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        ids = {report['formId'] for report in response.data}
        self.assertEqual(ids, {self.lost_id, self.found_id, self.returned_id})
        archived = next(r for r in response.data if r['formId'] == self.returned_id)
        self.assertFalse(archived['isActive'])

    def test_email_match_ignores_case(self):
        self.student.email = 'DoeJ@Farmingdale.edu'
        self.student.save()
        self.client.force_authenticate(self.student)
        self.assertEqual(len(self.client.get(self.url).data), 3)

    def test_does_not_show_other_students_reports(self):
        self.client.force_authenticate(self.other_student)
        self.assertEqual(len(self.client.get(self.url).data), 1)


# ------------------------------------------------- Campus Security + archive

class SecurityAndArchiveTests(TempMediaMixin, UsersMixin, APITestCase):

    def setUp(self):
        super().setUp()
        self.make_users()
        self.form_id = self.submit([make_photo()]).data['formId']
        self.detail_url = reverse('report-detail', args=[self.form_id])

    def test_anonymous_and_students_blocked(self):
        for url in (self.detail_url, reverse('lost-report-list'), reverse('archived-report-list')):
            self.assertIn(self.client.get(url).status_code, (401, 403))
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(self.detail_url).status_code, 403)
        response = self.client.patch(self.detail_url, {'status': 'returned'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_security_sees_full_report_by_form_id(self):
        self.client.force_authenticate(self.security)
        data = self.client.get(self.detail_url).data
        self.assertEqual(data['formId'], self.form_id)
        self.assertEqual(data['reportType'], 'lost')
        self.assertEqual(data['studentId'], 'R01234567')
        self.assertEqual(data['email'], 'doej@farmingdale.edu')
        self.assertNotIn('id', data)

    def test_progress_stages_stay_open(self):
        for stage in ('possible_match', 'under_verification', 'ready_for_pickup'):
            response = self.set_status(self.form_id, stage)
            self.assertEqual(response.data['status'], stage)
            self.assertTrue(response.data['isActive'])
        self.assertEqual(LostReport.objects.count(), 1)
        self.assertEqual(ArchivedReport.objects.count(), 0)

    def test_returned_moves_to_archive_with_photos(self):
        response = self.set_status(self.form_id, 'returned')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['formId'], self.form_id)  # same ID kept
        self.assertEqual(response.data['status'], 'returned')
        self.assertFalse(response.data['isActive'])
        self.assertIsNotNone(response.data['completedAt'])
        self.assertTrue(re.match(r'^(Spring|Summer|Fall) \d{4}$', response.data['archiveSemester']))

        self.assertEqual(LostReport.objects.count(), 0)
        self.assertEqual(LostReportImage.objects.count(), 0)
        archived = ArchivedReport.objects.get()
        self.assertEqual(archived.report_type, 'lost')
        self.assertEqual(archived.student_id, 'R01234567')
        self.assertEqual(ArchivedReportImage.objects.count(), 1)

        # Photo file is still on disk and viewable.
        self.client.force_authenticate(self.security)
        photo = self.client.get(response.data['images'][0]['url'])
        self.assertEqual(photo.status_code, 200)

    def test_report_without_date_or_location_archives(self):
        form_id = self.submit(incidentDate='', campusLocation='').data['formId']
        response = self.set_status(form_id, 'returned')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['incidentDate'])

    def test_closed_and_cancelled_also_archive(self):
        other = self.submit(reportType='found').data['formId']
        self.set_status(self.form_id, 'closed')
        self.set_status(other, 'cancelled')
        self.assertEqual(
            sorted(ArchivedReport.objects.values_list('status', flat=True)),
            ['cancelled', 'closed'])

    def test_archive_keeps_original_submission_time(self):
        created = LostReport.objects.get().created_at
        self.set_status(self.form_id, 'returned')
        self.assertEqual(ArchivedReport.objects.get().created_at, created)

    def test_reopen_moves_back_out_of_archive(self):
        self.set_status(self.form_id, 'returned')
        response = self.set_status(self.form_id, 'under_verification')
        self.assertEqual(response.data['status'], 'under_verification')
        self.assertEqual(ArchivedReport.objects.count(), 0)
        report = LostReport.objects.get()
        self.assertEqual(report.form_id, self.form_id)
        self.assertEqual(report.images.count(), 1)

    def test_open_lists_exclude_archived(self):
        self.submit(itemName='Umbrella')
        self.set_status(self.form_id, 'returned')
        self.client.force_authenticate(self.security)
        lost = self.client.get(reverse('lost-report-list')).data
        self.assertEqual([r['itemName'] for r in lost], ['Umbrella'])
        archive = self.client.get(reverse('archived-report-list'), {'type': 'lost'}).data
        self.assertEqual([r['formId'] for r in archive], [self.form_id])

    def test_list_filter_by_status(self):
        self.submit(itemName='Umbrella')
        self.set_status(self.form_id, 'possible_match')
        self.client.force_authenticate(self.security)
        url = reverse('lost-report-list')
        self.assertEqual(len(self.client.get(url, {'status': 'possible_match'}).data), 1)
        self.assertEqual(len(self.client.get(url, {'status': 'reported'}).data), 1)
        self.assertEqual(self.client.get(url, {'status': 'returned'}).status_code, 400)

    def test_patch_cannot_change_other_fields(self):
        self.client.force_authenticate(self.security)
        self.client.patch(self.detail_url, {'status': 'possible_match', 'itemName': 'Hacked'}, format='json')
        self.assertEqual(LostReport.objects.get().item_name, 'Black AirPods case')

    def test_invalid_status_rejected(self):
        self.assertEqual(self.set_status(self.form_id, 'lost-forever').status_code, 400)

    def test_find_report_checks_both_tables(self):
        self.assertIsInstance(find_report(self.form_id), LostReport)
        self.set_status(self.form_id, 'returned')
        self.assertIsInstance(find_report(self.form_id), ArchivedReport)


# ------------------------------------------------------ lost/found matches

class MatchTests(TempMediaMixin, UsersMixin, APITestCase):
    """A lost report and a found report for the same item point at each other."""

    def setUp(self):
        super().setUp()
        self.make_users()
        self.lost_id = self.submit([make_photo()], itemName='Sony headphones').data['formId']
        self.found_id = self.submit([make_photo()], reportType='found', itemName='Sony headphones').data['formId']
        self.client.force_authenticate(self.security)

    def patch(self, form_id, **data):
        return self.client.patch(reverse('report-detail', args=[form_id]), data, format='json')

    def detail(self, form_id):
        return self.client.get(reverse('report-detail', args=[form_id])).data

    def test_match_links_both_reports(self):
        response = self.patch(self.lost_id, matchedFormId=self.found_id)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['matchedFormId'], self.found_id)
        self.assertEqual(self.detail(self.found_id)['matchedFormId'], self.lost_id)
        # Both stay open until the item is returned.
        self.assertEqual(LostReport.objects.count(), 1)
        self.assertEqual(FoundReport.objects.count(), 1)

    def test_match_accepts_id_without_hash_or_lowercase(self):
        response = self.patch(self.found_id, matchedFormId=self.lost_id.replace('#', '').lower())
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['matchedFormId'], self.lost_id)

    def test_returned_archives_both_with_each_others_id(self):
        self.patch(self.lost_id, matchedFormId=self.found_id)
        response = self.patch(self.found_id, status='returned')
        self.assertEqual(response.status_code, 200)

        self.assertEqual(LostReport.objects.count(), 0)
        self.assertEqual(FoundReport.objects.count(), 0)
        lost = ArchivedReport.objects.get(form_id=self.lost_id)
        found = ArchivedReport.objects.get(form_id=self.found_id)
        self.assertEqual((lost.status, lost.matched_form_id), ('returned', self.found_id))
        self.assertEqual((found.status, found.matched_form_id), ('returned', self.lost_id))
        self.assertEqual(lost.images.count(), 1)
        self.assertEqual(found.images.count(), 1)

    def test_match_and_return_in_one_request(self):
        response = self.patch(self.lost_id, matchedFormId=self.found_id, status='returned')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['status'], 'returned')
        self.assertEqual(response.data['matchedFormId'], self.found_id)
        self.assertEqual(ArchivedReport.objects.count(), 2)

    def test_other_stages_only_change_one_report(self):
        self.patch(self.lost_id, matchedFormId=self.found_id)
        self.patch(self.lost_id, status='ready_for_pickup')
        self.assertEqual(LostReport.objects.get().status, 'ready_for_pickup')
        self.assertEqual(FoundReport.objects.get().status, 'reported')

    def test_closing_one_does_not_close_the_other(self):
        self.patch(self.lost_id, matchedFormId=self.found_id)
        self.patch(self.lost_id, status='closed')
        self.assertEqual(ArchivedReport.objects.get().form_id, self.lost_id)
        self.assertEqual(FoundReport.objects.get().matched_form_id, self.lost_id)

    def test_reopening_a_returned_pair_reopens_both(self):
        self.patch(self.lost_id, matchedFormId=self.found_id, status='returned')
        response = self.patch(self.lost_id, status='under_verification')
        self.assertEqual(response.data['status'], 'under_verification')
        self.assertEqual(ArchivedReport.objects.count(), 0)
        self.assertEqual(LostReport.objects.get().matched_form_id, self.found_id)
        self.assertEqual(FoundReport.objects.get().status, 'under_verification')

    def test_remove_match(self):
        self.patch(self.lost_id, matchedFormId=self.found_id)
        response = self.patch(self.found_id, matchedFormId='')
        self.assertEqual(response.data['matchedFormId'], '')
        self.assertEqual(LostReport.objects.get().matched_form_id, '')

    def test_cannot_match_same_type(self):
        other_lost = self.submit(itemName='Umbrella').data['formId']
        self.client.force_authenticate(self.security)
        response = self.patch(self.lost_id, matchedFormId=other_lost)
        self.assertEqual(response.status_code, 400)
        self.assertIn('found report', response.data['matchedFormId'][0])

    def test_cannot_match_unknown_or_badly_typed_id(self):
        self.assertIn('no report', self.patch(self.lost_id, matchedFormId='F#000000001').data['matchedFormId'][0])
        self.assertIn('form ID like', self.patch(self.lost_id, matchedFormId='banana').data['matchedFormId'][0])

    def test_cannot_match_to_itself(self):
        response = self.patch(self.lost_id, matchedFormId=self.lost_id)
        self.assertEqual(response.status_code, 400)

    def test_cannot_steal_a_report_that_is_already_matched(self):
        self.patch(self.lost_id, matchedFormId=self.found_id)
        second_lost = self.submit(itemName='Headphones').data['formId']
        self.client.force_authenticate(self.security)
        response = self.patch(second_lost, matchedFormId=self.found_id)
        self.assertEqual(response.status_code, 400)
        self.assertIn('already matched', response.data['matchedFormId'][0])
        self.assertEqual(FoundReport.objects.get().matched_form_id, self.lost_id)

    def test_failed_match_does_not_change_status(self):
        response = self.patch(self.lost_id, matchedFormId='F#000000001', status='returned')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(LostReport.objects.get().status, 'reported')

    def test_patch_needs_status_or_match(self):
        self.assertEqual(self.patch(self.lost_id).status_code, 400)

    def test_students_cannot_match(self):
        self.client.force_authenticate(self.student)
        self.assertEqual(self.patch(self.lost_id, matchedFormId=self.found_id).status_code, 403)

    def test_match_not_shown_in_public_progress(self):
        self.patch(self.lost_id, matchedFormId=self.found_id)
        self.client.force_authenticate(None)
        data = self.client.get(reverse('report-progress', args=[self.lost_id])).data
        self.assertNotIn('matchedFormId', data)


class MatchAdminTests(TempMediaMixin, UsersMixin, TestCase):
    """Matching from the Django admin."""

    def setUp(self):
        super().setUp()
        from django.test import Client
        self.api = APITestCase.client_class()
        self.lost_id = self.api.post(reverse('report-submit'), payload(), format='json').data['formId']
        self.found_id = self.api.post(reverse('report-submit'), payload(reportType='found'), format='json').data['formId']
        admin_user = get_user_model().objects.create_superuser('admin', 'a@a.com', 'x')
        self.client = Client()
        self.client.force_login(admin_user)

    def change_url(self, model, form_id):
        name = model._meta.model_name
        return reverse(f'admin:reports_{name}_change', args=[model.objects.get(form_id=form_id).pk])

    def form_data(self, report, **overrides):
        data = {
            'matched_form_id': report.matched_form_id, 'full_name': report.full_name, 'email': report.email,
            'student_id': report.student_id, 'phone': report.phone, 'category': report.category,
            'item_name': report.item_name, 'description': report.description, 'estimated_value': '',
            'incident_date': report.incident_date or '', 'incident_time': '', 'campus_location': report.campus_location,
            'location_details': report.location_details, 'liability_accepted': 'on',
            'map_latitude': '', 'map_longitude': '',
            'images-TOTAL_FORMS': '0', 'images-INITIAL_FORMS': '0',
            'images-MIN_NUM_FORMS': '0', 'images-MAX_NUM_FORMS': '1000',
        }
        data.update(overrides)
        return data

    def test_typing_a_match_in_the_admin_links_both(self):
        lost = LostReport.objects.get()
        response = self.client.post(self.change_url(LostReport, self.lost_id),
                                    self.form_data(lost, matched_form_id=self.found_id.replace('#', '')))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(LostReport.objects.get().matched_form_id, self.found_id)
        self.assertEqual(FoundReport.objects.get().matched_form_id, self.lost_id)

    def test_invalid_match_shows_an_error(self):
        lost = LostReport.objects.get()
        response = self.client.post(self.change_url(LostReport, self.lost_id),
                                    self.form_data(lost, matched_form_id='F#000000001'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'There is no report with form ID F#000000001.')
        self.assertEqual(FoundReport.objects.get().matched_form_id, '')

    def test_returned_action_archives_the_pair(self):
        from .archive import match_reports
        match_reports(LostReport.objects.get(), self.found_id)
        response = self.client.post(reverse('admin:reports_lostreport_changelist'), {
            'action': 'set_returned', '_selected_action': [LostReport.objects.get().pk]}, follow=True)
        self.assertContains(response, f'Matched report(s) updated too: {self.found_id}')
        self.assertEqual(ArchivedReport.objects.count(), 2)
        self.assertEqual(ArchivedReport.objects.get(form_id=self.found_id).matched_form_id, self.lost_id)
