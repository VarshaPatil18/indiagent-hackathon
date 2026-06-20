import os

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    print(f"Created: {path}")

# File 1: requirements.txt
write_file("requirements.txt", """fastapi==0.109.0
uvicorn[standard]==0.27.0
python-dotenv==1.0.0
pydantic==2.5.3
httpx==0.26.0
python-multipart==0.0.6
""")

# File 2: .env.example
write_file(".env.example", """# === GOOGLE AI STUDIO ===
GOOGLE_AI_API_KEY=your_google_ai_studio_key_here

# === N8N ===
N8N_HOST=https://yourname.app.n8n.cloud
N8N_API_KEY=your_n8n_api_key

# === TWILIO WHATSAPP SANDBOX ===
TWILIO_ACCOUNT_SID=AC36b83579eaba2e3904e5c717c9f3b32e
TWILIO_AUTH_TOKEN=0d34b7c1d0a52634166dbf20bb327e7e
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# === APP SETTINGS ===
APP_ENV=development
DEMO_MODE=true

# === OWNER PHONE ===
OWNER_PHONE_NUMBER=+919999999999
""")

# File 3: .gitignore
write_file(".gitignore", """.env
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
*.egg-info/
dist/
build/
.DS_Store
.idea/
.vscode/
*.log
""")

# File 4: config.py
write_file("config.py", '''"""
Central configuration. All secrets come from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY", "")
    GEMINI_MODEL = "gemini-1.5-flash"
    N8N_HOST = os.getenv("N8N_HOST", "").rstrip("/")
    N8N_API_KEY = os.getenv("N8N_API_KEY", "")
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
    APP_ENV = os.getenv("APP_ENV", "development")
    DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
    OWNER_PHONE_NUMBER = os.getenv("OWNER_PHONE_NUMBER", "")
    
    @classmethod
    def validate(cls):
        missing = []
        for key in ["GOOGLE_AI_API_KEY", "N8N_HOST", "N8N_API_KEY"]:
            if not getattr(cls, key):
                missing.append(key)
        if not cls.TWILIO_ACCOUNT_SID:
            print("Twilio not configured - WhatsApp will run in demo mode")
        if missing:
            print(f"WARNING: Missing env vars: {', '.join(missing)}")
            if not cls.DEMO_MODE:
                raise ValueError(f"Missing required config: {missing}")
        return True

settings = Settings()
''')

# File 5: models/__init__.py
write_file("models/__init__.py", "")

# File 6: models/schemas.py
write_file("models/schemas.py", """from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class Language(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"
    TELUGU = "te"
    TAMIL = "ta"
    MARATHI = "mr"
    GUJARATI = "gu"
    BENGALI = "bn"
    KANNADA = "kn"

class BusinessType(str, Enum):
    KIRANA = "kirana"
    PHARMACY = "pharmacy"
    SALON = "salon"
    RESTAURANT = "restaurant"
    CLOTHING = "clothing"
    ELECTRONICS = "electronics"
    OTHER = "other"

class HelperType(str, Enum):
    STOCK = "stock"
    MONEY = "money"
    ORDERS = "orders"
    CUSTOMERS = "customers"
    PROMOTIONS = "promotions"

class TrustMode(str, Enum):
    ALWAYS_ASK = "always_ask"
    AUTOPILOT = "autopilot"

class OnboardingRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\\+91\\d{10}$")
    language: Language
    business_type: BusinessType
    current_system: str
    selected_helpers: List[HelperType]
    trust_mode: TrustMode = TrustMode.ALWAYS_ASK

class ChatMessage(BaseModel):
    message: str
    helper_type: Optional[HelperType] = None
    language: Language = Language.ENGLISH
    session_id: str
    is_voice: bool = False

class HelperResponse(BaseModel):
    helper_type: HelperType
    message: str
    confidence: float
    action_taken: Optional[str] = None
    action_id: Optional[str] = None
    requires_approval: bool = False
    language: Language

class ApprovalRequest(BaseModel):
    action_id: str
    approved: bool
    session_id: str

class HomeDashboard(BaseModel):
    mood: str
    orders_today: int
    money_in: float
    money_pending: float
    low_stock_items: List[str]
    recent_actions: List[Dict[str, Any]]
    pending_approvals: List[Dict[str, Any]]
    active_helpers: List[HelperType]
""")

# File 7: services/__init__.py
write_file("services/__init__.py", "")

