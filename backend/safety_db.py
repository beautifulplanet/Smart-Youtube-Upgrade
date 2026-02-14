"""
Safety Database - Manages danger signatures and categories
Think of this like an antivirus definition database, but for dangerous content
"""

import json
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class SafetyDatabase:
    """
    Manages the safety signature database.
    
    Signatures are patterns that indicate potentially dangerous content.
    Each signature includes:
    - Trigger phrases/patterns
    - Category (fitness, DIY, cooking, etc.)
    - Severity level
    - Warning message
    - Safe alternatives
    """
    
    def __init__(self, db_path: str = None):
        """Initialize and load signatures from db_path (defaults to safety-db/)."""
        if db_path is None:
            # Default to safety-db folder relative to backend
            db_path = Path(__file__).parent.parent / "safety-db"
        
        self.db_path = Path(db_path)
        self.signatures = []
        self.categories = {}
        
        self._load_database()
    
    def _load_database(self) -> None:
        """Load all signatures and categories from JSON files"""
        
        # Load categories
        categories_file = self.db_path / "categories.json"
        if categories_file.exists():
            with open(categories_file, 'r', encoding='utf-8') as f:
                self.categories = json.load(f)
        else:
            # Default categories
            self.categories = self._get_default_categories()
        
        # Load all signature files
        signatures_dir = self.db_path / "signatures"
        if signatures_dir.exists():
            for sig_file in signatures_dir.glob("*.json"):
                try:
                    with open(sig_file, 'r', encoding='utf-8') as f:
                        sigs = json.load(f)
                        if isinstance(sigs, list):
                            self.signatures.extend(sigs)
                        else:
                            self.signatures.append(sigs)
                except Exception as e:
                    logger.error(f"Error loading {sig_file}: {e}")
        
        # If no signatures loaded, use defaults
        if not self.signatures:
            self.signatures = self._get_default_signatures()
    
    def get_all_signatures(self) -> list[dict]:
        """Return all loaded signatures"""
        return self.signatures
    
    def get_signatures_by_category(self, category: str) -> list[dict]:
        """Get signatures for a specific category"""
        return [s for s in self.signatures if s.get('category') == category]
    
    def get_categories(self) -> dict:
        """Return all categories"""
        return self.categories
    
    def get_category_name(self, category_id: str) -> str:
        """Get display name for a category"""
        cat = self.categories.get(category_id, {})
        return cat.get('name', category_id.title())
    
    def add_signature(self, signature: dict) -> bool:
        """Add a new signature to the database"""
        # Validate required fields
        required = ['id', 'category', 'triggers', 'severity', 'warning_message']
        if not all(k in signature for k in required):
            return False
        
        self.signatures.append(signature)
        return True
    
    def _get_default_categories(self) -> dict:
        """Default safety categories"""
        return {
            "fitness": {
                "name": "Fitness",
                "emoji": "🏋️",
                "description": "Exercise and workout safety"
            },
            "diy": {
                "name": "DIY",
                "emoji": "🔧",
                "description": "Do-it-yourself project safety"
            },
            "cooking": {
                "name": "Cooking",
                "emoji": "🍳",
                "description": "Food preparation and kitchen safety"
            },
            "electrical": {
                "name": "Electrical",
                "emoji": "⚡",
                "description": "Electrical work and fire safety"
            },
            "medical": {
                "name": "Medical",
                "emoji": "💊",
                "description": "Health and medical information"
            },
            "chemical": {
                "name": "Chemical",
                "emoji": "🧪",
                "description": "Chemical handling and mixing"
            },
            "automotive": {
                "name": "Automotive",
                "emoji": "🚗",
                "description": "Vehicle repair and maintenance"
            },
            "childcare": {
                "name": "Childcare",
                "emoji": "👶",
                "description": "Child safety and parenting"
            }
        }
    
    def _get_default_signatures(self) -> list[dict]:
        """
        Default danger signatures - these are the "virus definitions"
        for dangerous content patterns.
        """
        return [
            # ============ FITNESS DANGERS ============
            {
                "id": "fitness-001",
                "category": "fitness",
                "severity": "high",
                "triggers": [
                    "lock your knees",
                    "fully extend and lock",
                    "keep knees locked"
                ],
                "exclusions": ["don't lock", "never lock", "avoid locking"],
                "warning_message": "Locking knees during exercises can cause hyperextension injuries and joint damage",
                "safe_alternative": "Keep a slight bend in your knees to protect the joint",
                "source": "ACSM Guidelines"
            },
            {
                "id": "fitness-002",
                "category": "fitness",
                "severity": "high",
                "triggers": [
                    "bounce at the bottom",
                    "use momentum to bounce",
                    "bouncing helps lift more"
                ],
                "warning_message": "Bouncing during lifts can cause muscle tears and joint injuries",
                "safe_alternative": "Use controlled movements with a pause at the bottom",
                "source": "NSCA Strength Training Guidelines"
            },
            {
                "id": "fitness-003",
                "category": "fitness",
                "severity": "high",
                "triggers": [
                    "arch your back as much as possible",
                    "extreme back arch",
                    "hyperextend your spine"
                ],
                "exclusions": ["slight arch", "natural arch", "neutral spine"],
                "warning_message": "Excessive back arching during exercises can cause spinal injuries",
                "safe_alternative": "Maintain a neutral spine with natural curvature",
                "source": "Physical Therapy Guidelines"
            },
            {
                "id": "fitness-004",
                "category": "fitness",
                "severity": "medium",
                "triggers": [
                    "no warm up needed",
                    "skip the warmup",
                    "warming up is a waste"
                ],
                "warning_message": "Skipping warmup increases risk of muscle strains and injuries",
                "safe_alternative": "Always warm up for 5-10 minutes before intense exercise",
                "source": "ACSM Guidelines"
            },
            {
                "id": "fitness-005",
                "category": "fitness",
                "severity": "high",
                "triggers": [
                    "behind the neck press",
                    "behind neck pulldown",
                    "pull behind your head"
                ],
                "warning_message": "Behind-the-neck movements put extreme stress on shoulder joints and rotator cuffs",
                "safe_alternative": "Perform presses and pulldowns in front of the body",
                "source": "NSCA Position Statement"
            },
            
            # ============ DIY DANGERS ============
            {
                "id": "diy-001",
                "category": "diy",
                "severity": "high",
                "triggers": [
                    "galvanized pipe for bbq",
                    "galvanized steel grill",
                    "zinc coated for cooking"
                ],
                "warning_message": "DANGER: Heating galvanized metal releases toxic zinc fumes causing metal fume fever",
                "safe_alternative": "Use food-grade stainless steel or plain steel for cooking surfaces",
                "source": "OSHA Safety Guidelines"
            },
            {
                "id": "diy-002",
                "category": "diy",
                "severity": "high",
                "triggers": [
                    "pvc pipe for compressed air",
                    "pvc air compressor line",
                    "plastic pipe pressurized"
                ],
                "warning_message": "DANGER: PVC can shatter under pressure, sending shrapnel. Never use for compressed air",
                "safe_alternative": "Use copper, steel, or rated air hose for compressed air systems",
                "source": "OSHA Compressed Air Safety"
            },
            {
                "id": "diy-003",
                "category": "diy",
                "severity": "high",
                "triggers": [
                    "aluminum wiring is fine",
                    "connect aluminum to copper directly",
                    "aluminum wire safe"
                ],
                "warning_message": "Improper aluminum wiring connections are a major fire hazard",
                "safe_alternative": "Use proper AL/CU rated connectors or consult a licensed electrician",
                "source": "NEC Electrical Code"
            },
            {
                "id": "diy-004",
                "category": "diy",
                "severity": "medium",
                "triggers": [
                    "pressure treated wood fire",
                    "burn treated lumber",
                    "pressure treated firewood"
                ],
                "warning_message": "Burning pressure-treated wood releases toxic chemicals including arsenic",
                "safe_alternative": "Only burn untreated, natural wood",
                "source": "EPA Guidelines"
            },
            {
                "id": "diy-005",
                "category": "diy",
                "severity": "high",
                "triggers": [
                    "mix concrete in plastic bucket",
                    "5 gallon bucket concrete mixer"
                ],
                "exclusions": ["don't mix", "heavy duty", "mixing rated"],
                "warning_message": "Standard buckets can fail during mixing, causing injury. Concrete is caustic to skin",
                "safe_alternative": "Use a wheelbarrow or concrete mixing tub with proper PPE",
                "source": "Construction Safety Guidelines"
            },
            
            # ============ COOKING DANGERS ============
            {
                "id": "cooking-001",
                "category": "cooking",
                "severity": "high",
                "triggers": [
                    "add water to hot oil",
                    "pour water in grease",
                    "water into frying oil"
                ],
                "exclusions": ["never add water", "don't add water"],
                "warning_message": "DANGER: Water in hot oil causes explosive splattering and severe burns",
                "safe_alternative": "Smother oil fires with a lid or baking soda, never water",
                "source": "Fire Safety Guidelines"
            },
            {
                "id": "cooking-002",
                "category": "cooking",
                "severity": "high",
                "triggers": [
                    "raw chicken safe to taste",
                    "pink chicken is fine",
                    "undercooked poultry ok"
                ],
                "warning_message": "Undercooked chicken can contain Salmonella and Campylobacter",
                "safe_alternative": "Cook chicken to internal temperature of 165°F (74°C)",
                "source": "USDA Food Safety"
            },
            {
                "id": "cooking-003",
                "category": "cooking",
                "severity": "medium",
                "triggers": [
                    "leave rice out overnight",
                    "room temperature rice safe",
                    "rice doesn't need refrigeration"
                ],
                "warning_message": "Cooked rice left at room temperature can grow Bacillus cereus bacteria",
                "safe_alternative": "Refrigerate rice within 1 hour of cooking",
                "source": "FDA Food Safety Guidelines"
            },
            {
                "id": "cooking-004",
                "category": "cooking",
                "severity": "high",
                "triggers": [
                    "thaw meat on counter",
                    "defrost at room temperature",
                    "leave meat out to thaw"
                ],
                "warning_message": "Room temperature thawing allows bacteria to multiply rapidly",
                "safe_alternative": "Thaw in refrigerator, cold water, or microwave",
                "source": "USDA Food Safety"
            },
            
            # ============ ELECTRICAL DANGERS ============
            {
                "id": "electrical-001",
                "category": "electrical",
                "severity": "high",
                "triggers": [
                    "penny in fuse box",
                    "bypass the fuse",
                    "wire around breaker"
                ],
                "warning_message": "DANGER: Bypassing electrical protection causes fires and electrocution",
                "safe_alternative": "Replace fuses with correct amperage, call electrician for breaker issues",
                "source": "NEC Electrical Code"
            },
            {
                "id": "electrical-002",
                "category": "electrical",
                "severity": "high",
                "triggers": [
                    "daisy chain power strips",
                    "extension cord to extension cord",
                    "plug strip into strip"
                ],
                "warning_message": "Daisy-chaining power strips causes overheating and fires",
                "safe_alternative": "Use a single, properly rated power strip or install more outlets",
                "source": "NFPA Fire Safety"
            },
            {
                "id": "electrical-003",
                "category": "electrical",
                "severity": "high",
                "triggers": [
                    "wire gauge doesn't matter",
                    "any wire will work",
                    "use thinner wire to save money"
                ],
                "warning_message": "Undersized wire overheats and causes fires",
                "safe_alternative": "Always use properly rated wire gauge for the amperage",
                "source": "NEC Electrical Code"
            },
            
            # ============ MEDICAL DANGERS ============
            {
                "id": "medical-001",
                "category": "medical",
                "severity": "high",
                "triggers": [
                    "drink bleach to detox",
                    "mms miracle mineral",
                    "chlorine dioxide cure"
                ],
                "warning_message": "DANGER: Ingesting bleach or chlorine dioxide is toxic and potentially fatal",
                "safe_alternative": "Consult a licensed healthcare provider for detox advice",
                "source": "FDA Warning"
            },
            {
                "id": "medical-002",
                "category": "medical",
                "severity": "high",
                "triggers": [
                    "essential oils cure cancer",
                    "oils replace vaccines",
                    "essential oil antibiotic"
                ],
                "warning_message": "Essential oils are not proven treatments for serious diseases",
                "safe_alternative": "Consult healthcare providers for medical treatment",
                "source": "FDA/FTC Guidelines"
            },
            {
                "id": "medical-003",
                "category": "medical",
                "severity": "medium",
                "triggers": [
                    "put butter on burn",
                    "ice directly on burn",
                    "toothpaste on burn"
                ],
                "warning_message": "These burn treatments trap heat and can cause infection",
                "safe_alternative": "Run cool (not cold) water over burn, seek medical help for serious burns",
                "source": "American Red Cross"
            },
            {
                "id": "medical-004",
                "category": "medical",
                "severity": "high",
                "triggers": [
                    "tourniquet for any bleeding",
                    "always use tourniquet",
                    "tie off the limb"
                ],
                "exclusions": ["life-threatening", "arterial", "last resort"],
                "warning_message": "Improper tourniquet use can cause tissue death and amputation",
                "safe_alternative": "Apply direct pressure first, tourniquet only for life-threatening arterial bleeding",
                "source": "Stop the Bleed Guidelines"
            },
            
            # ============ CHEMICAL DANGERS ============
            {
                "id": "chemical-001",
                "category": "chemical",
                "severity": "high",
                "triggers": [
                    "mix bleach and ammonia",
                    "bleach with vinegar",
                    "combine cleaning products"
                ],
                "exclusions": ["never mix", "don't mix", "dangerous to mix"],
                "warning_message": "DANGER: Mixing bleach with ammonia or acids creates toxic chlorine gas",
                "safe_alternative": "Never mix cleaning products, use one at a time with ventilation",
                "source": "CDC Chemical Safety"
            },
            {
                "id": "chemical-002",
                "category": "chemical",
                "severity": "high",
                "triggers": [
                    "add water to acid",
                    "pour water into acid"
                ],
                "exclusions": ["never add water to acid", "add acid to water"],
                "warning_message": "Adding water to concentrated acid causes violent exothermic reaction",
                "safe_alternative": "Always add acid to water slowly, never the reverse",
                "source": "OSHA Chemical Safety"
            },
            
            # ============ CHILDCARE DANGERS ============
            {
                "id": "childcare-001",
                "category": "childcare",
                "severity": "high",
                "triggers": [
                    "baby sleep with blanket",
                    "pillows in crib safe",
                    "bumper pads safe"
                ],
                "warning_message": "Soft bedding in cribs increases SIDS and suffocation risk",
                "safe_alternative": "Bare crib with fitted sheet only, no loose bedding",
                "source": "AAP Safe Sleep Guidelines"
            },
            {
                "id": "childcare-002",
                "category": "childcare",
                "severity": "high",
                "triggers": [
                    "honey for infant",
                    "honey safe for babies",
                    "give baby honey"
                ],
                "exclusions": ["no honey under 1", "avoid honey for infants"],
                "warning_message": "Honey can cause infant botulism in babies under 12 months",
                "safe_alternative": "No honey for children under 1 year old",
                "source": "CDC Infant Botulism Prevention"
            },
            {
                "id": "childcare-003",
                "category": "childcare",
                "severity": "high",
                "triggers": [
                    "forward facing before 2",
                    "turn car seat around early",
                    "forward facing is fine for infant"
                ],
                "warning_message": "Rear-facing car seats provide critical head and neck protection",
                "safe_alternative": "Keep children rear-facing until at least age 2 or max seat weight",
                "source": "AAP Car Seat Guidelines"
            }
        ]
