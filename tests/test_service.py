"""
Unit tests for the service module.
"""

import os
import json
import time
import signal
import unittest
import tempfile
from unittest import mock
from roxy.service import ServiceManager

class TestServiceManager(unittest.TestCase):
    """Test cases for the ServiceManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test files
        self.test_dir = tempfile.TemporaryDirectory()
        # Create a ServiceManager instance with the test directory
        self.service_manager = ServiceManager(
            pid_file=os.path.join(self.test_dir.name, 'roxy.pid'),
            config_dir=self.test_dir.name
        )
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.test_dir.cleanup()
    
    def test_init(self):
        """Test initialization of ServiceManager."""
        self.assertEqual(self.service_manager.config_dir, self.test_dir.name)
        self.assertEqual(self.service_manager.pid_file, os.path.join(self.test_dir.name, 'roxy.pid'))
        self.assertEqual(self.service_manager.first_run_flag, os.path.join(self.test_dir.name, '.first_run'))
        
        # Check that the config directory was created
        self.assertTrue(os.path.exists(self.test_dir.name))
    
    def test_get_pid_no_file(self):
        """Test getting PID when the PID file doesn't exist."""
        self.assertIsNone(self.service_manager.get_pid())
    
    def test_get_pid_valid(self):
        """Test getting PID from a valid PID file."""
        # Create a test PID file
        with open(self.service_manager.pid_file, 'w') as f:
            f.write('12345')
        
        # Get the PID
        pid = self.service_manager.get_pid()
        
        # Check that the PID was read correctly
        self.assertEqual(pid, 12345)
    
    def test_get_pid_invalid(self):
        """Test getting PID from an invalid PID file."""
      