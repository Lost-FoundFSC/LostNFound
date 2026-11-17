"""Checks and cleans photos uploaded with a report.

Every photo is re-saved with Pillow, which:
- confirms the file really is an image (not just named .jpg),
- rotates it upright using the phone's orientation tag,
- removes metadata such as GPS location from phone photos.
"""
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGES_PER_REPORT = 5
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_IMAGE_PIXELS = 40_000_000      # about 7000 x 5700

# Pillow format name -> file extension
ALLOWED_FORMATS = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}


class ImageUploadError(ValueError):
    pass


def clean_image(uploaded_file):
    """Return a ContentFile with a clean copy of the photo, or raise ImageUploadError."""
    name = getattr(uploaded_file, 'name', 'image')

    if uploaded_file.size > MAX_IMAGE_BYTES:
        raise ImageUploadError(f'{name}: photo is larger than 5 MB.')

    try:
        with Image.open(uploaded_file) as image:
            image_format = image.format
            if image_format not in ALLOWED_FORMATS:
                raise ImageUploadError(f'{name}: only JPEG, PNG, or WebP photos are allowed.')
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ImageUploadError(f'{name}: photo dimensions are too large.')

            image.load()
            image = ImageOps.exif_transpose(image)
            if image_format == 'JPEG' and image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')

            output = BytesIO()
            image.save(output, format=image_format)  # no exif= argument, so metadata is dropped
    except ImageUploadError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ImageUploadError(f'{name}: file is not a valid image.')

    return ContentFile(output.getvalue(), name=f'upload{ALLOWED_FORMATS[image_format]}')
