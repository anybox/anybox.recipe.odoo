"""Provide devtools to openerp."""

requirements = ('anybox.testing.datetime',
                'unittest2',
                )

def load(for_tests=False):
    if for_tests:
        import anybox.testing.datetime
