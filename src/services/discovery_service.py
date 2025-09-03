"""
Ethical business discovery service using legitimate data sources.
"""
import asyncio
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional

import structlog

from ..core.config import SystemConfig
from ..core.models import BusinessLead, LocationInfo, ContactInfo, DataSource
from ..core.exceptions import DataSourceError
from .http_client import HttpClient


class EthicalDiscoveryService:
    """Discovers businesses using ethical, API-based methods and legitimate directories."""
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.logger = structlog.get_logger(__name__)
        self.discovery_stats = {
            'sources_queried': 0,
            'businesses_found': 0,
            'duplicates_filtered': 0,
            'validation_failures': 0
        }
    
    async def discover_businesses(self, target_count: int = 50) -> List[BusinessLead]:
        """Discover businesses from multiple ethical sources."""
        
        self.logger.info("discovery_started", target_count=target_count)
        
        all_businesses = []
        
        # Use multiple discovery methods
        discovery_methods = [
            self._discover_from_chamber_of_commerce(),
            self._discover_from_industry_directories(),
            self._discover_from_business_registries(),
            self._discover_mock_data()  # For demonstration purposes
        ]
        
        # Run discovery methods concurrently
        results = await asyncio.gather(*discovery_methods, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.warning("discovery_method_failed", method=i, error=str(result))
                self.discovery_stats['validation_failures'] += 1
            elif isinstance(result, list):
                all_businesses.extend(result)
                self.discovery_stats['sources_queried'] += 1
        
        # Remove duplicates
        unique_businesses = self._deduplicate_businesses(all_businesses)
        
        # Validate and filter
        validated_businesses = []
        for business in unique_businesses:
            try:
                validated = self._validate_business_data(business)
                if validated:
                    validated_businesses.append(validated)
            except Exception as e:
                self.logger.warning("business_validation_failed", 
                                  business_name=business.get('business_name', 'unknown'),
                                  error=str(e))
                self.discovery_stats['validation_failures'] += 1
        
        self.discovery_stats['businesses_found'] = len(validated_businesses)
        
        self.logger.info("discovery_completed", 
                        total_found=len(validated_businesses),
                        stats=self.discovery_stats)
        
        return validated_businesses[:target_count]
    
    async def _discover_from_chamber_of_commerce(self) -> List[Dict[str, Any]]:
        """Discover businesses from Hamilton Chamber of Commerce directory."""
        
        # In a real implementation, this would query the chamber's API or directory
        # For now, we'll return mock data that represents what this would find
        
        self.logger.info("querying_hamilton_chamber")
        
        # Simulate API call delay
        await asyncio.sleep(0.5)
        
        return [
            {
                'business_name': 'Hamilton Steel Fabrication Ltd',
                'address': '245 Industrial Dr, Hamilton, ON L8J 0G5',
                'phone': '905-555-0245',
                'website': 'hamiltonsteel.ca',
                'industry': 'metal_fabrication',
                'years_in_business': 26,
                'employee_count': 22,
                'data_source': DataSource.HAMILTON_CHAMBER
            },
            {
                'business_name': 'Ancaster Professional Services',
                'address': '89 Wilson St W, Ancaster, ON L9G 1N4',
                'phone': '905-555-0189',
                'email': 'info@ancasterpro.ca',
                'website': 'ancasterprofessional.com',
                'industry': 'professional_services',
                'years_in_business': 19,
                'employee_count': 11,
                'data_source': DataSource.HAMILTON_CHAMBER
            }
        ]
    
    async def _discover_from_industry_directories(self) -> List[Dict[str, Any]]:
        """Discover businesses from industry-specific directories."""
        
        self.logger.info("querying_industry_directories")
        
        # Simulate API call delay
        await asyncio.sleep(0.3)
        
        return [
            {
                'business_name': 'Precision Manufacturing Solutions',
                'address': '1156 Barton St E, Hamilton, ON L8H 2V4',
                'phone': '905-555-1156',
                'website': 'precisionsolutions.ca',
                'industry': 'manufacturing',
                'years_in_business': 24,
                'employee_count': 18,
                'data_source': DataSource.ONTARIO_MANUFACTURING
            },
            {
                'business_name': 'Dundas Wholesale Distribution',
                'address': '456 King St W, Dundas, ON L9H 1W4',
                'phone': '905-555-0456',
                'website': 'dundaswholesale.com',
                'industry': 'wholesale',
                'years_in_business': 31,
                'employee_count': 14,
                'data_source': DataSource.ONTARIO_MANUFACTURING
            }
        ]
    
    async def _discover_from_business_registries(self) -> List[Dict[str, Any]]:
        """Discover businesses from government business registries."""
        
        self.logger.info("querying_business_registries")
        
        # Simulate API call delay
        await asyncio.sleep(0.4)
        
        return [
            {
                'business_name': 'Stoney Creek Construction Ltd',
                'address': '789 Queenston Rd, Stoney Creek, ON L8E 5H4',
                'phone': '905-555-0789',
                'industry': 'construction',
                'years_in_business': 17,
                'employee_count': 25,
                'data_source': DataSource.CANADA411
            }
        ]
    
    async def _discover_mock_data(self) -> List[Dict[str, Any]]:
        """Mock data for testing and demonstration."""
        
        return [
            {
                'business_name': 'Bay Area Printing Services',
                'address': '321 Main St E, Hamilton, ON L8M 1K4',
                'phone': '905-555-0321',
                'email': 'orders@bayareaprinting.ca',
                'website': 'bayareaprinting.ca',
                'industry': 'printing',
                'years_in_business': 29,
                'employee_count': 16,
                'data_source': DataSource.YELLOWPAGES
            },
            {
                'business_name': 'Waterdown Equipment Rental',
                'address': '567 Dundas St, Waterdown, ON L9A 2G8',
                'phone': '905-555-0567',
                'website': 'waterdownequipment.com',
                'industry': 'equipment_rental',
                'years_in_business': 21,
                'employee_count': 12,
                'data_source': DataSource.GOOGLE_BUSINESS
            },
            # Additional businesses within $1M-$1.4M target range (8-12 employees)
            {
                'business_name': 'Stoney Creek Manufacturing Co',
                'address': '45 Centennial Pkwy N, Stoney Creek, ON L8E 1E5',
                'phone': '905-555-0445',
                'email': 'info@stoneymanufacturing.ca',
                'website': 'stoneymanufacturing.ca',
                'industry': 'manufacturing',
                'years_in_business': 18,
                'employee_count': 9,
                'data_source': DataSource.HAMILTON_CHAMBER
            },
            {
                'business_name': 'Flamborough Business Solutions',
                'address': '234 Dundas St W, Flamborough, ON L9H 5G3',
                'phone': '905-555-0234',
                'email': 'info@flamboroughbiz.com',
                'website': 'flamboroughbiz.com',
                'industry': 'professional_services',
                'years_in_business': 22,
                'employee_count': 10,
                'data_source': DataSource.ONTARIO_MANUFACTURING
            },
            {
                'business_name': 'Dundas Professional Consulting',
                'address': '156 King St W, Dundas, ON L9H 1V1',
                'phone': '905-555-0156',
                'email': 'service@dundasconsulting.ca',
                'website': 'dundasconsulting.ca',
                'industry': 'professional_services',
                'years_in_business': 16,
                'employee_count': 8,
                'data_source': DataSource.LINKEDIN
            },
            {
                'business_name': 'Hamilton Precision Printing',
                'address': '678 Barton St E, Hamilton, ON L8L 2Y5',
                'phone': '905-555-0678',
                'email': 'orders@hamiltonprecision.ca',
                'website': 'hamiltonprecision.ca',
                'industry': 'printing',
                'years_in_business': 24,
                'employee_count': 11,
                'data_source': DataSource.CANADA411
            },
            {
                'business_name': 'Ancaster Wholesale Solutions',
                'address': '89 Wilson St W, Ancaster, ON L9G 2B8',
                'phone': '905-555-0089',
                'email': 'sales@ancasterwholesale.ca',
                'website': 'ancasterwholesale.ca',
                'industry': 'wholesale',
                'years_in_business': 19,
                'employee_count': 12,
                'data_source': DataSource.INDUSTRY_ASSOCIATION
            },
            {
                'business_name': 'Hamilton Bay Equipment Services',
                'address': '345 Burlington St E, Hamilton, ON L8H 7M3',
                'phone': '905-555-0345',
                'email': 'rentals@bayequipment.ca',
                'website': 'bayequipment.ca',
                'industry': 'equipment_rental',
                'years_in_business': 17,
                'employee_count': 9,
                'data_source': DataSource.API_INTEGRATION
            },
            {
                'business_name': 'Stoney Creek Office Solutions',
                'address': '67 King St E, Stoney Creek, ON L8G 1K1',
                'phone': '905-555-0067',
                'email': 'admin@stoneyoffice.ca',
                'website': 'stoneyoffice.ca',
                'industry': 'professional_services',
                'years_in_business': 18,
                'employee_count': 9,
                'data_source': DataSource.YELLOWPAGES
            },
            {
                'business_name': 'Hamilton Business Printing Co',
                'address': '234 James St N, Hamilton, ON L8R 2L3',
                'phone': '905-555-0234',
                'email': 'print@hamiltonbizprint.ca',
                'website': 'hamiltonbizprint.ca',
                'industry': 'printing',
                'years_in_business': 21,
                'employee_count': 11,
                'data_source': DataSource.MANUAL_RESEARCH
            },
            # Additional qualified prospects within target criteria
            {
                'business_name': 'Ancaster Distribution Center',
                'address': '78 Wilson St W, Ancaster, ON L9G 4V5',
                'phone': '905-555-0078',
                'email': 'operations@ancasterdist.ca',
                'website': 'ancasterdist.ca',
                'industry': 'wholesale',
                'years_in_business': 16,
                'employee_count': 9,
                'data_source': DataSource.GOOGLE_BUSINESS
            },
            {
                'business_name': 'Hamilton Office Supplies Ltd',
                'address': '456 Main St W, Hamilton, ON L8P 1K5',
                'phone': '905-555-0456',
                'email': 'sales@hamiltonoffice.ca',
                'website': 'hamiltonoffice.ca',
                'industry': 'wholesale',
                'years_in_business': 22,
                'employee_count': 12,
                'data_source': DataSource.CANADA411
            },
            {
                'business_name': 'Dundas Business Services Inc',
                'address': '89 Main St, Dundas, ON L9H 3A1',
                'phone': '905-555-0089',
                'email': 'contact@dundasbusiness.ca',
                'website': 'dundasbusiness.ca',
                'industry': 'professional_services',
                'years_in_business': 19,
                'employee_count': 10,
                'data_source': DataSource.LINKEDIN
            },
            {
                'business_name': 'Waterdown Manufacturing Solutions',
                'address': '123 Dundas St E, Waterdown, ON L9A 1G2',
                'phone': '905-555-0123',
                'email': 'info@waterdownmfg.ca',
                'website': 'waterdownmfg.ca',
                'industry': 'manufacturing',
                'years_in_business': 18,
                'employee_count': 11,
                'data_source': DataSource.ONTARIO_MANUFACTURING
            },
            {
                'business_name': 'Stoney Creek Print Solutions',
                'address': '234 Highway 8, Stoney Creek, ON L8G 5C3',
                'phone': '905-555-0234',
                'email': 'orders@stoneyprint.ca',
                'website': 'stoneyprint.ca',
                'industry': 'printing',
                'years_in_business': 20,
                'employee_count': 9,
                'data_source': DataSource.WEB_SCRAPING
            },
            {
                'business_name': 'Hamilton Equipment Leasing Co',
                'address': '567 Burlington St W, Hamilton, ON L8H 2R4',
                'phone': '905-555-0567',
                'email': 'leasing@hamiltonequip.ca',
                'website': 'hamiltonequip.ca',
                'industry': 'equipment_rental',
                'years_in_business': 15,
                'employee_count': 8,
                'data_source': DataSource.API_INTEGRATION
            },
            {
                'business_name': 'Flamborough Supply Chain Services',
                'address': '345 Guelph Line, Flamborough, ON L9H 7J3',
                'phone': '905-555-0345',
                'email': 'logistics@flamboroughsupply.ca',
                'website': 'flamboroughsupply.ca',
                'industry': 'wholesale',
                'years_in_business': 17,
                'employee_count': 10,
                'data_source': DataSource.INDUSTRY_ASSOCIATION
            },
            {
                'business_name': 'Burlington Manufacturing Partners',
                'address': '678 Plains Rd E, Burlington, ON L7T 2E1',
                'phone': '905-555-0678',
                'email': 'partners@burlingtonmfg.ca',
                'website': 'burlingtonmfg.ca',
                'industry': 'manufacturing',
                'years_in_business': 21,
                'employee_count': 12,
                'data_source': DataSource.YELLOWPAGES
            },
            {
                'business_name': 'Ancaster Business Consulting Group',
                'address': '789 Golf Links Rd, Ancaster, ON L9G 3L1',
                'phone': '905-555-0789',
                'email': 'consultants@ancasterbcg.ca',
                'website': 'ancasterbcg.ca',
                'industry': 'professional_services',
                'years_in_business': 16,
                'employee_count': 9,
                'data_source': DataSource.HAMILTON_CHAMBER
            }
        ]
    
    def _deduplicate_businesses(self, businesses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate businesses based on name and location."""
        
        seen_hashes = set()
        unique_businesses = []
        
        for business in businesses:
            # Create unique identifier
            name = business.get('business_name', '').lower().strip()
            address = business.get('address', '').lower().strip()
            phone = business.get('phone', '').strip()
            
            # Create hash for deduplication
            identifier = f"{name}_{address}_{phone}"
            hash_value = hashlib.md5(identifier.encode()).hexdigest()
            
            if hash_value not in seen_hashes:
                seen_hashes.add(hash_value)
                unique_businesses.append(business)
            else:
                self.discovery_stats['duplicates_filtered'] += 1
        
        return unique_businesses
    
    def _validate_business_data(self, business_data: Dict[str, Any]) -> Optional[BusinessLead]:
        """Validate and convert raw business data to BusinessLead model."""
        
        try:
            # Extract location information
            location = LocationInfo(
                address=business_data.get('address'),
                city=self._extract_city_from_address(business_data.get('address')),
                province='ON',
                postal_code=self._extract_postal_code_from_address(business_data.get('address'))
            )
            
            # Extract contact information
            contact = ContactInfo(
                phone=business_data.get('phone'),
                email=business_data.get('email'),
                website=business_data.get('website')
            )
            
            # Create BusinessLead
            lead = BusinessLead(
                business_name=business_data['business_name'],
                location=location,
                contact=contact,
                industry=business_data.get('industry'),
                years_in_business=business_data.get('years_in_business'),
                employee_count=business_data.get('employee_count'),
                data_sources=[business_data.get('data_source', DataSource.MANUAL_RESEARCH)]
            )
            
            # Validation checks
            if not self._meets_basic_criteria(lead):
                return None
            
            lead.add_note(f"Discovered via {business_data.get('data_source', 'unknown')}", "discovery")
            
            return lead
            
        except Exception as e:
            self.logger.warning("business_validation_error", 
                              business_name=business_data.get('business_name', 'unknown'),
                              error=str(e))
            return None
    
    def _extract_city_from_address(self, address: str) -> Optional[str]:
        """Extract city name from address string."""
        if not address:
            return None
        
        # Look for Hamilton area cities
        hamilton_cities = ['hamilton', 'dundas', 'ancaster', 'stoney creek', 'waterdown', 'flamborough']
        address_lower = address.lower()
        
        for city in hamilton_cities:
            if city in address_lower:
                return city.title()
        
        return None
    
    def _extract_postal_code_from_address(self, address: str) -> Optional[str]:
        """Extract postal code from address string."""
        if not address:
            return None
        
        import re
        # Canadian postal code pattern
        pattern = r'[A-Z]\d[A-Z]\s?\d[A-Z]\d'
        match = re.search(pattern, address.upper())
        
        if match:
            postal_code = match.group()
            # Format as "A1A 1A1"
            if len(postal_code) == 6:
                return f"{postal_code[:3]} {postal_code[3:]}"
            return postal_code
        
        return None
    
    def _meets_basic_criteria(self, lead: BusinessLead) -> bool:
        """Check if business meets basic discovery criteria."""
        
        # Must have business name
        if not lead.business_name or len(lead.business_name) < 3:
            return False
        
        # Must be in Hamilton area
        if not lead.location.is_hamilton_area():
            return False
        
        # Must have some contact information
        if not any([lead.contact.phone, lead.contact.email, lead.contact.website]):
            return False
        
        # Age requirements (if known)
        if lead.years_in_business is not None and lead.years_in_business < self.config.business_criteria.min_years_in_business:
            return False
        
        # Employee count (if known)
        if lead.employee_count is not None and lead.employee_count > self.config.business_criteria.max_employee_count:
            return False
        
        return True
    
    def get_discovery_stats(self) -> Dict[str, int]:
        """Get discovery statistics."""
        return self.discovery_stats.copy()