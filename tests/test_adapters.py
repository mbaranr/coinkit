import unittest

from adapters.defi.silo import fetch as fetch_silo
from adapters.defi.euler import fetch as fetch_euler
from adapters.defi.aave import fetch as fetch_aave
from adapters.defi.dolomite import fetch as fetch_dolomite


class TestAdapters(unittest.TestCase):
    def test_fetch_silo(self):
        metrics = fetch_silo()
        self.assertIsInstance(metrics, list)
        self.assertEqual(len(metrics), 1)

    def test_fetch_euler(self):
        metrics = fetch_euler()
        self.assertIsInstance(metrics, list)
        self.assertEqual(len(metrics), 3)

    def test_fetch_aave(self):
        metrics = fetch_aave()
        self.assertIsInstance(metrics, list)
        self.assertEqual(len(metrics), 4)

    def test_fetch_dolomite(self):
        metrics = fetch_dolomite()
        self.assertIsInstance(metrics, list)
        self.assertEqual(len(metrics), 3)