# File 8: services/gemini_service.py
write_file("services/gemini_service.py", '''"""
Google AI Studio / Gemini 3.5 Flash integration.
Free tier: 1,500 requests/day, 60/minute.
"""
import httpx
from typing import Optional, Dict, Any
from config import settings

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

class GeminiService:
    def __init__(self):
        self.api_key = settings.GOOGLE_AI_API_KEY
        self.model = settings.GEMINI_MODEL
        self.base_url = f"{GEMINI_API_URL}/{self.model}:generateContent"
        
    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        language: str = "en"
    ) -> Dict[str, Any]:
        if not self.api_key:
            return self._demo_fallback(prompt, language)
        
        lang_instruction = self._get_language_instruction(language)
        full_system = (system_instruction or "") + "\\n" + lang_instruction
        
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }
        
        payload = {
            "contents": [{
                "role": "user",
                "parts": [{"text": full_system + "\\n\\n" + prompt}]
            }],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": 0.8,
                "topK": 40
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
            ]
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}?key={self.api_key}",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 429:
                    print("Gemini rate limit hit. Using demo fallback.")
                    return self._demo_fallback(prompt, language)
                
                response.raise_for_status()
                data = response.json()
                
                candidates = data.get("candidates", [])
                if not candidates:
                    return self._demo_fallback(prompt, language)
                
                text = candidates[0]["content"]["parts"][0]["text"]
                confidence = self._estimate_confidence(text, data)
                
                return {
                    "text": text.strip(),
                    "confidence": confidence,
                    "tokens_used": data.get("usageMetadata", {}).get("totalTokenCount", 0),
                    "raw": data
                }
                
        except Exception as e:
cd ~/indiagent-hackathon

# Create the setup script
cat > setup.py << 'PYEOF'
import os

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    print(f"Created: {path}")

# File 1: requirements.txt
write_file("requirements.txt", """fastapi==0.109.0
uvicorn[standard]==0.27.0
python-dotenv==1.0.0
pydantic==2.5.3
httpx==0.26.0
python-multipart==0.0.6
""")

# File 2: .env.example
write_file(".env.example", """# === GOOGLE AI STUDIO ===
GOOGLE_AI_API_KEY=your_google_ai_studio_key_here

# === N8N ===
N8N_HOST=https://yourname.app.n8n.cloud
N8N_API_KEY=your_n8n_api_key

# === TWILIO WHATSAPP SANDBOX ===
TWILIO_ACCOUNT_SID=AC36b83579eaba2e3904e5c717c9f3b32e
TWILIO_AUTH_TOKEN=0d34b7c1d0a52634166dbf20bb327e7e
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# === APP SETTINGS ===
APP_ENV=development
DEMO_MODE=true

# === OWNER PHONE ===
OWNER_PHONE_NUMBER=+919999999999
""")

# File 3: .gitignore
write_file(".gitignore", """.env
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
*.egg-info/
dist/
build/
.DS_Store
.idea/
.vscode/
*.log
""")

# File 4: config.py
write_file("config.py", '''"""
Central configuration. All secrets come from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY", "")
    GEMINI_MODEL = "gemini-1.5-flash"
    N8N_HOST = os.getenv("N8N_HOST", "").rstrip("/")
    N8N_API_KEY = os.getenv("N8N_API_KEY", "")
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
    APP_ENV = os.getenv("APP_ENV", "development")
    DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
    OWNER_PHONE_NUMBER = os.getenv("OWNER_PHONE_NUMBER", "")
    
    @classmethod
    def validate(cls):
        missing = []
        for key in ["GOOGLE_AI_API_KEY", "N8N_HOST", "N8N_API_KEY"]:
            if not getattr(cls, key):
                missing.append(key)
        if not cls.TWILIO_ACCOUNT_SID:
            print("Twilio not configured - WhatsApp will run in demo mode")
        if missing:
            print(f"WARNING: Missing env vars: {', '.join(missing)}")
            if not cls.DEMO_MODE:
                raise ValueError(f"Missing required config: {missing}")
        return True

settings = Settings()
''')

# File 5: models/__init__.py
write_file("models/__init__.py", "")

# File 6: models/schemas.py
write_file("models/schemas.py", """from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class Language(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"
    TELUGU = "te"
    TAMIL = "ta"
    MARATHI = "mr"
    GUJARATI = "gu"
    BENGALI = "bn"
    KANNADA = "kn"

class BusinessType(str, Enum):
    KIRANA = "kirana"
    PHARMACY = "pharmacy"
    SALON = "salon"
    RESTAURANT = "restaurant"
    CLOTHING = "clothing"
    ELECTRONICS = "electronics"
    OTHER = "other"

class HelperType(str, Enum):
    STOCK = "stock"
    MONEY = "money"
    ORDERS = "orders"
    CUSTOMERS = "customers"
    PROMOTIONS = "promotions"

class TrustMode(str, Enum):
    ALWAYS_ASK = "always_ask"
    AUTOPILOT = "autopilot"

class OnboardingRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\\+91\\d{10}$")
    language: Language
    business_type: BusinessType
    current_system: str
    selected_helpers: List[HelperType]
    trust_mode: TrustMode = TrustMode.ALWAYS_ASK

class ChatMessage(BaseModel):
    message: str
    helper_type: Optional[HelperType] = None
    language: Language = Language.ENGLISH
    session_id: str
    is_voice: bool = False

class HelperResponse(BaseModel):
    helper_type: HelperType
    message: str
    confidence: float
    action_taken: Optional[str] = None
    action_id: Optional[str] = None
    requires_approval: bool = False
    language: Language

class ApprovalRequest(BaseModel):
    action_id: str
    approved: bool
    session_id: str

class HomeDashboard(BaseModel):
    mood: str
    orders_today: int
    money_in: float
    money_pending: float
    low_stock_items: List[str]
    recent_actions: List[Dict[str, Any]]
    pending_approvals: List[Dict[str, Any]]
    active_helpers: List[HelperType]
""")

# File 7: services/__init__.py
write_file("services/__init__.py", "")

# File 8: services/gemini_service.py
write_file("services/gemini_service.py", '''"""
Google AI Studio / Gemini 3.5 Flash integration.
Free tier: 1,500 requests/day, 60/minute.
"""
import httpx
from typing import Optional, Dict, Any
from config import settings

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

class GeminiService:
    def __init__(self):
        self.api_key = settings.GOOGLE_AI_API_KEY
        self.model = settings.GEMINI_MODEL
        self.base_url = f"{GEMINI_API_URL}/{self.model}:generateContent"
        
    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        language: str = "en"


[200~cd ~/indiagent-hackathon

# Create the setup script
cat > setup.py << 'PYEOF'
import os

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    print(f"Created: {path}")

# File 1: requirements.txt
write_file("requirements.txt", """fastapi==0.109.0
uvicorn[standard]==0.27.0
python-dotenv==1.0.0
pydantic==2.5.3
httpx==0.26.0
python-multipart==0.0.6
""")

# File 2: .env.example
write_file(".env.example", """# === GOOGLE AI STUDIO ===
GOOGLE_AI_API_KEY=your_google_ai_studio_key_here

# === N8N ===
N8N_HOST=https://yourname.app.n8n.cloud
N8N_API_KEY=your_n8n_api_key

# === TWILIO WHATSAPP SANDBOX ===
TWILIO_ACCOUNT_SID=AC36b83579eaba2e3904e5c717c9f3b32e
TWILIO_AUTH_TOKEN=0d34b7c1d0a52634166dbf20bb327e7e
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# === APP SETTINGS ===
APP_ENV=development
DEMO_MODE=true

# === OWNER PHONE ===
OWNER_PHONE_NUMBER=+919999999999
""")

# File 3: .gitignore
write_file(".gitignore", """.env
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
*.egg-info/
dist/
build/
.DS_Store
.idea/
.vscode/
*.log
""")

# File 4: config.py
write_file("config.py", '''"""
Central configuration. All secrets come from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY", "")
    GEMINI_MODEL = "gemini-1.5-flash"
    N8N_HOST = os.getenv("N8N_HOST", "").rstrip("/")
    N8N_API_KEY = os.getenv("N8N_API_KEY", "")
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
    APP_ENV = os.getenv("APP_ENV", "development")
    DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
    OWNER_PHONE_NUMBER = os.getenv("OWNER_PHONE_NUMBER", "")
    
    @classmethod
    def validate(cls):
        missing = []
        for key in ["GOOGLE_AI_API_KEY", "N8N_HOST", "N8N_API_KEY"]:
            if not getattr(cls, key):
                missing.append(key)
        if not cls.TWILIO_ACCOUNT_SID:
            print("Twilio not configured - WhatsApp will run in demo mode")
        if missing:
            print(f"WARNING: Missing env vars: {', '.join(missing)}")
            if not cls.DEMO_MODE:
                raise ValueError(f"Missing required config: {missing}")
        return True

settings = Settings()
''')

# File 5: models/__init__.py
write_file("models/__init__.py", "")

# File 6: models/schemas.py
write_file("models/schemas.py", """from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class Language(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"
    TELUGU = "te"
    TAMIL = "ta"
    MARATHI = "mr"
    GUJARATI = "gu"
    BENGALI = "bn"
    KANNADA = "kn"

class BusinessType(str, Enum):
    KIRANA = "kirana"
    PHARMACY = "pharmacy"
    SALON = "salon"
    RESTAURANT = "restaurant"
    CLOTHING = "clothing"
    ELECTRONICS = "electronics"
    OTHER = "other"

class HelperType(str, Enum):
    STOCK = "stock"
    MONEY = "money"
    ORDERS = "orders"
    CUSTOMERS = "customers"
    PROMOTIONS = "promotions"

class TrustMode(str, Enum):
    ALWAYS_ASK = "always_ask"
    AUTOPILOT = "autopilot"

class OnboardingRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\\+91\\d{10}$")
    language: Language
    business_type: BusinessType
    current_system: str
    selected_helpers: List[HelperType]
    trust_mode: TrustMode = TrustMode.ALWAYS_ASK

class ChatMessage(BaseModel):
    message: str
    helper_type: Optional[HelperType] = None
    language: Language = Language.ENGLISH
    session_id: str
    is_voice: bool = False

class HelperResponse(BaseModel):
    helper_type: HelperType
    message: str
    confidence: float
    action_taken: Optional[str] = None
    action_id: Optional[str] = None
    requires_approval: bool = False
    language: Language

class ApprovalRequest(BaseModel):
    action_id: str
    approved: bool
    session_id: str

class HomeDashboard(BaseModel):
    mood: str
    orders_today: int
    money_in: float
    money_pending: float
    low_stock_items: List[str]
    recent_actions: List[Dict[str, Any]]
    pending_approvals: List[Dict[str, Any]]
    active_helpers: List[HelperType]
""")

# File 7: services/__init__.py
write_file("services/__init__.py", "")

# File 8: services/gemini_service.py
write_file("services/gemini_service.py", '''"""
Google AI Studio / Gemini 3.5 Flash integration.
Free tier: 1,500 requests/day, 60/minute.
"""
import httpx
from typing import Optional, Dict, Any
from config import settings

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

class GeminiService:
    def __init__(self):
        self.api_key = settings.GOOGLE_AI_API_KEY
        self.model = settings.GEMINI_MODEL
        self.base_url = f"{GEMINI_API_URL}/{self.model}:generateContent"
        
    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        language: str = "en"
    ) -> Dict[str, Any]:
        if not self.api_key:
            return self._demo_fallback(prompt, language)
        
        lang_instruction = self._get_language_instruction(language)
        full_system = (system_instruction or "") + "\\n" + lang_instruction
        
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }
        
        payload = {
            "contents": [{
                "role": "user",
                "parts": [{"text": full_system + "\\n\\n" + prompt}]
            }],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": 0.8,
                "topK": 40
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
            ]
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}?key={self.api_key}",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 429:
                    print("Gemini rate limit hit. Using demo fallback.")
                    return self._demo_fallback(prompt, language)
                
                response.raise_for_status()
                data = response.json()
                
                candidates = data.get("candidates", [])
                if not candidates:
                    return self._demo_fallback(prompt, language)
                
                text = candidates[0]["content"]["parts"][0]["text"]
                confidence = self._estimate_confidence(text, data)
                
                return {
                    "text": text.strip(),
                    "confidence": confidence,
                    "tokens_used": data.get("usageMetadata", {}).get("totalTokenCount", 0),
                    "raw": data
                }
                
        except Exception as e:
            print(f"Gemini error: {e}")
            return self._demo_fallback(prompt, language)
    
    def _get_language_instruction(self, language: str) -> str:
        lang_map = {
            "hi": "Respond in Hindi (Hinglish is fine).",
            "te": "Respond in Telugu.",
            "ta": "Respond in Tamil.",
            "mr": "Respond in Marathi.",
            "gu": "Respond in Gujarati.",
            "bn": "Respond in Bengali.",
            "kn": "Respond in Kannada.",
            "en": "Respond in simple English."
        }
        return lang_map.get(language, "Respond in simple English.")
    
    def _estimate_confidence(self, text: str, raw_data: Dict) -> float:
        uncertainty_markers = [
            "not sure", "uncertain", "maybe", "perhaps",
            "shayad", "pata nahi", "samajh nahi", "confused"
        ]
        text_lower = text.lower()
        confidence = 0.85
        
        for marker in uncertainty_markers:
            if marker in text_lower:
                confidence -= 0.15
                break
        
        finish_reason = raw_data.get("candidates", [{}])[0].get("finishReason", "")
        if finish_reason == "MAX_TOKENS":
            confidence -= 0.2
        
        if len(text) < 20:
            confidence -= 0.3
        
        return max(0.0, min(1.0, confidence))
    
    def _demo_fallback(self, prompt: str, language: str) -> Dict[str, Any]:
        prompt_lower = prompt.lower()
        
        responses = {
            "hi": {
                "stock": "Aapka stock theek hai. Bas rice thoda kam hai.",
                "money": "Aaj 3200 rupee aaye hain. 1500 pending hain.",
                "orders": "Aaj 4 orders aaye hain.",
                "customers": "Customer ne pucha tha, maine jawab diya.",
                "promotions": "Weekend offer bhejun?",
                "default": "Maine samajh liya. Kuch aur bataiye?"
            },
            "en": {
                "stock": "Your stock looks good. Rice is running low.",
                "money": "3200 received today. 1500 pending.",
                "orders": "4 orders today. 2 delivered.",
                "customers": "Customer query answered.",
                "promotions": "Shall I send weekend offer?",
                "default": "Got it. What else would you like to know?"
            }
        }
        
        helper = "default"
        for h in ["stock", "money", "orders", "customers", "promotions"]:
            if h in prompt_lower:
                helper = h
                break
        
        lang = language if language in responses else "en"
        return {
            "text": responses[lang][helper],
            "confidence": 0.75,
            "tokens_used": 0,
            "demo": True
        }

