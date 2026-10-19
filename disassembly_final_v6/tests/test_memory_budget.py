import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from disassembly_final_v6 import actors
from disassembly_final_v6.contracts import LIMITS,DEV_LIMITS,MODEL,EFFORT,ARMS
from disassembly_final_v5.contracts import LIMITS as OLD,DEV_LIMITS as OLD_DEV


class CommonMemoryBudgetTests(unittest.TestCase):
    def test_only_memory_cap_changes_in_final_and_additional_training(self):
        self.assertEqual(LIMITS,{**OLD,'max_rss_bytes':4*1024**3})
        self.assertEqual(DEV_LIMITS,{**OLD_DEV,'max_rss_bytes':4*1024**3})
        self.assertEqual((MODEL,EFFORT),('gpt-6-luna','low'))
        self.assertEqual(ARMS['B']['bank'],ARMS['C']['bank'])

    def test_measured_two_gib_is_allowed_by_new_shared_guard(self):
        units=1 if sys.platform=='darwin' else 1024
        with patch.object(actors.resource,'getrusage',return_value=SimpleNamespace(ru_maxrss=2*1024**3/units)):
            actors.rss_guard(LIMITS['max_rss_bytes'])
            with self.assertRaises(actors.LimitError):actors.rss_guard(1024**3)

    def test_limit_message_reports_the_actual_four_gib_cap(self):
        units=1 if sys.platform=='darwin' else 1024
        with patch.object(actors.resource,'getrusage',return_value=SimpleNamespace(ru_maxrss=5*1024**3/units)):
            with self.assertRaisesRegex(actors.LimitError,'4 GiB resident-memory ceiling'):
                actors.rss_guard(LIMITS['max_rss_bytes'])


if __name__=='__main__':unittest.main()
