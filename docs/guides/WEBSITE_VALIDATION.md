# Website Validation System

## Overview

The website validation system ensures that all business websites in the lead generation pipeline are legitimate, accessible, and properly matched to their corresponding businesses. This prevents the inclusion of fake or non-existent websites in export data.

## Key Features

### 1. HTTP Accessibility Verification
- **Status Code Validation**: Only websites returning HTTP 200 OK are considered valid
- **Response Time Monitoring**: Websites must respond within 10 seconds
- **SSL/TLS Detection**: Identifies HTTPS-enabled websites for security assessment
- **Redirect Handling**: Follows redirects to final destination URL

### 2. Business-Website Matching
- **Content Analysis**: Extracts and analyzes website text content
- **Name Matching Algorithm**: Compares business name with website content using fuzzy matching
- **Threshold Enforcement**: Requires minimum 60% business name match confidence
- **Title and Header Priority**: Gives higher weight to matches in page titles and headers

### 3. Contact Information Verification
- **Phone Number Matching**: Validates phone numbers appear on website
- **Address Consistency**: Checks for address information alignment
- **Cross-Reference Validation**: Ensures contact details are consistent across sources

### 4. Business Content Assessment
- **Professional Content Detection**: Identifies legitimate business indicators
- **Navigation Structure**: Validates presence of business-standard pages (About, Services, Contact)
- **Content Volume Analysis**: Ensures sufficient content for a legitimate business
- **Service/Product Information**: Looks for business offerings and descriptions

## Implementation

### WebsiteValidationService

```python
from src.services.website_validation_service import WebsiteValidationService

# Initialize validator
validator = WebsiteValidationService(
    timeout=10.0,
    max_retries=3
)

# Validate single website
async with validator:
    result = await validator.validate_website(
        url="https://business.com",
        business_name="Business Name",
        business_phone="(905) 555-0123",
        business_address="123 Business St"
    )
    
    if result.is_valid:
        print(f"Website validated successfully: {result.business_name_match:.1%} match")
    else:
        print(f"Validation failed: {result.error_message}")
```

### Integration with Business Validation

The website validation is automatically integrated into the main business validation pipeline:

```python
from src.services.validation_service import BusinessValidationService

validator = BusinessValidationService(config)
is_valid, issues = await validator.validate_business_lead(lead)
```

## Validation Results

### WebsiteValidationResult Properties

- **url**: Normalized website URL
- **is_accessible**: Whether the website responded successfully
- **status_code**: HTTP response status code
- **response_time**: Time taken to respond (seconds)
- **has_ssl**: Whether the website uses HTTPS
- **business_name_match**: Confidence score (0.0-1.0) of business name match
- **contact_info_match**: Whether contact information is consistent
- **has_business_content**: Whether site has legitimate business content
- **validation_timestamp**: When validation was performed
- **error_message**: Details if validation failed

### Validation Criteria for Success

A website is considered valid if ALL of the following are true:
- ✅ HTTP 200 OK response
- ✅ Response time < 10 seconds
- ✅ Business name match ≥ 60%
- ✅ Contains legitimate business content
- ✅ No validation errors occurred

## Database Integration

### ContactInfo Model Updates

The `ContactInfo` model now includes website validation fields:

```python
class ContactInfo(BaseModel):
    # Basic contact info
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    
    # Website validation fields
    website_validated: bool = False
    website_validation_timestamp: Optional[datetime] = None
    website_status_code: Optional[int] = None
    website_response_time: Optional[float] = None
    website_business_name_match: float = 0.0
    website_has_ssl: bool = False
    website_validation_error: Optional[str] = None
    
    def is_website_verified(self) -> bool:
        """Check if website is properly verified."""
        return (
            self.website_validated and
            self.website_status_code == 200 and
            self.website_business_name_match >= 0.6 and
            not self.website_validation_error
        )
```

## Export Data Protection

### Verified Websites Only

All export functions now filter out unverified websites:

- **CSV Exports**: Include `website_verified` and `website_validation_status` columns
- **JSON Exports**: Include complete `website_validation` object with verification details
- **Summary Reports**: Show website verification statistics

### Export Fields Added

- `website_verified`: YES/NO indicator
- `website_validation_status`: HTTP status code
- `website_business_match`: Match percentage
- `website_validation.verified`: Boolean verification status
- `website_validation.status_code`: Response status
- `website_validation.business_match_score`: Numerical match score
- `website_validation.validation_timestamp`: When verified
- `website_validation.has_ssl`: SSL certificate status