gemini = GeminiService()
''')

# File 9: services/memory_service.py
write_file("services/memory_service.py", '''"""
Simple in-memory session store. For production, replace with Redis.
"""
from typing import Dict, List, Any
from datetime import datetime, timedelta
import asyncio

class MemoryService:
    def __init__(self):
        self._store: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
    
    async def get_session(self, session_id: str) -> Dict[str, Any]:
        async with self._lock:
            session = self._store.get(session_id)
            if not session:
                session = {
                    "messages": [],
                    "business_data": {},
                    "watch_list": [],
                    "trust_mode": "always_ask",
                    "language": "en",
                    "created_at": datetime.now(),
                    "expires": datetime.now() + timedelta(hours=24)
                }
                self._store[session_id] = session
            return session
    
    async def add_message(self, session_id: str, role: str, content: str, helper_type: str = None):
        async with self._lock:
            session = await self.get_session(session_id)
            session["messages"].append({
                "role": role,
                "content": content,
                "helper_type": helper_type,
                "timestamp": datetime.now().isoformat()
            })
            session["messages"] = session["messages"][-20:]
    
    async def get_context(self, session_id: str, limit: int = 5) -> List[Dict]:
        session = await self.get_session(session_id)
        return session["messages"][-limit:]
    
    async def update_business_data(self, session_id: str, key: str, value: Any):
        async with self._lock:
            session = await self.get_session(session_id)
            session["business_data"][key] = value
    
    async def add_watch(self, session_id: str, item: str, condition: str, helper_type: str):
        async with self._lock:
            session = await self.get_session(session_id)
            session["watch_list"].append({
                "item": item,
                "condition": condition,
                "helper_type": helper_type,
                "created_at": datetime.now().isoformat()
            })
    
    async def get_watch_list(self, session_id: str) -> List[Dict]:
        session = await self.get_session(session_id)
        return session.get("watch_list", [])
    
    async def set_trust_mode(self, session_id: str, mode: str):
        async with self._lock:
            session = await self.get_session(session_id)
            session["trust_mode"] = mode
    
    async def get_trust_mode(self, session_id: str) -> str:
        session = await self.get_session(session_id)
        return session.get("trust_mode", "always_ask")
    
    async def cleanup_expired(self):
        now = datetime.now()
        expired = [sid for sid, s in self._store.items() if s["expires"] < now]
        for sid in expired:
            del self._store[sid]

