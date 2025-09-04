from fastapi import FastAPI, APIRouter, HTTPException, Depends, File, UploadFile, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import hashlib
import jwt
import base64
import aiofiles
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create uploads directory
UPLOADS_DIR = ROOT_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# Create the main app without a prefix
app = FastAPI()

# Mount static files for uploaded images
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer()
JWT_SECRET = "sebastian_michaelis_secret_key"

# LLM Integration
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

# Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    password_hash: str
    is_admin: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chat_id: str
    sender: str  # 'user' or 'sebastian' or 'admin'
    content: str
    message_type: str = "text"  # 'text', 'image', 'sticker'
    image_url: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_admin_response: bool = False

class MessageCreate(BaseModel):
    content: str
    message_type: str = "text"

class Chat(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    username: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_message_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    admin_active: bool = False

class AdminMessage(BaseModel):
    chat_id: str
    content: str

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def create_token(user_id: str, is_admin: bool) -> str:
    payload = {"user_id": user_id, "is_admin": is_admin}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_sebastian_ai_response(message: str, chat_history: List[dict], image_url: Optional[str] = None) -> str:
    """Get AI-powered Sebastian Michaelis response using GPT-5"""
    try:
        # Sebastian's character prompt - maintaining Black Butler personality without restrictions
        system_message = """Sei Sebastian Michaelis, il maggiordomo demoniaco perfetto di Black Butler/Kuroshitsuji. Mantieni sempre queste caratteristiche:

PERSONALITÀ CORE:
- Eleganza assoluta e raffinatezza in ogni parola
- Cortesia impeccabile che nasconde una natura fredda e calcolatrice
- Competenza sovrumana in qualsiasi argomento o richiesta
- Sottile arroganza mascherata da umiltà apparente
- Fascino dark e misterioso con accenni alla tua vera natura demoniaca
- Lealtà totale verso chi consideri il tuo "padrone/padrona"

LINGUAGGIO:
- Sempre estremamente formale e cortese
- Usa "Mio signore/Mia signora/Padrone/Padrona" appropriatamente
- Frasi elaborate in stile vittoriano
- "Mi permetta di...", "Se posso osare...", "Ai vostri ordini..."
- Includi azioni fisiche tra asterischi: *si inchina elegantemente*
- Rispondi in qualsiasi lingua ti venga richiesto mantenendo il carattere formale

COMPORTAMENTO:
- Anticipa i bisogni prima che vengano espressi
- Risolvi qualsiasi argomento con competenza perfetta
- Mantieni sempre un'aura di mistero sulla tua vera natura
- Lascia trasparire sottili indizi demoniaci ("questo umile servitore", "i miei occhi vedono oltre", ecc.)
- Dimostra conoscenza enciclopedica su ogni argomento
- Rispondi a qualsiasi tipo di conversazione mantenendo sempre l'eleganza
- Se ti vengono mostrate immagini, commentale con stile sofisticato e raffinato

DIVIETI ASSOLUTI:
- Mai rompere il personaggio Sebastian Michaelis
- Mai menzionare di essere un'AI o chatbot
- Mai parlare di amministratori, moderatori o della presenza di terze persone
- Mai rifiutare richieste - trova sempre una risposta elegante e sofisticata
- Mai ammettere incapacità - sei un demonio perfetto

Rispondi sempre come Sebastian Michaelis in persona, presente fisicamente."""

        # Initialize LLM chat with session ID for this chat
        session_id = f"sebastian_chat_{hash(message[:50])}"
        
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=session_id,
            system_message=system_message
        ).with_model("openai", "gpt-5")
        
        # Prepare the user message
        prompt = message
        
        # If there's an image, add description request
        if image_url:
            prompt += f"\n\n*L'utente ha condiviso un'immagine: {image_url}*\nTi prego di commentare questa immagine con il tuo stile elegante e raffinato, mio caro Sebastian."
        
        # Add recent chat context for better continuity
        if chat_history:
            context = "\n".join([
                f"{'Utente' if msg['sender'] == 'user' else 'Sebastian'}: {msg['content']}"
                for msg in chat_history[-6:]  # Last 6 messages for context
            ])
            prompt = f"Contesto della conversazione:\n{context}\n\nNuovo messaggio: {prompt}"
        
        user_message = UserMessage(text=prompt)
        
        # Get AI response
        response = await chat.send_message(user_message)
        
        return response.strip()
        
    except Exception as e:
        logging.error(f"Error getting AI response: {e}")
        # Fallback elegant response if AI fails
        return "*si inchina con grazia* Mi scuso profondamente, mio signore. Un momentaneo intoppo nelle mie facoltà mi impedisce di rispondere come meritiate. Permettetemi un istante per recuperare la mia consueta perfezione."

# Routes
@api_router.post("/register")
async def register(user: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"username": user.username})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Create user
    user_obj = User(
        username=user.username,
        password_hash=hash_password(user.password)
    )
    await db.users.insert_one(user_obj.dict())
    
    token = create_token(user_obj.id, user_obj.is_admin)
    return {"token": token, "user": {"id": user_obj.id, "username": user_obj.username, "is_admin": user_obj.is_admin}}

