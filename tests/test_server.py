"""
Unit tests for the server module.
"""

import os
import json
import socket
import unittest
import tempfile
import threading
from unittest import mock
from roxy.server import ProxyServer, RoxyServerError, PortInUseError, PermissionError, ConnectionError, ConfigError

class TestProxyServer(unittest.TestCase):
    """Test cases for the ProxyServer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test files
        self.test_dir = tempfile.TemporaryDirectory()
        # Mock the home directory path to use our temporary directory
        self.home_dir_patcher = mock.patch('os.path.expanduser')
        self.mock_expanduser = self.home_dir_patcher.start()
        self.mock_expanduser.return_value = self.test_dir.name
        
        # Create a ProxyServer instance with mocked Flask app
        self.server = ProxyServer()
        self.server.app = mock.MagicMock()
        
        # Create a test mapping file
        self.mapping_file = os.path.join(self.test_dir.name, 'port_mappings.json')
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.home_dir_patcher.stop()
        self.test_dir.cleanup()
    
    def test_init(self):
        """Test initialization of ProxyServer."""
        self.assertEqual(self.server.host, '127.0.0.1')
        self.assertEqual(self.server.port, 5000)
        self.assertEqual(self.server.start_port, 10000)
        self.assertEqual(self.server.delimiter, '|')
        self.assertDictEqual(self.server.active_proxies, {})
        self.assertEqual(self.server.mapping_file, os.path.join(self.test_dir.name, 'port_mappings.json'))
        
        # Check protocol ports
        self.assertEqual(self.server.protocol_ports['ssh'], 22)
        self.assertEqual(self.server.protocol_ports['http'], 80)
        self.assertEqual(self.server.protocol_ports['https'], 443)
    
    def test_load_mappings_empty(self):
        """Test loading mappings when the file doesn't exist."""
        mappings = self.server.load_mappings()
        self.assertDictEqual(mappings, {})
    
    def test_load_mappings_valid(self):
        """Test loading mappings from a valid file."""
        # Create a test mapping file
        test_mappings = {
            '10.0.0.1|ssh': 10000,
            '10.0.0.2|http': 10001
        }
        os.makedirs(os.path.dirname(self.mapping_file), exist_ok=True)
        with open(self.mapping_file, 'w') as f:
            json.dump(test_mappings, f)
        
        # Load the mappings
        mappings = self.server.load_mappings()
        
        # Check that the mappings were loaded correctly
        self.assertEqual(len(mappings), 2)
        self.assertEqual(mappings[('10.0.0.1', 'ssh')], 10000)
        self.assertEqual(mappings[('10.0.0.2', 'http')], 10001)
    
    def test_load_mappings_invalid_json(self):
        """Test loading mappings from an invalid JSON file."""
        # Create an invalid JSON file
        os.makedirs(os.path.dirname(self.mapping_file), exist_ok=True)
        with open(self.mapping_file, 'w') as f:
            f.write('invalid json')
        
        # Load the mappings - should return an empty dict without raising an exception
        mappings = self.server.load_mappings()
        self.assertDictEqual(mappings, {})
    
    def test_save_mappings(self):
        """Test saving mappings to a file."""
        # Create test mappings
        test_mappings = {
            ('10.0.0.1', 'ssh'): 10000,
            ('10.0.0.2', 'http'): 10001
        }
        
        # Save the mappings
        self.server.save_mappings(test_mappings)
        
        # Check that the file was created
        self.assertTrue(os.path.exists(self.mapping_file))
        
        # Load the mappings and check they match
        with open(self.mapping_file, 'r') as f:
            saved_mappings = json.load(f)
        
        self.assertEqual(len(saved_mappings), 2)
        self.assertEqual(saved_mappings['10.0.0.1|ssh'], 10000)
        self.assertEqual(saved_mappings['10.0.0.2|http'], 10001)
    
    def test_save_mappings_permission_error(self):
        """Test saving mappings when permission is denied."""
        # Mock os.makedirs to raise PermissionError
        with mock.patch('os.makedirs', side_effect=PermissionError):
            with self.assertRaises(ConfigError):
                self.server.save_mappings({('10.0.0.1', 'ssh'): 10000})
    
    @mock.patch('socket.socket')
    def test_start_tcp_proxy_success(self, mock_socket):
        """Test starting a TCP proxy successfully."""
        # Mock socket instance
        mock_socket_instance = mock.MagicMock()
        mock_socket.return_value = mock_socket_instance
        
        # Call the method
        self.server.start_tcp_proxy(10000, '10.0.0.1', 22)
        
        # Check that the proxy was added to active_proxies
        self.assertEqual(len(self.server.active_proxies), 1)
        self.assertIn(10000, self.server.active_proxies)
    
    @mock.patch('socket.socket')
    def test_start_tcp_proxy_port_in_use(self, mock_socket):
        """Test starting a TCP proxy when the port is already in use."""
        # Mock socket instance to raise socket.error with errno 98 (Address already in use)
        mock_socket_instance = mock.MagicMock()
        mock_socket_instance.bind.side_effect = socket.error(98, 'Address already in use')
        mock_socket.return_value = mock_socket_instance
        
        # Start a thread that will raise the exception
        def proxy_thread():
            with self.assertRaises(PortInUseError):
                self.server.start_tcp_proxy(10000, '10.0.0.1', 22)
        
        thread = threading.Thread(target=proxy_thread)
        thread.start()
        thread.join(timeout=1)
    
    @mock.patch('socket.socket')
    def test_start_tcp_proxy_permission_denied(self, mock_socket):
        """Test starting a TCP proxy when permission is denied."""
        # Mock socket instance to raise socket.error with errno 13 (Permission denied)
        mock_socket_instance = mock.MagicMock()
        mock_socket_instance.bind.side_effect = socket.error(13, 'Permission denied')
        mock_socket.return_value = mock_socket_instance
        
        # Start a thread that will raise the exception
        def proxy_thread():
            with self.assertRaises(PermissionError):
                self.server.start_tcp_proxy(10000, '10.0.0.1', 22)
        
        thread = threading.Thread(target=proxy_thread)
        thread.start()
        thread.join(timeout=1)
    
    def test_handle_client_connection_success(self):
        """Test handling a client connection successfully."""
        # Mock client and remote sockets
        client_socket = mock.MagicMock()
        client_socket.getpeername.return_value = ('127.0.0.1', 12345)
        
        # Mock socket.socket to return a mock remote socket
        with mock.patch('socket.socket') as mock_socket:
            mock_remote_socket = mock.MagicMock()
            mock_socket.return_value = mock_remote_socket
            
            # Mock threading.Thread to avoid actually starting threads
            with mock.patch('threading.Thread') as mock_thread:
                # Call the method
                self.server.handle_client_connection(client_socket, '10.0.0.1', 22)
                
                # Check that the remote socket was connected to the right address
                mock_remote_socket.connect.assert_called_once_with(('10.0.0.1', 22))
                
                # Check that two threads were started for forwarding data
                self.assertEqual(mock_thread.call_count, 2)
    
    def test_handle_client_connection_timeout(self):
        """Test handling a client connection when the connection times out."""
        # Mock client socket
        client_socket = mock.MagicMock()
        client_socket.getpeername.return_value = ('127.0.0.1', 12345)
        
        # Mock socket.socket to raise socket.timeout
        with mock.patch('socket.socket') as mock_socket:
            mock_remote_socket = mock.MagicMock()
            mock_remote_socket.connect.side_effect = socket.timeout
            mock_socket.return_value = mock_remote_socket
            
            # Call the method and check that it raises ConnectionError
            with self.assertRaises(ConnectionError):
                self.server.handle_client_connection(client_socket, '10.0.0.1', 22)
            
            # Check that the client socket was closed
            client_socket.close.assert_called_once()
    
    def test_handle_client_connection_refused(self):
        """Test handling a client connection when the connection is refused."""
        # Mock client socket
        client_socket = mock.MagicMock()
        client_socket.getpeername.return_value = ('127.0.0.1', 12345)
        
        # Mock socket.socket to raise ConnectionRefusedError
        with mock.patch('socket.socket') as mock_socket:
            mock_remote_socket = mock.MagicMock()
            mock_remote_socket.connect.side_effect = ConnectionRefusedError
            mock_socket.return_value = mock_remote_socket
            
            # Call the method and check that it raises ConnectionError
            with self.assertRaises(ConnectionError):
                self.server.handle_client_connection(client_socket, '10.0.0.1', 22)
            
            # Check that the client socket was closed
            client_socket.close.assert_called_once()
    
    def test_forward_data(self):
        """Test forwarding data between sockets."""
        # Mock source and destination sockets
        source_socket = mock.MagicMock()
        destination_socket = mock.MagicMock()
        
        # Set up source_socket.recv to return data once, then empty string to simulate end of data
        source_socket.recv.side_effect = [b'test data', b'']
        
        # Call the method
        self.server.forward_data(source_socket, destination_socket, 'source', 'destination')
        
        # Check that data was received and sent
        source_socket.recv.assert_called_with(8192)
        destination_socket.sendall.assert_called_once_with(b'test data')
        
        # Check that both sockets were closed
        source_socket.close.assert_called_once()
        destination_socket.close.assert_called_once()
    
    def test_forward_data_connection_reset(self):
        """Test forwarding data when the connection is reset."""
        # Mock source and destination sockets
        source_socket = mock.MagicMock()
        destination_socket = mock.MagicMock()
        
        # Set up source_socket.recv to raise ConnectionResetError
        source_socket.recv.side_effect = ConnectionResetError
        
        # Call the method
        self.server.forward_data(source_socket, destination_socket, 'source', 'destination')
        
        # Check that both sockets were closed
        source_socket.close.assert_called_once()
        destination_socket.close.assert_called_once()
    
    def test_restart_proxies(self):
        """Test restarting proxies from saved mappings."""
        # Create test mappings
        test_mappings = {
            ('10.0.0.1', 'ssh'): 10000,
            ('10.0.0.2', 'http'): 10001
        }
        
        # Save the mappings
        self.server.save_mappings(test_mappings)
        
        # Mock start_tcp_proxy to track calls
        self.server.start_tcp_proxy = mock.MagicMock()
        
        # Call the method
        self.server.restart_proxies()
        
        # Check that start_tcp_proxy was called for each mapping
        self.assertEqual(self.server.start_tcp_proxy.call_count, 2)
        self.server.start_tcp_proxy.assert_any_call(10000, '10.0.0.1', 22)
        self.server.start_tcp_proxy.assert_any_call(10001, '10.0.0.2', 80)
    
    def test_restart_proxies_invalid_protocol(self):
        """Test restarting proxies with an invalid protocol."""
        # Create test mappings with an invalid protocol
        test_mappings = {
            ('10.0.0.1', 'invalid'): 10000
        }
        
        # Save the mappings
        self.server.save_mappings(test_mappings)
        
        # Mock start_tcp_proxy to track calls
        self.server.start_tcp_proxy = mock.MagicMock()
        
        # Call the method
        self.server.restart_proxies()
        
        # Check that start_tcp_proxy was not called
        self.server.start_tcp_proxy.assert_not_called()
    
    def test_stop_proxy(self):
        """Test stopping a proxy."""
        # Create a mock proxy thread
        mock_thread = mock.MagicMock()
        self.server.active_proxies[10000] = mock_thread
        
        # Call the method
        self.server.stop_proxy(10000)
        
        # Check that the thread was joined and removed from active_proxies
        mock_thread.join.assert_called_once()
        self.assertNotIn(10000, self.server.active_proxies)
    
    def test_stop(self):
        """Test stopping all proxies."""
        # Create mock proxy threads
        mock_thread1 = mock.MagicMock()
        mock_thread2 = mock.MagicMock()
        self.server.active_proxies[10000] = mock_thread1
        self.server.active_proxies[10001] = mock_thread2
        
        # Mock stop_proxy to track calls
        self.server.stop_proxy = mock.MagicMock()
        
        # Call the method
        self.server.stop()
        
        # Check that stop_proxy was called for each active proxy
        self.assertEqual(self.server.stop_proxy.call_count, 2)
        self.server.stop_proxy.assert_any_call(10000)
        self.server.stop_proxy.assert_any_call(10001)
    
    @mock.patch('flask.Flask.run')
    def test_start(self, mock_run):
        """Test starting the server."""
        # Mock restart_proxies to avoid actual proxy creation
        self.server.restart_proxies = mock.MagicMock()
        
        # Call the method
        self.server.start()
        
        # Check that restart_proxies was called
        self.server.restart_proxies.assert_called_once()
        
        # Check that Flask.run was called with the correct arguments
        mock_run.assert_called_once_with(host=self.server.host, port=self.server.port)
    
    @mock.patch('flask.Flask.run')
    def test_start_port_in_use(self, mock_run):
        """Test starting the server when the port is already in use."""
        # Mock restart_proxies to avoid actual proxy creation
        self.server.restart_proxies = mock.MagicMock()
        
        # Mock Flask.run to raise socket.error with errno 98 (Address already in use)
        mock_run.side_effect = socket.error(98, 'Address already in use')
        
        # Call the method and check that it raises PortInUseError
        with self.assertRaises(PortInUseError):
            self.server.start()
    
    @mock.patch('flask.Flask.run')
    def test_start_permission_denied(self, mock_run):
        """Test starting the server when permission is denied."""
        # Mock restart_proxies to avoid actual proxy creation
        self.server.restart_proxies = mock.MagicMock()
        
        # Mock Flask.run to raise socket.error with errno 13 (Permission denied)
        mock_run.side_effect = socket.error(13, 'Permission denied')
        
        # Call the method and check that it raises PermissionError
        with self.assertRaises(PermissionError):
            self.server.start()

if __name__ == '__main__':
    unittest.main()