## Configuration

### WebsiteValidationConfig

```python
@dataclass
class WebsiteValidationConfig:
    enabled: bool = True
    timeout_seconds: float = 10.0
    max_retries: int = 3
    min_business_name_match: float = 0.6
    require_ssl: bool = False
    max_response_time: float = 10.0
    require_business_content: bool = True
    parallel_validation_limit: int = 5
    cache_validation_hours: int = 24
```

Access via system config:
```python
from src.core.config import config
validation_config = config.website_validation
```

## Error Handling

### Common Validation Failures

1. **Network Errors**
   - Connection timeouts
   - DNS resolution failures
   - Connection refused

2. **HTTP Errors**
   - 404 Not Found
   - 403 Forbidden
   - 500 Server Error

3. **Content Validation Failures**
   - Low business name match (<60%)
   - Insufficient business content
   - Missing navigation/professional structure

4. **Performance Issues**
   - Response time >10 seconds
   - Multiple retry failures

### Error Recovery

- **Automatic Retries**: Up to 3 attempts with exponential backoff
- **Graceful Degradation**: Continue processing other leads if one fails
- **Detailed Logging**: All validation attempts logged with context
- **Error Reporting**: Failed validations reported in export data

## Performance Considerations

### Optimization Features

- **Concurrent Validation**: Multiple websites validated in parallel (limit: 5)
- **Connection Pooling**: Reuses HTTP connections efficiently
- **Request Caching**: Validation results cached for 24 hours
- **Rate Limiting**: Respects server load and ethical crawling practices

### Monitoring

- Track validation success/failure rates
- Monitor response times and performance
- Alert on high failure rates
- Report validation statistics in exports

## Security and Ethics

### Responsible Web Crawling

- **Respectful User Agent**: Identifies as business validation bot
- **Rate Limiting**: Limits requests to avoid overwhelming servers
- **Robots.txt Compliance**: Respects website crawling preferences (configurable)
- **Minimal Data Collection**: Only collects data necessary for validation

### Data Privacy

- **No Personal Data Storage**: Does not store website content
- **Validation Metadata Only**: Stores only validation results, not content
- **Secure Connections**: Uses HTTPS where available
- **Audit Trail**: Complete validation history maintained

## Testing

### Test Coverage

The system includes comprehensive tests:

- **Unit Tests**: Individual validation components
- **Integration Tests**: Full validation workflow
- **Mock Tests**: Simulated network conditions
- **Error Handling Tests**: Failure scenarios
- **Performance Tests**: Response time and concurrency

### Running Tests

```bash
# Run all website validation tests
python -m pytest tests/test_website_validation.py -v

# Run with coverage
python -m pytest tests/test_website_validation.py --cov=src.services.website_validation_service
```

## Troubleshooting

### Common Issues

1. **High Validation Failure Rate**
   - Check network connectivity
   - Review timeout settings
   - Verify target websites are operational

2. **Low Business Name Matches**
   - Review business name formatting
   - Check website content quality
   - Adjust match threshold if appropriate

3. **Performance Issues**
   - Reduce parallel validation limit
   - Increase timeout settings
   - Check system resource usage

### Debug Mode

Enable detailed validation logging:

```python
import logging
logging.getLogger('src.services.website_validation_service').setLevel(logging.DEBUG)
```

## Best Practices

### Implementation Guidelines

1. **Always Use Async Context Manager**
   ```python
   async with WebsiteValidationService() as validator:
       # Validation code here
   ```

2. **Handle Validation Failures Gracefully**
   ```python
   if not result.is_valid:
       logger.warning(f"Website validation failed: {result.error_message}")
       # Continue processing without website
   ```

3. **Batch Validate for Efficiency**
   ```python
   results = await validator.validate_multiple_websites(website_list)
   ```

4. **Check Verification Before Export**
   ```python
   if contact.is_website_verified():
       export_data['website'] = contact.website
   ```

### Monitoring and Maintenance

- **Regular Performance Reviews**: Monitor validation success rates
- **Website Revalidation**: Periodically revalidate existing entries
- **Configuration Tuning**: Adjust thresholds based on results
- **Error Analysis**: Review and address common failure patterns

---

This website validation system ensures data integrity and prevents the export of fake or non-existent business websites, maintaining the quality and reliability of the lead generation pipeline.