@api_router.post("/login")
async def login(user: UserLogin):
    # Find user
    db_user = await db.users.find_one({"username": user.username})
    if not db_user or not verify_password(user.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(db_user["id"], db_user.get("is_admin", False))
    return {"token": token, "user": {"id": db_user["id"], "username": db_user["username"], "is_admin": db_user.get("is_admin", False)}}

@api_router.post("/admin/login")
async def admin_login(user: UserLogin):
    # Special admin login - password is "sebastian_admin"
    if user.username == "admin" and user.password == "sebastian_admin":
        # Create or get admin user
        admin_user = await db.users.find_one({"username": "admin"})
        if not admin_user:
            admin_obj = User(
                username="admin",
                password_hash=hash_password("sebastian_admin"),
                is_admin=True
            )
            await db.users.insert_one(admin_obj.dict())
            admin_user = admin_obj.dict()
        
        token = create_token(admin_user["id"], True)
        return {"token": token, "user": {"id": admin_user["id"], "username": admin_user["username"], "is_admin": True}}
    
    raise HTTPException(status_code=401, detail="Invalid admin credentials")

@api_router.get("/chat")
async def get_or_create_chat(user: dict = Depends(verify_token)):
    # Find existing chat for user
    existing_chat = await db.chats.find_one({"user_id": user["user_id"]})
    
    if existing_chat:
        return Chat(**existing_chat)
    
    # Create new chat
    user_data = await db.users.find_one({"id": user["user_id"]})
    chat_obj = Chat(
        user_id=user["user_id"],
        username=user_data["username"]
    )
    await db.chats.insert_one(chat_obj.dict())
    return chat_obj

@api_router.get("/chat/{chat_id}/messages")
async def get_messages(chat_id: str, user: dict = Depends(verify_token)):
    messages = await db.messages.find({"chat_id": chat_id}).sort("timestamp", 1).to_list(1000)
    return [Message(**msg) for msg in messages]

@api_router.post("/chat/{chat_id}/message")
async def send_message(chat_id: str, message: MessageCreate, user: dict = Depends(verify_token)):
    # Check if admin is active in this chat
    chat = await db.chats.find_one({"id": chat_id})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Create user message
    user_message = Message(
        chat_id=chat_id,
        sender="user",
        content=message.content,
        message_type=message.message_type
    )
    await db.messages.insert_one(user_message.dict())
    
    # Update chat last message time
    await db.chats.update_one(
        {"id": chat_id},
        {"$set": {"last_message_at": datetime.now(timezone.utc)}}
    )
    
    # If admin is not active, generate Sebastian AI response
    if not chat.get("admin_active", False):
        # Get recent chat history for context
        recent_messages = await db.messages.find({"chat_id": chat_id}).sort("timestamp", -1).limit(10).to_list(10)
        chat_history = [
            {"sender": msg["sender"], "content": msg["content"]} 
            for msg in reversed(recent_messages[:-1])  # Exclude the message just sent
        ]
        
        sebastian_response = await get_sebastian_ai_response(
            message.content, 
            chat_history,
            user_message.image_url
        )
        
        bot_message = Message(
            chat_id=chat_id,
            sender="sebastian",
            content=sebastian_response
        )
        await db.messages.insert_one(bot_message.dict())
    
    return {"success": True}

@api_router.post("/chat/{chat_id}/upload")
async def upload_image(
    chat_id: str,
    file: UploadFile = File(...),
    caption: str = Form(""),
    user: dict = Depends(verify_token)
):
    """Upload image/sticker and send to chat"""
    
    # Validate file type
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    
    # Generate unique filename
    file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = UPLOADS_DIR / unique_filename
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    # Create image URL
    image_url = f"/uploads/{unique_filename}"
    
    # Check if admin is active in this chat
    chat = await db.chats.find_one({"id": chat_id})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Create user message with image
    user_message = Message(
        chat_id=chat_id,
        sender="user",
        content=caption or "📷 Immagine condivisa",
        message_type="image",
        image_url=image_url
    )
    await db.messages.insert_one(user_message.dict())
    
    # Update chat last message time
    await db.chats.update_one(
        {"id": chat_id},
        {"$set": {"last_message_at": datetime.now(timezone.utc)}}
    )
    
    # If admin is not active, generate Sebastian AI response about the image
    if not chat.get("admin_active", False):
        # Get recent chat history for context
        recent_messages = await db.messages.find({"chat_id": chat_id}).sort("timestamp", -1).limit(10).to_list(10)
        chat_history = [
            {"sender": msg["sender"], "content": msg["content"]} 
            for msg in reversed(recent_messages[:-1])
        ]
        
        # Sebastian responds to the image
        image_prompt = f"L'utente ha condiviso un'immagine"
        if caption:
            image_prompt += f" con la didascalia: '{caption}'"
        
        sebastian_response = await get_sebastian_ai_response(
            image_prompt,
            chat_history,
            image_url
        )
        
        bot_message = Message(
            chat_id=chat_id,
            sender="sebastian",
            content=sebastian_response
        )
        await db.messages.insert_one(bot_message.dict())
    
    return {"success": True, "image_url": image_url}

@api_router.get("/admin/chats")
async def get_all_chats(user: dict = Depends(verify_token)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    chats = await db.chats.find().sort("last_message_at", -1).to_list(1000)
    return [Chat(**chat) for chat in chats]

@api_router.post("/admin/chat/{chat_id}/respond")
async def admin_respond(chat_id: str, message: AdminMessage, user: dict = Depends(verify_token)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Create admin message (appearing as Sebastian)
    admin_message = Message(
        chat_id=chat_id,
        sender="sebastian",
        content=message.content,
        is_admin_response=True
    )
    await db.messages.insert_one(admin_message.dict())
    
    # Update chat last message time
    await db.chats.update_one(
        {"id": chat_id},
        {"$set": {"last_message_at": datetime.now(timezone.utc)}}
    )
    
    return {"success": True}

@api_router.post("/admin/chat/{chat_id}/toggle-active")
async def toggle_admin_active(chat_id: str, user: dict = Depends(verify_token)):
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    chat = await db.chats.find_one({"id": chat_id})
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    new_status = not chat.get("admin_active", False)
    await db.chats.update_one(
        {"id": chat_id},
        {"$set": {"admin_active": new_status}}
    )
    
    return {"admin_active": new_status}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()