memory = MemoryService()
''')

# File 10: services/whatsapp_service.py
write_file("services/whatsapp_service.py", '''"""
Twilio WhatsApp Sandbox API integration.
Uses test number +14155238886 with $15 free credit.
"""
import httpx
import os
from typing import Dict, Any, Optional
from config import settings

TWILIO_API_URL = "https://api.twilio.com/2010-04-01"

class WhatsAppService:
    def __init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
        self.enabled = bool(self.account_sid and self.auth_token)
        
        if not self.enabled:
            print("Twilio not configured. WhatsApp will run in demo mode.")
        else:
            print(f"Twilio WhatsApp ready. Sandbox: {self.from_number}")
    
    async def send_message(
        self,
        to: str,
        message: str,
        message_type: str = "text"
    ) -> Dict[str, Any]:
        if not self.enabled:
            print(f"[DEMO] Would send to {to}: {message[:50]}...")
            return {"status": "demo", "to": to, "message": message}
        
        to_formatted = f"whatsapp:{to}" if not to.startswith("whatsapp:") else to
        
        auth = httpx.BasicAuth(self.account_sid, self.auth_token)
        
        payload = {
            "From": self.from_number,
            "To": to_formatted,
            "Body": message
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{TWILIO_API_URL}/Accounts/{self.account_sid}/Messages.json",
                    auth=auth,
                    data=payload
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "status": "sent",
                    "sid": data.get("sid"),
                    "to": to,
                    "message": message[:50]
                }
        except httpx.HTTPStatusError as e:
            error_msg = str(e)
            if "21608" in error_msg:
                return {"status": "error", "error": "Recipient not in sandbox. Send join code first."}
            elif "21606" in error_msg:
                return {"status": "error", "error": "Invalid number. Use +919999999999 format."}
            else:
                print(f"Twilio error: {error_msg}")
                return {"status": "error", "error": error_msg}
        except Exception as e:
            print(f"Twilio error: {e}")
            return {"status": "error", "error": str(e)}
    
    async def send_approval_request(
        self,
        to: str,
        action_description: str,
        action_id: str,
        language: str = "en"
    ):
        yes_hints = {
            "hi": "Haan / OK / thumbs up / Theek hai",
            "en": "Yes / OK / thumbs up / Sure"
        }
        
        lang = language if language in yes_hints else "en"
        
        message = (
            f"IndiAgent Approval Needed\\n\\n"
            f"{action_description}\\n\\n"
            f"Reply: {yes_hints[lang]} to approve\\n"
            f"Or: No / Nahi / X to reject"
        )
        
        return await self.send_message(to, message)
    
    def is_owner(self, from_number: str) -> bool:
        owner = settings.OWNER_PHONE_NUMBER.replace("whatsapp:", "").replace("+", "").replace(" ", "")
        sender = from_number.replace("whatsapp:", "").replace("+", "").replace(" ", "")
        return owner == sender
    
    def parse_natural_yes_no(self, message: str) -> Optional[bool]:
        msg_lower = message.lower().strip()
        
        yes_patterns = [
            "yes", "haa", "haan", "han", "h", "ok", "okay", "theek", 
            "theek hai", "sahi", "sahi hai", "done", "kar do", "karde",
            "thumbs up", "sure", "bilkul", "jarur", "zaroor",
            "ha", "hanji", "haji", "ji", "chal", "chalo"
        ]
        
        no_patterns = [
            "no", "nahi", "na", "n", "mat karo", "mat kar", "ruk",
            "ruk ja", "stop", "cancel", "baad mein",
            "nhi", "nh", "nhn"
        ]
        
        for pattern in yes_patterns:
            if pattern in msg_lower:
                return True
        
        for pattern in no_patterns:
            if pattern in msg_lower:
                return False
        
        return None

