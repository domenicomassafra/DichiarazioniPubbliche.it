import unittest
from dataclasses import replace

from dichiarazioni_pubbliche.bounded_private_pilot_manifest_v1 import *

class TestDP235(unittest.TestCase):
    def sample(self, n="a"):
        return PrivatePilotSample(n,"content-"+n,"source","it","written","rights-ref","APPROVED_EXTERNAL_REQUIRED")
    def test_freeze_is_sorted_and_private(self):
        m=freeze_private_pilot_manifest([self.sample("b"),self.sample("a")])
        validate_private_pilot_manifest(m)
        self.assertFalse(m.dispatch_authorized)
    def test_tamper_is_rejected(self):
        m=freeze_private_pilot_manifest([self.sample()])
        with self.assertRaises(ValueError): validate_private_pilot_manifest(replace(m, manifest_sha256="bad"))
    def test_duplicate_is_rejected(self):
        with self.assertRaises(ValueError): freeze_private_pilot_manifest([self.sample(),self.sample()])

if __name__ == "__main__": unittest.main()
