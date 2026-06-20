"""
IndiAgent Backend - Complete Single File
AI Employees for Indian MSMEs
"""
import os
import asyncio
import time
import random
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx
from dotenv import load_dotenv

load_dotenv()

# ==================== CONFIG ====================
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

settings = Settings()

# ==================== MODELS ====================
class Language(str, Enum):
    ENGLISH = "en"; HINDI = "hi"; TELUGU = "te"; TAMIL = "ta"
    MARATHI = "mr"; GUJARATI = "gu"; BENGALI = "bn"; KANNADA = "kn"

class BusinessType(str, Enum):
    KIRANA = "kirana"; PHARMACY = "pharmacy"; SALON = "salon"
    RESTAURANT = "restaurant"; CLOTHING = "clothing"
    ELECTRONICS = "electronics"; OTHER = "other"

class HelperType(str, Enum):
    STOCK = "stock"; MONEY = "money"; ORDERS = "orders"
    CUSTOMERS = "customers"; PROMOTIONS = "promotions"

class TrustMode(str, Enum):
    ALWAYS_ASK = "always_ask"; AUTOPILOT = "autopilot"

class OnboardingRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\+91\d{10}$")
    language: Language; business_type: BusinessType
    current_system: str; selected_helpers: List[HelperType]
    trust_mode: TrustMode = TrustMode.ALWAYS_ASK

class ChatMessage(BaseModel):
    message: str; helper_type: Optional[HelperType] = None
    language: Language = Language.ENGLISH; session_id: str; is_voice: bool = False

class HelperResponse(BaseModel):
    helper_type: HelperType; message: str; confidence: float
    action_taken: Optional[str] = None; action_id: Optional[str] = None
    requires_approval: bool = False; language: Language

class ApprovalRequest(BaseModel):
    action_id: str; approved: bool; session_id: str

# ==================== MEMORY ====================
class MemoryService:
    def __init__(self):
        self._store: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
    
    async def get_session(self, session_id: str) -> Dict[str, Any]:
        async with self._lock:
            session = self._store.get(session_id)
            if not session:
                session = {
                    "messages": [], "business_data": {}, "watch_list": [],
                    "trust_mode": "always_ask", "language": "en",
                    "created_at": datetime.now(), "expires": datetime.now() + timedelta(hours=24)
                }
                self._store[session_id] = session
            return session
    
    async def add_message(self, session_id: str, role: str, content: str, helper_type: str = None):
        async with self._lock:
            session = await self.get_session(session_id)
            session["messages"].append({"role": role, "content": content, "helper_type": helper_type, "timestamp": datetime.now().isoformat()})
            session["messages"] = session["messages"][-20:]
    
    async def get_context(self, session_id: str, limit: int = 5) -> List[Dict]:
        session = await self.get_session(session_id)
        return session["messages"][-limit:]
    
    async def update_business_data(self, session_id: str, key: str, value: Any):
        async with self._lock:
            session = await self.get_session(session_id)
            session["business_data"][key] = value
    
    async def set_trust_mode(self, session_id: str, mode: str):
        async with self._lock:
            session = await self.get_session(session_id)
            session["trust_mode"] = mode
    
    async def get_trust_mode(self, session_id: str) -> str:
        session = await self.get_session(session_id)
        return session.get("trust_mode", "always_ask")

memory = MemoryService()

