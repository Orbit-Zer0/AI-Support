import io
import os
import re
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APITestCase

from .avatars import MAX_AVATAR_BYTES
from .models import Country, Language, UserProfile

User = get_user_model()
PASSWORD = 'Str0ng-pass-111'
URL_PATTERN = re.compile(r'^/media/avatars/[0-9a-f]{32}\.webp$')


def make_user(username='alice'):
    country, _ = Country.objects.get_or_create(code='KG', defaults={'name': 'Kyrgyzstan'})
    lang, _ = Language.objects.get_or_create(code='en', defaults={'name': 'English'})
    user = User.objects.create_user(username, password=PASSWORD)
    UserProfile.objects.create(user=user, country=country, language=lang)
    return user


def image_bytes(fmt='PNG', size=(300, 200), mode='RGB', color=(200, 30, 30), **save_kwargs):
    buffer = io.BytesIO()
    Image.new(mode, size, color).save(buffer, format=fmt, **save_kwargs)
    return buffer.getvalue()


def upload(content, name='photo.png', content_type='image/png'):
    return SimpleUploadedFile(name, content, content_type=content_type)


class AvatarTests(APITestCase):
    def setUp(self):
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        override = override_settings(MEDIA_ROOT=media.name)
        override.enable()
        self.addCleanup(override.disable)

        self.user = make_user()
        self.client.force_authenticate(self.user)
        self.url = reverse('account-avatar')

    def post_avatar(self, file):
        return self.client.post(self.url, {'avatar': file}, format='multipart')

    def stored_path(self):
        self.user.profile.refresh_from_db()
        return self.user.profile.avatar.path

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.post_avatar(upload(image_bytes())).status_code, 401)

    def test_image_is_cropped_resized_and_converted(self):
        response = self.post_avatar(upload(image_bytes(size=(300, 200))))
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.data['avatar_url'], URL_PATTERN)

        with Image.open(self.stored_path()) as stored:
            self.assertEqual(stored.format, 'WEBP')
            self.assertEqual(stored.size, (256, 256))

    def test_metadata_is_stripped(self):
        exif = Image.Exif()
        exif[0x010F] = 'TestCamera'
        original = image_bytes('JPEG', exif=exif.tobytes())
        self.assertGreater(len(Image.open(io.BytesIO(original)).getexif()), 0)

        response = self.post_avatar(upload(original, 'photo.jpg', 'image/jpeg'))
        self.assertEqual(response.status_code, 200)
        with Image.open(self.stored_path()) as stored:
            self.assertEqual(len(stored.getexif()), 0)

    def test_transparent_png_is_accepted(self):
        content = image_bytes(size=(100, 100), mode='RGBA', color=(0, 0, 0, 0))
        self.assertEqual(self.post_avatar(upload(content)).status_code, 200)

    def test_webp_is_accepted(self):
        content = image_bytes('WEBP')
        self.assertEqual(self.post_avatar(upload(content, 'p.webp', 'image/webp')).status_code, 200)

    def test_files_that_are_not_images_are_rejected(self):
        bad_files = [
            upload(b'just some text'),
            upload(b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
                    'a.svg', 'image/svg+xml'),
            upload(b'\x89PNG\r\n\x1a\n broken', 'broken.png'),
        ]
        for file in bad_files:
            with self.subTest(name=file.name):
                response = self.post_avatar(file)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data['code'], 'avatar_invalid')
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.avatar)

    def test_gif_is_rejected(self):
        content = image_bytes('GIF', size=(50, 50), mode='P', color=0)
        response = self.post_avatar(upload(content, 'a.gif', 'image/gif'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'avatar_invalid')

    def test_file_over_the_limit_is_rejected(self):
        response = self.post_avatar(upload(b'0' * (MAX_AVATAR_BYTES + 1)))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'avatar_too_large')

    def test_far_oversized_request_is_refused_before_reading_it(self):
        response = self.post_avatar(upload(b'0' * (MAX_AVATAR_BYTES + 200_000)))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.data['code'], 'avatar_too_large')

    def test_huge_dimensions_are_rejected(self):
        content = image_bytes(size=(6000, 6000), mode='L', color=0)
        self.assertLess(len(content), MAX_AVATAR_BYTES)
        response = self.post_avatar(upload(content))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'avatar_dimensions')

    def test_missing_file_is_rejected(self):
        response = self.client.post(self.url, {}, format='multipart')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'avatar_required')

    def test_file_name_is_random_and_not_taken_from_the_upload(self):
        response = self.post_avatar(upload(image_bytes(), '../../evil.png'))
        self.assertRegex(response.data['avatar_url'], URL_PATTERN)
        self.assertNotIn('evil', response.data['avatar_url'])
        self.assertNotIn('alice', response.data['avatar_url'])

    def test_replacing_the_avatar_deletes_the_old_file(self):
        self.post_avatar(upload(image_bytes()))
        first_path = self.stored_path()
        self.assertTrue(os.path.exists(first_path))

        self.post_avatar(upload(image_bytes(color=(10, 200, 10))))
        second_path = self.stored_path()
        self.assertNotEqual(first_path, second_path)
        self.assertFalse(os.path.exists(first_path))
        self.assertTrue(os.path.exists(second_path))

    def test_delete_endpoint_removes_file_and_url(self):
        self.post_avatar(upload(image_bytes()))
        path = self.stored_path()

        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(os.path.exists(path))
        self.assertIsNone(self.client.get(reverse('account')).data['avatar_url'])

    def test_account_endpoint_exposes_the_url(self):
        self.assertIsNone(self.client.get(reverse('account')).data['avatar_url'])
        self.post_avatar(upload(image_bytes()))
        self.assertRegex(self.client.get(reverse('account')).data['avatar_url'], URL_PATTERN)

    def test_deleting_the_account_removes_the_file(self):
        self.post_avatar(upload(image_bytes()))
        path = self.stored_path()

        response = self.client.post(
            reverse('account-delete'), {'password': PASSWORD}, format='json'
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(os.path.exists(path))