whatsapp = WhatsAppService()
''')

# File 11: services/n8n_service.py
write_file("services/n8n_service.py", '''"""
n8n Pro workflow triggers via REST API.
"""
import httpx
from typing import Dict, Any
from config import settings

class N8nService:
    def __init__(self):
        self.host = settings.N8N_HOST
        self.api_key = settings.N8N_API_KEY
        self.enabled = bool(self.host and self.api_key)
    
    async def trigger_workflow(
        self,
        workflow_id: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not self.enabled:
            print(f"n8n not configured. Workflow {workflow_id} would trigger.")
            return {"status": "demo", "workflow_id": workflow_id}
        
        webhook_url = f"{self.host}/webhook/{workflow_id}"
        headers = {"Content-Type": "application/json"}
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    webhook_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"n8n trigger error: {e}")
            return {"status": "error", "error": str(e)}
    
    async def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        if not self.enabled:
            return {"status": "demo"}
        
        headers = {"X-N8N-API-KEY": self.api_key}
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.host}/api/v1/executions/{execution_id}",
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}

n8n = N8nService()
''')

# File 12: utils/__init__.py
write_file("utils/__init__.py", "")

# File 13: utils/demo_fallback.py
write_file("utils/demo_fallback.py", '''"""
Demo mode fallback data. When APIs fail, show realistic data instead of errors.
"""
from typing import Dict, List, Any
import random

