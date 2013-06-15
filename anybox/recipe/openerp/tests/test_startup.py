from unittest import TestCase
from ..startup import already_imported, clear_import_registry


class TestImportRegistry(TestCase):

    def tearDown(self):
        clear_import_registry()

    def test_clear(self):
        self.assertFalse(already_imported('myaddon'))
        self.assertTrue(already_imported('myaddon'))
        clear_import_registry()
        self.assertFalse(already_imported('myaddon'))

    def test_already_imported(self):
        self.assertFalse(already_imported('myaddon'))
        self.assertTrue(already_imported('myaddon'))
        self.assertTrue(already_imported('openerp.addons.myaddon'))
