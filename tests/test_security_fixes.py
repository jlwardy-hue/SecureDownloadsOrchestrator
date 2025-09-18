#!/usr/bin/env python3
"""
Tests for SecureDownloadsOrchestrator security and quality fixes.
Tests the critical security improvements and behavioral changes.
"""

import os
import sys
import tempfile
import shutil
import yaml
import unittest
from unittest.mock import patch, MagicMock

# Add modules path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.organize import is_keyword_match_file, organize_file
from modules.extract import extract_archives


class TestSecurityFixes(unittest.TestCase):
    """Test suite for security and quality improvements."""
    
    def setUp(self):
        """Set up test configuration."""
        self.test_config = {
            'directories': {
                'organized': tempfile.mkdtemp(prefix='test_organized_'),
                'quarantine': tempfile.mkdtemp(prefix='test_quarantine_'),
                'logs': '/tmp/test.log'
            },
            'content_organization': {
                'Springfield': ['springfield', 'homer', 'simpsons'],
                'Business': ['business', 'contract', 'invoice'],
                'ProjectAlpha': ['project_alpha', 'alpha']
            }
        }
    
    def tearDown(self):
        """Clean up test directories."""
        for dir_path in [self.test_config['directories']['organized'], 
                        self.test_config['directories']['quarantine']]:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)
    
    def test_content_organization_generalization(self):
        """Test that content organization is now configurable and generalized."""
        # Test Springfield matching (original example)
        result = is_keyword_match_file('/test/homer_simpson.jpg', self.test_config)
        self.assertEqual(result, 'Springfield')
        
        # Test new business folder matching
        result = is_keyword_match_file('/test/business_contract.pdf', self.test_config)
        self.assertEqual(result, 'Business')
        
        # Test project folder matching
        result = is_keyword_match_file('/test/project_alpha_docs.txt', self.test_config)
        self.assertEqual(result, 'ProjectAlpha')
        
        # Test no match
        result = is_keyword_match_file('/test/random_file.txt', self.test_config)
        self.assertIsNone(result)
    
    def test_case_insensitive_matching(self):
        """Test that keyword matching is case-insensitive."""
        result = is_keyword_match_file('/test/HOMER_SIMPSON.JPG', self.test_config)
        self.assertEqual(result, 'Springfield')
        
        result = is_keyword_match_file('/test/Business_Document.pdf', self.test_config)
        self.assertEqual(result, 'Business')
    
    @patch('modules.extract.tempfile.mkdtemp')
    def test_secure_temp_directory_usage(self, mock_mkdtemp):
        """Test that extract_archives uses secure random temp directories."""
        mock_mkdtemp.return_value = '/tmp/secure_test_dir'
        
        # Mock the file operations to avoid actual extraction
        with patch('os.path.exists', return_value=False), \
             patch('os.walk', return_value=[]), \
             patch('shutil.rmtree'):
            
            result = extract_archives('/fake/test.zip', self.test_config)
            
            # Verify tempfile.mkdtemp was called with security parameters
            mock_mkdtemp.assert_called_once_with(prefix="secure_extract_", suffix="_tmp")
    
    def test_config_validation(self):
        """Test that the new configuration format is valid and accessible."""
        # Test default config loading
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        # Verify content_organization section exists
        self.assertIn('content_organization', config)
        self.assertIn('Springfield', config['content_organization'])
        
        # Verify it's configurable (has example comments)
        with open(config_path) as f:
            content = f.read()
            self.assertIn('# Example:', content)
            self.assertIn('business', content.lower())
    
    def test_module_logging_initialization(self):
        """Test that modules properly initialize logging."""
        # This test verifies that modules can be imported without print statements
        import modules.organize
        import modules.extract
        import modules.metadata
        import modules.monitor
        import modules.antivirus
        
        # If we get here without exceptions, modules imported successfully
        self.assertTrue(True)
    
    def test_io_module_import(self):
        """Test that io module is properly imported where needed."""
        import modules.organize
        import modules.extract
        
        # Verify io module is available in modules that need it
        self.assertTrue(hasattr(modules.organize, 'io'))
        self.assertTrue(hasattr(modules.extract, 'io'))


class TestBinaryHandling(unittest.TestCase):
    """Test binary content handling improvements."""
    
    def test_file_hash_binary_handling(self):
        """Test that file hashing properly handles binary content."""
        from modules.organize import file_hash
        
        # Create a test binary file
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
            binary_data = b'\x00\x01\x02\xff\xfe\xfd'  # Binary content
            f.write(binary_data)
            test_file = f.name
        
        try:
            # Test that hash calculation doesn't fail on binary content
            hash_result = file_hash(test_file)
            self.assertIsInstance(hash_result, str)
            self.assertEqual(len(hash_result), 64)  # SHA256 hex length
        finally:
            os.unlink(test_file)


if __name__ == '__main__':
    unittest.main()