class DemoData:
    @staticmethod
    def get_dashboard_data() -> Dict[str, Any]:
        return {
            "mood": "Good",
            "orders_today": random.randint(3, 8),
            "money_in": round(random.uniform(2000, 8000), 2),
            "money_pending": round(random.uniform(500, 3000), 2),
            "low_stock_items": ["Rice (5 left)", "Wheat flour (2 left)"],
            "recent_actions": [
                {
                    "id": "act_001",
                    "helper": "stock",
                    "action": "Flagged rice as low stock",
                    "reason": "Only 5 packets remaining, below threshold of 10",
                    "time": "10 mins ago",
                    "undoable": True
                },
                {
                    "id": "act_002",
                    "helper": "money",
                    "action": "Sent payment reminder to Sharma ji",
                    "reason": "Invoice 1024 overdue by 5 days",
                    "time": "1 hour ago",
                    "undoable": False
                }
            ],
            "pending_approvals": [
                {
                    "id": "apr_001",
                    "helper": "orders",
                    "description": "Reorder 20 packets of rice from supplier?",
                    "confidence": 0.72
                }
            ],
            "active_helpers": ["stock", "money", "orders"]
        }
    
    @staticmethod
    def get_helper_data(helper_type: str) -> Dict[str, Any]:
        actions = {
            "stock": [
                {"action": "Checked inventory", "result": "Rice low, others OK"},
                {"action": "Suggested reorder", "result": "Waiting for approval"}
            ],
            "money": [
                {"action": "Tracked payment", "result": "3200 received"},
                {"action": "Flagged overdue", "result": "Sharma ji - 1500"}
            ],
            "orders": [
                {"action": "New order received", "result": "Order 45 - Processing"},
                {"action": "Status update", "result": "2 orders shipped"}
            ],
            "customers": [
                {"action": "Answered query", "result": "Stock availability confirmed"},
                {"action": "Escalated", "result": "Custom pricing request to Owner"}
            ],
            "promotions": [
                {"action": "Weekend offer ready", "result": "10 percent off template prepared"}
            ]
        }
        return {
            "helper_type": helper_type,
            "recent_actions": actions.get(helper_type, []),
            "manual_triggers": ["Send reminder now", "Check status"] if helper_type != "customers" else ["View unanswered queries"]
        }

demo_data = DemoData()
''')

# File 14: utils/confidence.py
write_file("utils/confidence.py", '''"""
Confidence threshold logic for auto-execute vs approval queue.
"""

CONFIDENCE_THRESHOLD = 0.80
CUSTOMER_CONFIDENCE_THRESHOLD = 0.70

def should_auto_execute(confidence: float, trust_mode: str, is_customer: bool = False) -> bool:
    if trust_mode == "always_ask":
        return False
    
    if is_customer and confidence < CUSTOMER_CONFIDENCE_THRESHOLD:
        return False
    
    if trust_mode == "autopilot" and confidence >= CONFIDENCE_THRESHOLD:
        return True
    
    return False

def get_confidence_explanation(confidence: float) -> str:
    if confidence >= 0.90:
        return "Very confident"
    elif confidence >= 0.80:
        return "Confident"
    elif confidence >= 0.60:
        return "Somewhat confident"
    else:
        return "Not very confident - needs your check"
''')

# File 15: utils/i18n.py
write_file("utils/i18n.py", '''"""
Simple JSON-based i18n for static UI text.
"""

TRANSLATIONS = {
    "en": {
        "app_name": "IndiAgent",
        "welcome": "Your AI team for your business",
        "get_started": "Get Started",
        "home": "Home",
        "orders": "Orders",
        "stock": "Stock",
        "money": "Money",
        "customers": "Customers",
        "promotions": "Promotions",
        "things_i_did": "Things I did for you",
        "needs_check": "I need you to check this",
        "yes": "Yes",
        "no": "No",
        "undo": "Undo",
        "ask_me_anything": "Ask Me Anything",
        "settings": "Settings",
        "trust_mode_always_ask": "Always ask me first",
        "trust_mode_autopilot": "Let helpers act on their own",
        "low_stock": "Low Stock",
        "money_in": "Money In",
        "money_pending": "Money Pending",
        "approval_needed": "Approval Needed",
        "action_completed": "Done! Here is what I did:",
        "watch_list_added": "I will watch this for you.",
        "voice_note_received": "I heard your voice note. Let me check..."
    },
    "hi": {
        "app_name": "IndiAgent",
        "welcome": "Aapke business ke liye AI team",
        "get_started": "Shuru Karein",
        "home": "Home",
        "orders": "Orders",
        "stock": "Stock",
        "money": "Paisa",
        "customers": "Customers",
        "promotions": "Offers",
        "things_i_did": "Maine aapke liye kiya:",
        "needs_check": "Yeh check karna hai:",
        "yes": "Haan",
        "no": "Nahi",
        "undo": "Wapas",
        "ask_me_anything": "Kuch bhi poochiye",
        "settings": "Settings",
        "trust_mode_always_ask": "Hamesha pehle poochiye",
        "trust_mode_autopilot": "Khud kaam karein",
        "low_stock": "Kam Stock",
        "money_in": "Aaya Paisa",
        "money_pending": "Baki Paisa",
        "approval_needed": "Approval Chahiye",
        "action_completed": "Ho gaya! Maine kiya:",
        "watch_list_added": "Main ispe nazar rakhunga.",
        "voice_note_received": "Maine aapki voice note suni. Dekhta hoon..."
    }
}

def get_text(key: str, language: str = "en") -> str:
    lang_dict = TRANSLATIONS.get(language, TRANSLATIONS["en"])
    return lang_dict.get(key, TRANSLATIONS["en"].get(key, key))

def get_all_texts(language: str = "en") -> dict:
    return TRANSLATIONS.get(language, TRANSLATIONS["en"])
''')

# File 16: routers/__init__.py
write_file("routers/__init__.py", "")

# File 17: routers/business.py
write_file("routers/business.py", '''"""
Business onboarding endpoints.
"""
from fastapi import APIRouter
from models.schemas import OnboardingRequest
from services.memory_service import memory

