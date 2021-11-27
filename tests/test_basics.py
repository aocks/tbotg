"""Test some basic things.
"""

import unittest

from tbotg.core import examples


class TestBasics(unittest.TestCase):
    """Testor for some basic items.
    """

    def test_shout(self):
        "Test shoutntimes command."
        result = examples.shoutntimes.callback('hi', 2)
        self.assertEqual(result, 'I will shout it 2 times: HI, HI')
