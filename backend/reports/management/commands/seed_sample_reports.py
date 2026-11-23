from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from reports.models import (
    FoundReport, LostReport, form_id_exists,
)


class Command(BaseCommand):
    help = 'Add the eight synthetic lost and found reports used for local testing.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Sample reports may only be seeded when DEBUG=True.')

        today = timezone.localdate()
        samples = [
            (LostReport, 'L#312198494', {
                'full_name': 'Sample Test User One',
                'email': 'sample.lost.one@example.com',
                'phone': '516-555-0101',
                'category': 'Electronics',
                'item_name': 'Navy Sony headphones with silver star sticker',
                'description': 'Navy over-ear Sony headphones with a small silver star sticker on the left ear cup and initials MK written under the headband.',
                'incident_date': today,
                'campus_location': 'Greenley Library',
                'location_details': 'Second-floor study area',
                'liability_accepted': True,
            }),
            (FoundReport, 'F#471000254', {
                'category': 'Accessories',
                'item_name': 'Brass dorm key with orange rocket keychain',
                'description': 'Single brass dorm key with a scratched round head and an orange rocket-shaped plastic keychain.',
                'incident_date': today,
                'campus_location': 'Campus Center',
                'location_details': 'Near the east entrance',
                'liability_accepted': True,
            }),
            (LostReport, 'L#142196003', {
                'full_name': 'Sample Test User Two',
                'email': 'sample.lost.two@example.com',
                'phone': '516-555-0102',
                'category': 'Clothing',
                'item_name': 'Charcoal canvas backpack with turquoise dinosaur patch',
                'description': 'Charcoal canvas backpack with a turquoise dinosaur patch on the front pocket and a missing zipper pull on the left side.',
                'incident_date': today,
                'campus_location': 'Whitman Hall',
                'location_details': 'Outside the main lecture room',
                'liability_accepted': True,
            }),
            (FoundReport, 'F#889760940', {
                'category': 'Clothing',
                'item_name': 'Olive carry-on duffel with white ram patch',
                'description': 'Olive carry-on duffel bag with a white ram-shaped patch on the side handle and a red luggage tag.',
                'incident_date': today,
                'campus_location': 'Campus Center',
                'location_details': 'Beside the information desk',
                'liability_accepted': True,
            }),
            (LostReport, 'L#800000001', {
                'full_name': 'Sample Test User Three',
                'email': 'sample.lost.three@example.com',
                'phone': '516-555-0103',
                'category': 'Books',
                'item_name': 'Calculus textbook with red bicycle sticker',
                'description': 'Calculus textbook with a red bicycle sticker on the back cover and pages 42 through 48 highlighted in green.',
                'incident_date': today - timedelta(days=2),
                'campus_location': 'Greenley Library',
                'location_details': 'Near the mathematics reference shelves',
                'liability_accepted': True,
            }),
            (FoundReport, 'F#800000001', {
                'category': 'Books',
                'item_name': 'Calculus textbook with red bicycle sticker',
                'description': 'Calculus textbook with a red bicycle sticker on the back cover and green highlighting on pages 42 through 48.',
                'incident_date': today - timedelta(days=1),
                'campus_location': 'Greenley Library',
                'location_details': 'At the library front desk',
                'liability_accepted': True,
            }),
            (LostReport, 'L#800000002', {
                'full_name': 'Sample Test User Four',
                'email': 'sample.lost.four@example.com',
                'phone': '516-555-0104',
                'category': 'Wallets & IDs',
                'item_name': 'Brown card wallet with tiny compass charm',
                'description': 'Brown leather card wallet with a tiny brass compass charm stitched beside the inside ID window.',
                'incident_date': today - timedelta(days=2),
                'campus_location': 'Campus Center',
                'location_details': 'Second-floor seating area',
                'liability_accepted': True,
            }),
            (FoundReport, 'F#800000002', {
                'category': 'Wallets & IDs',
                'item_name': 'Brown wallet with small compass charm',
                'description': 'Brown leather card wallet with a small brass compass charm next to the clear ID window.',
                'incident_date': today - timedelta(days=1),
                'campus_location': 'Campus Center',
                'location_details': 'Turned in at the information desk',
                'liability_accepted': True,
            }),
        ]

        created = 0
        skipped = 0
        with transaction.atomic():
            for model, form_id, fields in samples:
                if model.objects.filter(form_id=form_id).exists():
                    skipped += 1
                    continue
                if form_id_exists(form_id):
                    raise CommandError(
                        f'{form_id} is already used by a different report; no sample reports were added.'
                    )

                model.objects.create(form_id=form_id, student_id='', **fields)
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Created {created} sample reports; skipped {skipped} that already existed.'
        ))