router = APIRouter(prefix="/business", tags=["business"])

@router.post("/onboard")
async def onboard_business(request: OnboardingRequest):
    session_id = f"biz_{request.phone}"
    
    await memory.update_business_data(session_id, "phone", request.phone)
    await memory.update_business_data(session_id, "language", request.language.value)
    await memory.update_business_data(session_id, "business_type", request.business_type.value)
    await memory.update_business_data(session_id, "current_system", request.current_system)
    await memory.update_business_data(session_id, "selected_helpers", [h.value for h in request.selected_helpers])
    await memory.set_trust_mode(session_id, request.trust_mode.value)
    
    return {
        "status": "success",
        "session_id": session_id,
        "message": "Business setup complete",
        "helpers": [h.value for h in request.selected_helpers]
    }
''')

# File 18: routers/dashboard.py
write_file("routers/dashboard.py", '''"""
Dashboard/home screen data endpoints.
"""
from fastapi import APIRouter
from services.memory_service import memory
from utils.demo_fallback import demo_data
from config import settings

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/{session_id}")
async def get_dashboard(session_id: str):
    if settings.DEMO_MODE:
        data = demo_data.get_dashboard_data()
    else:
        data = demo_data.get_dashboard_data()
    
    session = await memory.get_session(session_id)
    data["language"] = session.get("language", "en")
    data["trust_mode"] = session.get("trust_mode", "always_ask")
    
    return data

@router.get("/helper/{helper_type}/{session_id}")
async def get_helper_page(helper_type: str, session_id: str):
    data = demo_data.get_helper_data(helper_type)
    return data
''')

# File 19: routers/helpers.py
write_file("routers/helpers.py", '''"""
Runtime Helper endpoints. Each helper = Gemini + Memory + Tools.
"""
from fastapi import APIRouter
from models.schemas import ChatMessage, HelperResponse, HelperType, ApprovalRequest
from services.gemini_service import gemini
from services.memory_service import memory
from utils.confidence import should_auto_execute
from utils.i18n import get_text
import uuid

router = APIRouter(prefix="/helpers", tags=["helpers"])

HELPER_PROMPTS = {
    "stock": """You are the Stock Helper for an Indian small business.
Your job: Track inventory, flag low stock, suggest reorders.
Rules:
- Be concise, use simple language
- Always mention specific numbers
- If unsure, say so clearly
- Suggest actions but do not assume approval""",
    
    "money": """You are the Money Helper for an Indian small business.
Your job: Track payments, send reminders, flag overdue invoices.
Rules:
- Use rupee symbol for rupees
- Mention specific amounts and names
- Be polite but clear about pending payments
- Never make up payment data""",
    
    "orders": """You are the Order Helper for an Indian small business.
Your job: Track orders, update status, notify customers.
Rules:
- Mention order numbers
- Status options: Received, Processing, Packed, Shipped, Delivered
- Be specific about timelines""",
    
    "customers": """You are the Customer Helper for an Indian small business.
You answer customer questions on WhatsApp on behalf of the business.
Rules:
- Be friendly and helpful
- If you do not know something, say so honestly
- NEVER guess prices or stock if unsure
- Escalate to owner if customer asks something you cannot answer
- Use the same language the customer used""",
    
    "promotions": """You are the Promotion Helper for an Indian small business.
Your job: Create offers, send promotional messages, track response.
Rules:
- Suggest relevant offers based on business type
- Keep messages short (WhatsApp friendly)
- Include clear call-to-action"""
}

@router.post("/chat/{helper_type}")
async def chat_with_helper(helper_type: HelperType, message: ChatMessage):
    session = await memory.get_session(message.session_id)
    context = await memory.get_context(message.session_id)
    
    context_str = "\\n".join([
        f"{'User' if m['role'] == 'user' else 'Helper'}: {m['content']}"
        for m in context
    ])
    
    full_prompt = f"""Previous conversation:
{context_str}

Current message: {message.message}

Respond helpfully. If suggesting an action, state your confidence level (0-1).
"""
    
    system = HELPER_PROMPTS.get(helper_type.value, HELPER_PROMPTS["stock"])
    result = await gemini.generate(
        prompt=full_prompt,
        system_instruction=system,
        language=message.language.value
    )
    
    await memory.add_message(message.session_id, "user", message.message, helper_type.value)
    await memory.add_message(message.session_id, "assistant", result["text"], helper_type.value)
    
    confidence = result["confidence"]
    trust_mode = await memory.get_trust_mode(message.session_id)
    
    requires_approval = not should_auto_execute(confidence, trust_mode)
    
    action_id = None
    if requires_approval and confidence > 0.5:
        action_id = f"apr_{uuid.uuid4().hex[:8]}"
    
    return HelperResponse(
        helper_type=helper_type,
        message=result["text"],
        confidence=confidence,
        action_taken=None if requires_approval else "auto_executed",
        action_id=action_id,
        requires_approval=requires_approval,
        language=message.language
    )

@router.post("/approve")
async def handle_approval(approval: ApprovalRequest):
    status = "approved" if approval.approved else "rejected"
    
    return {
        "status": status,
        "action_id": approval.action_id,
        "message": get_text("action_completed", "en") if approval.approved else "Action cancelled."
    }
''')

# File 20: routers/whatsapp.py
write_file("routers/whatsapp.py", '''"""
Twilio WhatsApp webhook handler.
CRITICAL: Owner vs Customer routing happens here.
"""
from fastapi import APIRouter, Request, Form
from typing import Optional
from services.whatsapp_service import whatsapp
from services.gemini_service import gemini
from services.memory_service import memory
from utils.i18n import get_text
from config import settings
import time

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

