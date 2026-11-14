# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Python stdlib (pathlib, subprocess, sys, unittest); local modules (animate).
"""Regression checks for transient and persistent set_pose failures."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from animate import send_pose


def reply(text, code=0):
    return subprocess.CompletedProcess([],code,stdout=text,stderr='')


class PoseRetries(unittest.TestCase):
    @patch('animate.time.sleep')
    @patch('animate.subprocess.run')
    def test_transient_failures_retry_identical_pose(self, run, sleep):
        run.side_effect=[reply('Service call timed out',1),
                         subprocess.TimeoutExpired(['gz'],8),reply('data: true\n')]
        self.assertEqual(send_pose((1,2,3),'funnel_demo'),3)
        commands=[call.args[0] for call in run.call_args_list]
        self.assertTrue(all(command==commands[0] for command in commands))
        self.assertEqual(sleep.call_count,2)

    @patch('animate.time.sleep')
    @patch('animate.subprocess.run',return_value=reply('data: false\n'))
    def test_persistent_rejection_is_bounded(self, run, sleep):
        with self.assertRaisesRegex(RuntimeError,'after 3 attempts'):
            send_pose((1,2,3),'funnel_demo',retries=2)
        self.assertEqual(run.call_count,3)
        self.assertEqual(sleep.call_count,2)

    @patch('animate.time.sleep')
    @patch('animate.subprocess.run',return_value=reply('transport true status is unavailable',1))
    def test_failure_is_not_accepted_as_success(self, run, sleep):
        with self.assertRaises(RuntimeError):
            send_pose((1,2,3),'funnel_demo',retries=0)
        self.assertEqual(run.call_count,1)


if __name__=='__main__':
    unittest.main()
