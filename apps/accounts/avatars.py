import io
import uuid

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_AVATAR_BYTES = 2 * 1024 * 1024
MAX_AVATAR_PIXELS = 25_000_000
AVATAR_SIZE = 256
ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP'}


class AvatarError(Exception):

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def process_avatar(upload):
    if upload.size > MAX_AVATAR_BYTES:
        raise AvatarError('avatar_too_large')

    try:
        image = Image.open(upload)
        if image.format not in ALLOWED_FORMATS:
            raise AvatarError('avatar_invalid')

        width, height = image.size
        if width * height > MAX_AVATAR_PIXELS:
            raise AvatarError('avatar_dimensions')

        image.load()
        image = ImageOps.exif_transpose(image)
        has_alpha = image.mode in ('RGBA', 'LA') or (
            image.mode == 'P' and 'transparency' in image.info
        )
        image = image.convert('RGBA' if has_alpha else 'RGB')
        image = ImageOps.fit(image, (AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        image.save(buffer, format='WEBP', quality=85)
    except AvatarError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError):
        raise AvatarError('avatar_invalid')

    return ContentFile(buffer.getvalue(), name=f'{uuid.uuid4().hex}.webp')