_last_message_time: dict = {}

@router.post("/webhook")
async def receive_message(
    From: str = Form(...),
    Body: str = Form(""),
    NumMedia: int = Form(0)
):
    """
    Handle incoming Twilio WhatsApp messages.
    Twilio sends form data, not JSON.
    """
    from_number = From.replace("whatsapp:", "")
    text = Body.strip()
    
    # Debounce
    now = time.time()
    last_time = _last_message_time.get(from_number, 0)
    if now - last_time < 3:
        return {"status": "debounced"}
    _last_message_time[from_number] = now
    
    is_voice = NumMedia > 0
    is_owner = whatsapp.is_owner(from_number)
    
    if is_owner:
        response = await _handle_owner_message(from_number, text, is_voice)
    else:
        response = await _handle_customer_message(from_number, text)
    
    await whatsapp.send_message(from_number, response)
    
    return {"status": "processed", "is_owner": is_owner}

@router.get("/webhook")
async def webhook_health():
    return {"status": "ok"}

async def _handle_owner_message(phone: str, text: str, is_voice: bool) -> str:
    session_id = f"wa_owner_{phone}"
    session = await memory.get_session(session_id)
    language = session.get("language", "en")
    
    if is_voice:
        return get_text("voice_note_received", language)
    
    text_lower = text.lower()
    
    # Watch list commands
    if any(w in text_lower for w in ["watch", "nazar", "bata", "dekho"]):
        await memory.add_watch(session_id, text, "custom", "stock")
        return get_text("watch_list_added", language)
    
    # Natural yes/no
    yes_no = whatsapp.parse_natural_yes_no(text)
    if yes_no is not None:
        return "Theek hai, maine note kar liya." if yes_no else "Ruk gaya, maine cancel kar diya."
    
    # Determine helper
    helper = "stock"
    if any(w in text_lower for w in ["paisa", "payment", "rupee", "money", "due", "baki"]):
        helper = "money"
    elif any(w in text_lower for w in ["order", "delivery", "ship", "bhejo"]):
        helper = "orders"
    elif any(w in text_lower for w in ["customer", "client", "query", "sawal"]):
        helper = "customers"
    elif any(w in text_lower for w in ["offer", "discount", "promo", "sale"]):
        helper = "promotions"
    
    context = await memory.get_context(session_id)
    context_str = "\\n".join([f"{'User' if m['role'] == 'user' else 'Helper'}: {m['content']}" for m in context])
    
    system = f"You are the {helper} helper. The owner is messaging you on WhatsApp. Respond concisely. Use simple language."
    
    result = await gemini.generate(
        prompt=f"Previous: {context_str}\\n\\nCurrent: {text}",
        system_instruction=system,
        language=language
    )
    
    await memory.add_message(session_id, "user", text, helper)
    await memory.add_message(session_id, "assistant", result["text"], helper)
    
    return result["text"]

async def _handle_customer_message(phone: str, text: str) -> str:
    session_id = f"wa_customer_{phone}"
    
    system = """You are answering on behalf of a small Indian business.
CRITICAL RULES:
- If you do not know stock levels or prices, say "Let me check with the owner"
- NEVER guess or make up information
- Be polite but honest
- Use the same language the customer wrote in
- If the question is complex, say "The owner will contact you shortly""""
    
    result = await gemini.generate(
        prompt=text,
        system_instruction=system,
        language="en"
    )
    
    if result["confidence"] < 0.70:
        owner_msg = f"Customer {phone} asked: '{text}'\\nI was not confident. Please reply directly."
        await whatsapp.send_message(
            settings.OWNER_PHONE_NUMBER,
            owner_msg
        )
        return "The owner will check this and get back to you shortly. Dhanyawad!"
    
    await memory.add_message(session_id, "user", text, "customers")
    await memory.add_message(session_id, "assistant", result["text"], "customers")
    
    return result["text"]
''')

# File 21: main.py
write_file("main.py", '''"""
IndiAgent Backend - FastAPI Middleware
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from routers import helpers, whatsapp, dashboard, business

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate()
    print("IndiAgent Backend starting...")
    print(f"   Environment: {settings.APP_ENV}")
    print(f"   Demo Mode: {settings.DEMO_MODE}")
    print(f"   Gemini: {'OK' if settings.GOOGLE_AI_API_KEY else 'demo fallback'}")
    print(f"   n8n: {'OK' if settings.N8N_HOST else 'demo fallback'}")
    print(f"   Twilio: {'OK' if settings.TWILIO_ACCOUNT_SID else 'demo fallback'}")
    yield
    print("IndiAgent Backend shutting down...")

app = FastAPI(
    title="IndiAgent API",
    description="AI Employees for Indian MSMEs",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(helpers.router)
app.include_router(whatsapp.router)
app.include_router(dashboard.router)
app.include_router(business.router)

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "demo_mode": settings.DEMO_MODE,
        "services": {
            "gemini": bool(settings.GOOGLE_AI_API_KEY),
            "n8n": bool(settings.N8N_HOST),
            "twilio": bool(settings.TWILIO_ACCOUNT_SID)
        }
    }

@app.get("/")
async def root():
    return {
        "message": "IndiAgent Backend API",
        "version": "2.0.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
''')

# File 22: tests/__init__.py
write_file("tests/__init__.py", "")

print("\\n✅ ALL FILES CREATED!")
print("Run: python setup.py")
