"""
Comprehensive tests for website validation service.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

import aiohttp

from src.services.website_validation_service import (
    WebsiteValidationService, 
    WebsiteValidationResult
)


class TestWebsiteValidationResult:
    """Test WebsiteValidationResult class."""
    
    def test_valid_result_properties(self):
        """Test validation result with valid properties."""
        result = WebsiteValidationResult(
            url="https://example.com",
            is_accessible=True,
            status_code=200,
            response_time=2.5,
            has_ssl=True,
            business_name_match=0.8,
            contact_info_match=True,
            has_business_content=True
        )
        
        assert result.is_valid == True
        assert result.url == "https://example.com"
        assert result.status_code == 200
        assert result.business_name_match == 0.8
        
    def test_invalid_result_low_match(self):
        """Test validation result with low business name match."""
        result = WebsiteValidationResult(
            url="https://example.com",
            is_accessible=True,
            status_code=200,
            response_time=2.5,
            has_ssl=True,
            business_name_match=0.3,  # Too low
            contact_info_match=True,
            has_business_content=True
        )
        
        assert result.is_valid == False
        
    def test_invalid_result_slow_response(self):
        """Test validation result with slow response time."""
        result = WebsiteValidationResult(
            url="https://example.com",
            is_accessible=True,
            status_code=200,
            response_time=15.0,  # Too slow
            has_ssl=True,
            business_name_match=0.8,
            contact_info_match=True,
            has_business_content=True
        )
        
        assert result.is_valid == False
        
    def test_invalid_result_bad_status(self):
        """Test validation result with bad HTTP status."""
        result = WebsiteValidationResult(
            url="https://example.com",
            is_accessible=True,
            status_code=404,  # Not found
            response_time=2.5,
            has_ssl=True,
            business_name_match=0.8,
            contact_info_match=True,
            has_business_content=True
        )
        
        assert result.is_valid == False
        
    def test_to_dict_conversion(self):
        """Test conversion to dictionary."""
        result = WebsiteValidationResult(
            url="https://example.com",
            is_accessible=True,
            status_code=200,
            response_time=2.5,
            has_ssl=True,
            business_name_match=0.8,
            contact_info_match=True,
            has_business_content=True
        )
        
        result_dict = result.to_dict()
        
        assert result_dict['url'] == "https://example.com"
        assert result_dict['is_accessible'] == True
        assert result_dict['status_code'] == 200
        assert result_dict['business_name_match'] == 0.8
        assert result_dict['is_valid'] == True
        assert 'validation_timestamp' in result_dict


class TestWebsiteValidationService:
    """Test WebsiteValidationService class."""
    
    @pytest.fixture
    def validator(self):
        """Create website validator instance."""
        return WebsiteValidationService(timeout=5.0, max_retries=2)
    
    def test_normalize_url(self, validator):
        """Test URL normalization."""
        # Test adding protocol
        assert validator._normalize_url("example.com") == "https://example.com"
        assert validator._normalize_url("www.example.com") == "https://www.example.com"
        
        # Test existing protocol preservation
        assert validator._normalize_url("http://example.com") == "http://example.com"
        assert validator._normalize_url("https://example.com") == "https://example.com"
        
        # Test case normalization
        assert validator._normalize_url("EXAMPLE.COM") == "https://example.com"
        
    @pytest.mark.asyncio
    async def test_successful_validation(self, validator):
        """Test successful website validation."""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.url = "https://acme-corp.com"
        mock_response.text = AsyncMock(return_value="""
            <html>
            <head><title>ACME Corporation - Manufacturing Excellence</title></head>
            <body>
                <h1>Welcome to ACME Corporation</h1>
                <p>About our company: ACME Corp has been serving clients since 2005</p>
                <p>Services: Manufacturing, wholesale distribution</p>
                <p>Contact us: (905) 555-0123</p>
                <p>Address: 123 Business St, Hamilton, ON</p>
                <div>Products and solutions for businesses</div>
            </body>
            </html>
        """)
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            
            result = await validator.validate_website(
                url="https://acme-corp.com",
                business_name="ACME Corporation",
                business_phone="(905) 555-0123",
                business_address="123 Business St"
            )
            
            assert result.is_accessible == True
            assert result.status_code == 200
            assert result.has_ssl == True
            assert result.business_name_match > 0.6
            assert result.has_business_content == True
            assert result.is_valid == True
            
    @pytest.mark.asyncio
    async def test_failed_validation_404(self, validator):
        """Test validation failure with 404 status."""
        mock_response = Mock()
        mock_response.status = 404
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            
            result = await validator.validate_website(
                url="https://nonexistent.com",
                business_name="Test Business"
            )
            
            assert result.is_accessible == True  # Response received
            assert result.status_code == 404
            assert result.is_valid == False  # Invalid due to bad status
            
    @pytest.mark.asyncio
    async def test_validation_timeout(self, validator):
        """Test validation handling of timeouts."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.side_effect = asyncio.TimeoutError("Timeout")
            
            result = await validator.validate_website(
                url="https://slow-website.com",
                business_name="Test Business"
            )
            
            assert result.is_accessible == False
            assert "Timeout after" in result.error_message
            assert result.is_valid == False
            
    @pytest.mark.asyncio
    async def test_validation_connection_error(self, validator):
        """Test validation handling of connection errors."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.side_effect = aiohttp.ClientConnectorError(
                connection_key=None, os_error=None
            )
            
            result = await validator.validate_website(
                url="https://unreachable.com",
                business_name="Test Business"
            )
            
            assert result.is_accessible == False
            assert "Request failed" in result.error_message
            assert result.is_valid == False
            
    def test_business_name_match_calculation(self, validator):
        """Test business name matching algorithm."""
        from bs4 import BeautifulSoup
        
        # Test high match
        html_content = """
        <html>
        <head><title>Hamilton Manufacturing Co - Quality Products</title></head>
        <body>
            <h1>Hamilton Manufacturing Co</h1>
            <p>Welcome to Hamilton Manufacturing Company</p>
        </body>
        </html>
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        match = validator._calculate_business_name_match(
            soup, "Hamilton Manufacturing Co"
        )
        assert match > 0.6
        
        # Test low match
        html_content = """
        <html>
        <head><title>Completely Different Business</title></head>
        <body><p>Nothing related here</p></body>
        </html>
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        match = validator._calculate_business_name_match(
            soup, "Hamilton Manufacturing Co"
        )
        assert match < 0.3
        
    def test_contact_info_validation(self, validator):
        """Test contact information validation."""
        from bs4 import BeautifulSoup
        
        # Test matching contact info
        html_content = """
        <html>
        <body>
            <p>Call us at (905) 555-0123</p>
            <p>Located at 123 Business Street</p>
        </body>
        </html>
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = validator._validate_contact_info(
            soup, "(905) 555-0123", "123 Business Street"
        )
        assert result == True
        
        # Test non-matching contact info
        html_content = """
        <html>
        <body>
            <p>Call us at (416) 999-8888</p>
            <p>Located at 999 Different Ave</p>
        </body>
        </html>
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = validator._validate_contact_info(
            soup, "(905) 555-0123", "123 Business Street"
        )
        assert result == False
        
    def test_business_content_validation(self, validator):
        """Test business content validation."""
        from bs4 import BeautifulSoup
        
        # Test legitimate business content
        html_content = """
        <html>
        <body>
            <nav>
                <a href="/about">About</a>
                <a href="/services">Services</a>
                <a href="/contact">Contact</a>
                <a href="/products">Products</a>
            </nav>
            <p>We are a professional company offering quality services 
            to our business clients. Contact us for more information about 
            our products and solutions. We have been serving customers 
            since 2005 with excellent customer service and reliable 
            business solutions.</p>
        </body>
        </html>
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = validator._validate_business_content(soup)
        assert result == True
        
        # Test insufficient business content
        html_content = """
        <html>
        <body>
            <p>Simple page</p>
        </body>
        </html>
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        result = validator._validate_business_content(soup)
        assert result == False
        
    @pytest.mark.asyncio
    async def test_multiple_website_validation(self, validator):
        """Test validating multiple websites concurrently."""
        website_data = [
            {
                'url': 'https://business1.com',
                'business_name': 'Business One',
                'phone': '(905) 111-1111'
            },
            {
                'url': 'https://business2.com',
                'business_name': 'Business Two',
                'phone': '(905) 222-2222'
            }
        ]
        
        # Mock successful responses
        mock_response = Mock()
        mock_response.status = 200
        mock_response.url = "https://business.com"
        mock_response.text = AsyncMock(return_value="""
            <html>
            <head><title>Business</title></head>
            <body>
                <p>About our business services and products</p>
                <nav><a href="/about">About</a><a href="/contact">Contact</a></nav>
            </body>
            </html>
        """)
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
            
            results = await validator.validate_multiple_websites(website_data)
            
            assert len(results) == 2
            assert all(isinstance(result, WebsiteValidationResult) for result in results)
            
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality."""
        async with WebsiteValidationService() as validator:
            assert validator._session is not None
            
        # Session should be closed after context exit
        # Note: This test validates the pattern, actual session closing 
        # would be tested with more sophisticated mocking


