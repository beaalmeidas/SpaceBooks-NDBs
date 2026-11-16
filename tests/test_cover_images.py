import unittest
from io import BytesIO
from unittest.mock import patch
from PIL import Image
from src.services.covers import validate_image, cover_image

def image_bytes(size):
 stream=BytesIO();Image.new('RGB',size,'navy').save(stream,format='PNG');return stream.getvalue()
class CoverTests(unittest.TestCase):
 def test_error_banner_rejected(self):
  with self.assertRaises(ValueError):validate_image(image_bytes((575,92)))
 def test_thumbnail_rejected_for_large_display(self):
  with self.assertRaises(ValueError):validate_image(image_bytes((128,198)))
 def test_high_resolution_accepted(self):
  self.assertEqual(validate_image(image_bytes((575,912)))[1],575)
 def test_fallback_when_google_fails(self):
  cover_image.clear()
  with patch('src.services.covers.download',side_effect=[image_bytes((575,92)),image_bytes((600,900))]):
   source,quality=cover_image('9780801435300','https://books.google.com/books/content?id=test&zoom=1')
   self.assertTrue(quality);self.assertIn('covers.openlibrary.org',source)
 def test_no_invented_cover_if_all_sources_fail(self):
  cover_image.clear()
  with patch('src.services.covers.download',side_effect=OSError):
   self.assertEqual(cover_image('9780801435300','https://books.google.com/books/content?id=test&zoom=1'),(None,False))
if __name__ == '__main__':
 unittest.main()