# ==================== GEMINI ====================
class GeminiService:
    def __init__(self):
        self.api_key = settings.GOOGLE_AI_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    
    async def generate(self, prompt: str, system_instruction: Optional[str] = None, language: str = "en") -> Dict[str, Any]:
        if not self.api_key:
            return self._demo_fallback(prompt, language)
        
        lang_map = {"hi": "Respond in Hindi.", "te": "Respond in Telugu.", "ta": "Respond in Tamil.",
                    "mr": "Respond in Marathi.", "gu": "Respond in Gujarati.", "bn": "Respond in Bengali.",
                    "kn": "Respond in Kannada.", "en": "Respond in simple English."}
        lang_inst = lang_map.get(language, "Respond in simple English.")
        full_system = (system_instruction or "") + "\n" + lang_inst
        
        payload = {
            "contents": [{"role": "user", "parts": [{"text": full_system + "\n\n" + prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024, "topP": 0.8, "topK": 40}
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{self.base_url}?key={self.api_key}", headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key}, json=payload)
                if response.status_code == 429:
                    return self._demo_fallback(prompt, language)
                response.raise_for_status()
                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    return self._demo_fallback(prompt, language)
                text = candidates[0]["content"]["parts"][0]["text"]
                return {"text": text.strip(), "confidence": self._estimate_confidence(text, data), "tokens_used": data.get("usageMetadata", {}).get("totalTokenCount", 0)}
        except Exception as e:
            print(f"Gemini error: {e}")
            return self._demo_fallback(prompt, language)
    
    def _estimate_confidence(self, text: str, raw_data: Dict) -> float:
        confidence = 0.85
        for marker in ["not sure", "maybe", "shayad", "pata nahi", "confused"]:
            if marker in text.lower():
                confidence -= 0.15; break
        if raw_data.get("candidates", [{}])[0].get("finishReason", "") == "MAX_TOKENS":
            confidence -= 0.2
        if len(text) < 20: confidence -= 0.3
        return max(0.0, min(1.0, confidence))
    
    def _demo_fallback(self, prompt: str, language: str) -> Dict[str, Any]:
        prompt_lower = prompt.lower()
        responses = {
            "hi": {"stock": "Aapka stock theek hai. Bas rice thoda kam hai.", "money": "Aaj 3200 rupee aaye hain. 1500 pending hain.", "orders": "Aaj 4 orders aaye hain.", "customers": "Customer ne pucha tha, maine jawab diya.", "promotions": "Weekend offer bhejun?", "default": "Maine samajh liya. Kuch aur bataiye?"},
            "en": {"stock": "Your stock looks good. Rice is running low.", "money": "3200 received today. 1500 pending.", "orders": "4 orders today. 2 delivered.", "customers": "Customer query answered.", "promotions": "Shall I send weekend offer?", "default": "Got it. What else would you like to know?"}
        }
        helper = "default"
        for h in ["stock", "money", "orders", "customers", "promotions"]:
            if h in prompt_lower: helper = h; break
        lang = language if language in responses else "en"
        return {"text": responses[lang][helper], "confidence": 0.75, "tokens_used": 0, "demo": True}

gemini = GeminiService()

# ==================== TWILIO ====================
class WhatsAppService:
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_WHATSAPP_NUMBER
        self.enabled = bool(self.account_sid and self.auth_token)
    
    async def send_message(self, to: str, message: str) -> Dict[str, Any]:
        if not self.enabled:
            print(f"[DEMO] Would send to {to}: {message[:50]}...")
            return {"status": "demo", "to": to, "message": message}
        
        to_formatted = f"whatsapp:{to}" if not to.startswith("whatsapp:") else to
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json",
                    auth=httpx.BasicAuth(self.account_sid, self.auth_token),
                    data={"From": self.from_number, "To": to_formatted, "Body": message})
                response.raise_for_status()
                return {"status": "sent", "sid": response.json().get("sid"), "to": to}
        except Exception as e:
            print(f"Twilio error: {e}")
            return {"status": "error", "error": str(e)}
    
    def is_owner(self, from_number: str) -> bool:
        owner = settings.OWNER_PHONE_NUMBER.replace("whatsapp:", "").replace("+", "").replace(" ", "")
        sender = from_number.replace("whatsapp:", "").replace("+", "").replace(" ", "")
        return owner == sender
    
    def parse_natural_yes_no(self, message: str) -> Optional[bool]:
        msg_lower = message.lower().strip()
        yes = ["yes", "haa", "haan", "ok", "okay", "theek", "theek hai", "sahi", "done", "kar do", "karde", "thumbs up", "sure", "bilkul", "jarur", "zaroor", "ha", "hanji", "haji", "ji", "chal", "chalo"]
        no = ["no", "nahi", "na", "mat karo", "mat kar", "ruk", "ruk ja", "stop", "cancel", "baad mein", "nhi", "nh", "nhn"]
        for p in yes:
            if p in msg_lower: return True
        for p in no:
            if p in msg_lower: return False
        return None

whatsapp = WhatsAppService()

# ==================== DEMO DATA ====================
class DemoData:
    @staticmethod
    def get_dashboard_data():
        return {
            "mood": "Good", "orders_today": random.randint(3, 8),
            "money_in": round(random.uniform(2000, 8000), 2), "money_pending": round(random.uniform(500, 3000), 2),
            "low_stock_items": ["Rice (5 left)", "Wheat flour (2 left)"],
            "recent_actions": [{"id": "act_001", "helper": "stock", "action": "Flagged rice as low stock", "reason": "Only 5 packets remaining", "time": "10 mins ago", "undoable": True}],
            "pending_approvals": [{"id": "apr_001", "helper": "orders", "description": "Reorder 20 packets of rice?", "confidence": 0.72}],
            "active_helpers": ["stock", "money", "orders"]
        }

demo_data = DemoData()

# ==================== ROUTERS ====================
business_router = APIRouter(prefix="/business", tags=["business"])
dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])
helpers_router = APIRouter(prefix="/helpers", tags=["helpers"])
whatsapp_router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

HELPER_PROMPTS = {
    "stock": "You are the Stock Helper for an Indian small business. Track inventory, flag low stock, suggest reorders. Be concise, mention specific numbers.",
    "money": "You are the Money Helper for an Indian small business. Track payments, send reminders, flag overdue. Use rupee symbol, mention amounts and names.",
    "orders": "You are the Order Helper for an Indian small business. Track orders, update status. Mention order numbers.",
    "customers": "You are the Customer Helper. Answer customer questions on WhatsApp. If unsure, say so honestly. NEVER guess prices or stock.",
    "promotions": "You are the Promotion Helper. Create offers, send promotional messages. Keep messages short."
}

@business_router.post("/onboard")
async def onboard_business(request: OnboardingRequest):
    session_id = f"biz_{request.phone}"
    await memory.update_business_data(session_id, "phone", request.phone)
    await memory.update_business_data(session_id, "language", request.language.value)
    await memory.update_business_data(session_id, "business_type", request.business_type.value)
    await memory.update_business_data(session_id, "selected_helpers", [h.value for h in request.selected_helpers])
    await memory.set_trust_mode(session_id, request.trust_mode.value)
    return {"status": "success", "session_id": session_id, "helpers": [h.value for h in request.selected_helpers]}

@dashboard_router.get("/{session_id}")
async def get_dashboard(session_id: str):
    data = demo_data.get_dashboard_data()
    session = await memory.get_session(session_id)
    data["language"] = session.get("language", "en")
    data["trust_mode"] = session.get("trust_mode", "always_ask")
    return data

@helpers_router.post("/chat/{helper_type}")
async def chat_with_helper(helper_type: HelperType, message: ChatMessage):
    session = await memory.get_session(message.session_id)
    context = await memory.get_context(message.session_id)
    context_str = "\n".join([f"{'User' if m['role'] == 'user' else 'Helper'}: {m['content']}" for m in context])
    
    full_prompt = f"Previous:\n{context_str}\n\nCurrent: {message.message}\n\nRespond helpfully."
    system = HELPER_PROMPTS.get(helper_type.value, HELPER_PROMPTS["stock"])
    result = await gemini.generate(prompt=full_prompt, system_instruction=system, language=message.language.value)
    
    await memory.add_message(message.session_id, "user", message.message, helper_type.value)
    await memory.add_message(message.session_id, "assistant", result["text"], helper_type.value)
    
    confidence = result["confidence"]
    trust_mode = await memory.get_trust_mode(message.session_id)
    requires_approval = not (trust_mode == "autopilot" and confidence >= 0.80)
    action_id = f"apr_{uuid.uuid4().hex[:8]}" if requires_approval and confidence > 0.5 else None
    
    return HelperResponse(helper_type=helper_type, message=result["text"], confidence=confidence,
                         action_taken=None if requires_approval else "auto_executed", action_id=action_id,
                         requires_approval=requires_approval, language=message.language)

@helpers_router.post("/approve")
async def handle_approval(approval: ApprovalRequest):
    status = "approved" if approval.approved else "rejected"
    return {"status": status, "action_id": approval.action_id, "message": "Done!" if approval.approved else "Cancelled."}

_last_message_time: dict = {}

@whatsapp_router.post("/webhook")
async def receive_message(From: str = Form(...), Body: str = Form(""), NumMedia: int = Form(0)):
    from_number = From.replace("whatsapp:", "")
    text = Body.strip()
    
    now = time.time()
    if now - _last_message_time.get(from_number, 0) < 3:
        return {"status": "debounced"}
    _last_message_time[from_number] = now
    
    is_owner = whatsapp.is_owner(from_number)
    
    if is_owner:
        response = await _handle_owner(from_number, text, NumMedia > 0)
    else:
        response = await _handle_customer(from_number, text)
    
    await whatsapp.send_message(from_number, response)
    return {"status": "processed", "is_owner": is_owner}

@whatsapp_router.get("/webhook")
async def webhook_health():
    return {"status": "ok"}

async def _handle_owner(phone: str, text: str, is_voice: bool) -> str:
    session_id = f"wa_owner_{phone}"
    session = await memory.get_session(session_id)
    language = session.get("language", "en")
    
    if is_voice: return "I heard your voice note. Let me check..."
    
    text_lower = text.lower()
    if any(w in text_lower for w in ["watch", "nazar", "bata"]):
        return "I will watch this for you."
    
    yes_no = whatsapp.parse_natural_yes_no(text)
    if yes_no is not None:
        return "Theek hai, maine note kar liya." if yes_no else "Ruk gaya, maine cancel kar diya."
    
    helper = "stock"
    if any(w in text_lower for w in ["paisa", "payment", "money", "due"]): helper = "money"
    elif any(w in text_lower for w in ["order", "delivery", "ship"]): helper = "orders"
    elif any(w in text_lower for w in ["customer", "query", "sawal"]): helper = "customers"
    elif any(w in text_lower for w in ["offer", "discount", "promo"]): helper = "promotions"
    
    context = await memory.get_context(session_id)
    context_str = "\n".join([f"{'User' if m['role'] == 'user' else 'Helper'}: {m['content']}" for m in context])
    result = await gemini.generate(prompt=f"Previous: {context_str}\n\nCurrent: {text}", system_instruction=f"You are the {helper} helper. Respond concisely.", language=language)
    
    await memory.add_message(session_id, "user", text, helper)
    await memory.add_message(session_id, "assistant", result["text"], helper)
    return result["text"]

async def _handle_customer(phone: str, text: str) -> str:
    result = await gemini.generate(prompt=text, system_instruction="You answer on behalf of a small Indian business. If unsure, say 'Let me check with the owner'. NEVER guess.", language="en")
    if result["confidence"] < 0.70:
        await whatsapp.send_message(settings.OWNER_PHONE_NUMBER, f"Customer {phone} asked: '{text}'\nI was not confident.")
        return "The owner will check this. Dhanyawad!"
    return result["text"]

# ==================== FASTAPI APP ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("IndiAgent Backend starting...")
    print(f"   Gemini: {'OK' if settings.GOOGLE_AI_API_KEY else 'demo'}")
    print(f"   Twilio: {'OK' if settings.TWILIO_ACCOUNT_SID else 'demo'}")
    yield
    print("Shutting down...")

app = FastAPI(title="IndiAgent API", description="AI Employees for Indian MSMEs", version="2.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(business_router)
app.include_router(dashboard_router)
app.include_router(helpers_router)
app.include_router(whatsapp_router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "demo_mode": settings.DEMO_MODE, "services": {"gemini": bool(settings.GOOGLE_AI_API_KEY), "twilio": bool(settings.TWILIO_ACCOUNT_SID)}}

@app.get("/")
async def root():
    return {"message": "IndiAgent Backend API", "version": "2.0.0", "docs": "/docs"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
