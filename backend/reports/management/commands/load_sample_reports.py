"""Load example lost and found reports for testing and demos.

Usage:
    python manage.py load_sample_reports          # add the examples
    python manage.py load_sample_reports --clear  # remove them, then add them again

The examples live in reports/sample_data/sample_reports.json and their photos
in reports/sample_data/photos/. All people in them are made up, and phone
numbers use the 555-01xx range reserved for fiction.

Each report goes through the same validation and photo cleaning as the real
form, so the examples always match the current rules.

A sample can also say what happened to it afterwards:
    "key":        a name other samples can refer to, like "sony-lost"
    "matchWith":  the key of its lost/found partner (they get linked)
    "status":     a status to set after loading, like "returned"
    "returnedAt": when a returned item was handed back, like "2026-11-14T15:30"
"""
import json
from datetime import datetime, time
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from reports.archive import change_status, find_report, match_reports
from reports.images import ImageUploadError, clean_image
from reports.models import (
    ArchivedReport, FoundReport, FoundReportImage, LostReport, LostReportImage,
    semester_for,
)
from reports.serializers import FoundReportSerializer, LostReportSerializer

SAMPLE_DIR = Path(__file__).resolve().parents[2] / 'sample_data'
SAMPLE_FILE = SAMPLE_DIR / 'sample_reports.json'
PHOTO_DIR = SAMPLE_DIR / 'photos'

SERIALIZERS = {'lost': LostReportSerializer, 'found': FoundReportSerializer}
IMAGE_MODELS = {'lost': LostReportImage, 'found': FoundReportImage}
ALL_MODELS = (LostReport, FoundReport, ArchivedReport)
EXTRA_KEYS = {'photos', 'key', 'matchWith', 'status', 'returnedAt'}


def load_samples():
    with open(SAMPLE_FILE, encoding='utf-8') as file:
        return json.load(file)


def find_existing(sample):
    for model in ALL_MODELS:
        report = model.objects.filter(email__iexact=sample['email'], item_name=sample['itemName']).first()
        if report:
            return report
    return None


def submitted_at(sample):
    """Pretend the report was submitted when the item went missing, if known."""
    if not sample.get('incidentDate'):
        return None
    day = datetime.strptime(sample['incidentDate'], '%Y-%m-%d').date()
    clock = datetime.strptime(sample['incidentTime'], '%H:%M').time() if sample.get('incidentTime') else time(12, 0)
    return timezone.make_aware(datetime.combine(day, clock))


class Command(BaseCommand):
    help = 'Load example lost and found reports (with photos) for testing.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete previously loaded example reports before loading them again.',
        )

    def handle(self, *args, **options):
        samples = load_samples()

        if options['clear']:
            removed = 0
            for sample in samples:
                for model in ALL_MODELS:
                    count, _ = model.objects.filter(
                        email__iexact=sample['email'], item_name=sample['itemName']).delete()
                    removed += count
            self.stdout.write(f'Removed {removed} database rows from earlier example reports.')

        created = skipped = 0
        form_ids = {}  # sample key -> form ID
        for sample in samples:
            existing = find_existing(sample)
            if existing:
                skipped += 1
                form_ids[sample.get('key')] = existing.form_id
                self.stdout.write(f'  skipped  {existing.form_id}  {sample["itemName"]} (already loaded)')
                continue

            report_type = sample['reportType']
            data = {key: value for key, value in sample.items() if key not in EXTRA_KEYS}
            data['liabilityAccepted'] = True
            serializer = SERIALIZERS[report_type](data=data)
            if not serializer.is_valid():
                raise CommandError(f'{sample["itemName"]}: {serializer.errors}')

            photos = []
            for name in sample.get('photos', []):
                path = PHOTO_DIR / name
                if not path.exists():
                    raise CommandError(f'{sample["itemName"]}: photo not found: {path}')
                with open(path, 'rb') as handle:
                    try:
                        photos.append(clean_image(File(handle, name=name)))
                    except ImageUploadError as error:
                        raise CommandError(str(error))

            with transaction.atomic():
                report = serializer.save()
                when = submitted_at(sample)
                if when:
                    report.created_at = when
                    report.save(update_fields=['created_at'])
                for photo in photos:
                    IMAGE_MODELS[report_type].objects.create(report=report, image=photo)

            created += 1
            form_ids[sample.get('key')] = report.form_id
            self.stdout.write(
                f'  created  {report.form_id}  {sample["itemName"]} '
                f'({report_type}, {len(photos)} photo{"" if len(photos) == 1 else "s"})'
            )

        matched = self.link_matches(samples, form_ids)
        returned = self.apply_statuses(samples, form_ids)

        self.stdout.write(self.style.SUCCESS(
            f'Done: {created} example report(s) created, {skipped} already existed, '
            f'{matched} pair(s) matched, {returned} report(s) marked returned.'))

    def link_matches(self, samples, form_ids):
        matched = 0
        for sample in samples:
            partner_key = sample.get('matchWith')
            if not partner_key:
                continue
            if partner_key not in form_ids:
                raise CommandError(f'{sample["itemName"]}: matchWith "{partner_key}" is not a sample key.')
            report = find_report(form_ids[sample['key']])
            partner_id = form_ids[partner_key]
            if report.matched_form_id == partner_id:
                continue  # already linked (by its partner, or an earlier run)
            match_reports(report, partner_id)
            matched += 1
            self.stdout.write(f'  matched  {report.form_id} <-> {partner_id}')
        return matched

    def apply_statuses(self, samples, form_ids):
        returned = 0
        for sample in samples:
            status = sample.get('status')
            if not status:
                continue
            report = find_report(form_ids[sample['key']])
            if report.status != status:
                report = change_status(report, status)
                if status == 'returned':
                    returned += 1 + (1 if report.matched_form_id else 0)
                self.stdout.write(f'  {status:<8} {report.form_id}'
                                  + (f' and {report.matched_form_id}' if report.matched_form_id else ''))
            if sample.get('returnedAt') and isinstance(report, ArchivedReport):
                when = timezone.make_aware(datetime.strptime(sample['returnedAt'], '%Y-%m-%dT%H:%M'))
                report.completed_at = when
                report.archive_semester = semester_for(timezone.localtime(when))
                report.save(update_fields=['completed_at', 'archive_semester'])
        return returned