class TestWebsiteValidationIntegration:
    """Integration tests with realistic scenarios."""
    
    @pytest.mark.asyncio
    async def test_real_business_scenario(self):
        """Test validation with realistic business scenario."""
        validator = WebsiteValidationService(timeout=10.0)
        
        # Mock a realistic business website response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.url = "https://steelworksinc.com"
        mock_response.text = AsyncMock(return_value="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Steel Works Inc - Hamilton Metal Manufacturing</title>
                <meta name="description" content="Steel Works Inc provides quality metal fabrication">
            </head>
            <body>
                <header>
                    <h1>Steel Works Inc</h1>
                    <nav>
                        <a href="/about">About Us</a>
                        <a href="/services">Services</a>
                        <a href="/contact">Contact</a>
                        <a href="/products">Products</a>
                    </nav>
                </header>
                <main>
                    <section>
                        <h2>About Steel Works Inc</h2>
                        <p>Since 2005, Steel Works Inc has been Hamilton's premier metal fabrication company.
                        We provide professional manufacturing services to businesses across Ontario.</p>
                        <p>Our experienced team delivers quality products and reliable service.</p>
                    </section>
                    <section>
                        <h2>Our Services</h2>
                        <ul>
                            <li>Custom metal fabrication</li>
                            <li>Steel manufacturing</li>
                            <li>Industrial equipment</li>
                        </ul>
                    </section>
                    <section>
                        <h2>Contact Information</h2>
                        <p>Phone: (905) 555-STEEL</p>
                        <p>Email: info@steelworksinc.com</p>
                        <p>Address: 456 Industrial Drive, Hamilton, ON L8E 3K2</p>
                    </section>
                </main>
            </body>
            </html>
        """)
        
        async with validator:
            with patch('aiohttp.ClientSession.get') as mock_get:
                mock_get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
                mock_get.return_value.__aexit__ = AsyncMock(return_value=None)
                
                result = await validator.validate_website(
                    url="https://steelworksinc.com",
                    business_name="Steel Works Inc",
                    business_phone="(905) 555-7833",  # STEEL in numbers
                    business_address="456 Industrial Drive"
                )
                
                # Validate comprehensive results
                assert result.is_accessible == True
                assert result.status_code == 200
                assert result.has_ssl == True
                assert result.business_name_match > 0.8  # High match expected
                assert result.contact_info_match == True
                assert result.has_business_content == True
                assert result.is_valid == True
                assert result.response_time is not None
                assert result.validation_timestamp is not None
                
                # Validate dictionary conversion
                result_dict = result.to_dict()
                assert 'url' in result_dict
                assert 'is_valid' in result_dict
                assert 'validation_timestamp' in result_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])