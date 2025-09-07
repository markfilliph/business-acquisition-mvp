"""
NOC (National Occupational Classification) business classification service.
Maps business names to NOC codes to identify skilled trades that should be excluded.
"""
import sqlite3
import re
from typing import Optional, List, Dict, Any
from pathlib import Path
import structlog

class NOCClassificationService:
    """Maps business names to NOC codes to identify skilled trades."""
    
    def __init__(self, db_path: str = "data/leads.db"):
        self.db_path = db_path
        self.logger = structlog.get_logger(__name__)
        
        # Business name patterns that map to specific NOC codes
        self.business_to_noc_patterns = {
            # Construction Management
            '70010': [
                r'\bconstruction\s+manag', r'\bconstruct\w*\s+manag', r'\bgeneral\s+contract',
                r'\bconstruction\s+compan', r'\bbuilding\s+contract'
            ],
            '70011': [
                r'\bhome\s+build', r'\brenovation\s+manag', r'\bcustom\s+home', 
                r'\bresidential\s+build', r'\bhome\s+renov'
            ],
            '22303': [
                r'\bconstruction\s+estimat', r'\bestimating\s+serv', r'\bquotation\s+serv',
                r'\bcost\s+estimat', r'\bbid\w*\s+serv'
            ],
            
            # Culinary
            '63200': [
                r'\brestaurant', r'\bcatering', r'\bfood\s+serv', r'\bcook\w*\s+serv',
                r'\bchef', r'\bcafe', r'\bdining', r'\bbakery'
            ],
            
            # Metal & Machinery
            '72100': [
                r'\bmachin\w*\s+shop', r'\bmachinist', r'\btool\s+and\s+die', r'\bprecision\s+machin',
                r'\bcnc\s+machin', r'\bmetal\s+machin'
            ],
            '72102': [
                r'\bsheet\s+metal', r'\bmetal\s+fabricat', r'\bduct\s*work', r'\bhvac\s+install',
                r'\bmetal\s+work'
            ],
            
            # Electrical & Mechanical
            '72201': [
                r'\bindustrial\s+electric', r'\belectric\w*\s+contract', r'\belectrical\s+serv',
                r'\belectric\w*\s+install', r'\belectric\w*\s+repair'
            ],
            '72401': [
                r'\bheavy\s+equipment', r'\bequipment\s+repair', r'\bmobile\s+equipment',
                r'\bconstruction\s+equipment', r'\bmining\s+equipment'
            ],
            '72422': [
                r'\bmotor\s+repair', r'\belectric\w*\s+motor', r'\btransformer\s+serv',
                r'\belectrical\s+repair'
            ],
            
            # Construction Trades
            '72302': [
                r'\bgas\s+fitt', r'\bgas\s+line', r'\bgas\s+install', r'\bnatural\s+gas',
                r'\bgas\s+piping'
            ],
            '72311': [
                r'\bcabinet', r'\bmillwork', r'\bcustom\s+wood', r'\bkitchen\s+cabinet',
                r'\bwood\s*work'
            ],
            '72320': [
                r'\bbrick', r'\bmasonry', r'\bstone\s*work', r'\bblock\s*work',
                r'\bbricklayer'
            ],
            
            # Building Finishing
            '73100': [
                r'\bconcrete', r'\bcement', r'\bconcrete\s+finish', r'\bconcrete\s+pour',
                r'\bconcrete\s+work'
            ],
            '73110': [
                r'\broof', r'\bshingle', r'\broofing', r'\broof\s+repair',
                r'\broof\s+install'
            ],
            '73112': [
                r'\bpaint\w*\s+contract', r'\bpainting\s+serv', r'\bdecorat\w*\s+serv',
                r'\bexterior\s+paint', r'\bindustrial\s+paint'
            ],
            '73113': [
                r'\bfloor\w*\s+cover', r'\bcarpet\s+install', r'\btile\s+install',
                r'\bfloor\w*\s+install', r'\bvinyl\s+install'
            ],
            
            # Glass & Window (commonly misclassified)
            '73200': [  # Adding this for glass workers even though removed from official list
                r'\bglass', r'\bglazier', r'\bglazin', r'\bwindow', r'\bmirror',
                r'\bwindow\s+install', r'\bglass\s+install'
            ],
            
            # Services that are often skilled trades
            'SERVICE_TRADES': [
                r'\bplumb', r'\belectric', r'\bhvac', r'\brepair\s+serv', 
                r'\bmaintenance\s+serv', r'\binstallation\s+serv', r'\bhandyman',
                r'\bhome\s+serv', r'\bcontractor', r'\bspecialist\s+serv'
            ]
        }
    
    def classify_business_noc(self, business_name: str) -> Optional[str]:
        """
        Classify a business name to determine if it matches a skilled trades NOC.
        Returns NOC code if skilled trade, None otherwise.
        """
        if not business_name:
            return None
            
        name_lower = business_name.lower()
        
        # Check each NOC pattern
        for noc_code, patterns in self.business_to_noc_patterns.items():
            for pattern in patterns:
                if re.search(pattern, name_lower):
                    self.logger.info(
                        "noc_classification_matched",
                        business_name=business_name,
                        noc_code=noc_code,
                        pattern=pattern
                    )
                    return noc_code
        
        return None
    
    def get_noc_details(self, noc_code: str) -> Optional[Dict[str, Any]]:
        """Get NOC code details from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT noc_code, title, category, description FROM skilled_trades_noc WHERE noc_code = ?",
                    (noc_code,)
                )
                row = cursor.fetchone()
                
                if row:
                    return {
                        'noc_code': row[0],
                        'title': row[1], 
                        'category': row[2],
                        'description': row[3]
                    }
                return None
                
        except Exception as e:
            self.logger.error("noc_lookup_error", noc_code=noc_code, error=str(e))
            return None
    
    def is_skilled_trade_by_noc(self, business_name: str) -> tuple[bool, Optional[Dict[str, Any]]]:
        """
        Determine if business is a skilled trade based on NOC classification.
        Returns (is_skilled_trade, noc_details).
        """
        noc_code = self.classify_business_noc(business_name)
        if not noc_code:
            return False, None
        
        # Don't return service trades as they're too broad
        if noc_code == 'SERVICE_TRADES':
            return True, {'noc_code': 'SERVICE_TRADES', 'title': 'General Service Trade', 'category': 'Service', 'description': 'General service-based business'}
        
        noc_details = self.get_noc_details(noc_code)
        if noc_details:
            return True, noc_details
            
        return False, None
    
    def get_all_skilled_trades_noc(self) -> List[Dict[str, Any]]:
        """Get all skilled trades NOC codes from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT noc_code, title, category, description FROM skilled_trades_noc ORDER BY noc_code")
                rows = cursor.fetchall()
                
                return [
                    {
                        'noc_code': row[0],
                        'title': row[1],
                        'category': row[2], 
                        'description': row[3]
                    }
                    for row in rows
                ]
                
        except Exception as e:
            self.logger.error("noc_list_error", error=str(e))
            return []