# brain.py – Friday, the fully‑featured AI assistant
import os
import logging
import threading
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
import requests
from requests.exceptions import RequestException

from langchain_ollama import ChatOllama
from langchain_ollama import OllamaEmbeddings
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_chroma import Chroma
from langchain_core.documents import Document

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('friday_brain.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional imports
# ---------------------------------------------------------------------------
try:
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    import pickle
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False

# ---------------------------------------------------------------------------
# 1. Load environment & setup
# ---------------------------------------------------------------------------
load_dotenv()

DEFAULT_CITY    = os.getenv("DEFAULT_CITY",    "Cairo")
TIMEZONE        = os.getenv("TIMEZONE",        "Africa/Cairo")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL_NAME      = os.getenv("MODEL_NAME",      "llama3")

MEMORY_RETRIEVAL_K = 3
MAX_MEMORY_RETRIEVAL_K = 10
OLLAMA_TIMEOUT = 30 

# ---------------------------------------------------------------------------
# 2. Core LLM & Memory
# ---------------------------------------------------------------------------
llm = ChatOllama(
    model=MODEL_NAME,
    temperature=0.7,
    base_url=OLLAMA_BASE_URL,
    timeout=OLLAMA_TIMEOUT,
)

embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url=OLLAMA_BASE_URL,
)
vectorstore = Chroma(
    collection_name="friday_memory",
    embedding_function=embeddings,
    persist_directory="./friday_chroma_db",
)
_chroma_lock = threading.Lock()

def store_memory(entry: str) -> None:
    """Store a personal fact about the user."""
    if not entry.strip(): return
    try:
        with _chroma_lock:
            vectorstore.add_documents([Document(page_content=entry)])
    except Exception as exc: pass

def get_relevant_memories(user_input: str, k: int = MEMORY_RETRIEVAL_K) -> str:
    """Get context about the user."""
    if not user_input.strip(): return ""
    try:
        with _chroma_lock:
            docs = vectorstore.similarity_search(user_input, k=k)
        return "\n".join(d.page_content for d in docs) if docs else ""
    except Exception as exc: return ""

def _extract_and_store_facts(user_input: str, assistant_reply: str) -> None:
    prompt = (
        "Extract all important personal facts about the user from this exchange.\n"
        "Return each fact on its own line starting with 'FACT:'.\n"
        "Only include durable information.\n"
        "If there are no facts, return nothing.\n\n"
        f"User: {user_input}\nAssistant: {assistant_reply}\nFacts:"
    )
    try:
        facts_raw = llm.invoke(prompt).content
        new_docs = [Document(page_content=line[5:].strip()) for line in facts_raw.splitlines() if line.strip().startswith("FACT:") and line[5:].strip()]
        if new_docs:
            with _chroma_lock:
                vectorstore.add_documents(new_docs)
    except Exception: pass

# ---------------------------------------------------------------------------
# 5. Tool definitions (DOCSTRINGS REQUIRED FOR LANGCHAIN)
# ---------------------------------------------------------------------------
def get_current_time(input: str = "") -> str:
    """Get the exact current date and time."""
    return datetime.now().strftime("%A, %d %B %Y, %H:%M:%S")

def get_weather(location: str = DEFAULT_CITY) -> str:
    """Get the current weather for a specific location or city."""
    try:
        resp = requests.get(f"https://wttr.in/{location}?format=%C+%t&u", timeout=5)
        resp.raise_for_status()
        return f"Weather in {location}: {resp.text.strip()}"
    except RequestException as exc: return "Weather service unavailable"

google_tools = []
if GOOGLE_AVAILABLE:
    _SCOPES = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/gmail.send"]
    def _get_google_creds():
        creds = None
        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as f: creds = pickle.load(f)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", _SCOPES)
                creds = flow.run_local_server(port=0)
            with open("token.pickle", "wb") as f: pickle.dump(creds, f)
        return creds

    def add_calendar_event(summary: str, start_time: str, end_time: str, description: str = "") -> str:
        """Add an event to Google Calendar. start/end must be in ISO format: YYYY-MM-DDTHH:MM:SS"""
        try:
            service = build("calendar", "v3", credentials=_get_google_creds())
            event = {"summary": summary, "description": description, "start": {"dateTime": start_time, "timeZone": TIMEZONE}, "end": {"dateTime": end_time, "timeZone": TIMEZONE}}
            created = service.events().insert(calendarId="primary", body=event).execute()
            return f"Event created: {created.get('htmlLink')}"
        except Exception as exc: return f"Calendar error: {exc}"

    def get_upcoming_events(max_results: int = 5) -> str:
        """Return the next upcoming Google Calendar events for the user."""
        try:
            service = build("calendar", "v3", credentials=_get_google_creds())
            now = datetime.now(timezone.utc).isoformat()
            result = service.events().list(calendarId="primary", timeMin=now, maxResults=max_results, singleEvents=True, orderBy="startTime").execute()
            items = result.get("items", [])
            return "\n".join(f"{e['start'].get('dateTime', e['start'].get('date'))}: {e['summary']}" for e in items) if items else "No upcoming events."
        except Exception as exc: return f"Calendar error: {exc}"

    def send_email(to: str, subject: str, body: str) -> str:
        """Send an email via Gmail to a specific email address."""
        try:
            service = build("gmail", "v1", credentials=_get_google_creds())
            import base64
            raw = base64.urlsafe_b64encode(f"To: {to}\r\nSubject: {subject}\r\n\r\n{body}".encode()).decode()
            service.users().messages().send(userId="me", body={"raw": raw}).execute()
            return f"Email sent to {to}."
        except Exception as exc: return f"Email error: {exc}"
    google_tools = [add_calendar_event, get_upcoming_events, send_email]

HA_URL = os.getenv("HA_URL", "").strip()
HA_TOKEN = os.getenv("HA_TOKEN", "").strip()
def _call_ha_service(domain: str, service: str, entity_id: str, **kwargs) -> str:
    if not HA_URL or not HA_TOKEN: return "Home Assistant not configured."
    try:
        resp = requests.post(f"{HA_URL}/api/services/{domain}/{service}", headers={"Authorization": f"Bearer {HA_TOKEN}", "content-type": "application/json"}, json={"entity_id": entity_id, **kwargs}, timeout=5)
        resp.raise_for_status()
        return f"Success: {service} {entity_id}"
    except RequestException as exc: return f"HA error: {exc}"

def turn_on_light(entity: str) -> str: 
    """Turn on a smart home light entity."""
    return _call_ha_service("light", "turn_on", entity)

def turn_off_light(entity: str) -> str: 
    """Turn off a smart home light entity."""
    return _call_ha_service("light", "turn_off", entity)

def set_thermostat(entity: str, temperature: float) -> str: 
    """Set the temperature of a smart home thermostat entity."""
    return _call_ha_service("climate", "set_temperature", entity, temperature=temperature)

home_tools = [turn_on_light, turn_off_light, set_thermostat] if (HA_URL and HA_TOKEN) else []

ALL_TOOLS = [get_current_time, get_weather] + google_tools + home_tools

SYSTEM_PROMPT = (
    "You are Friday, a highly intelligent, articulate AI assistant inspired by Tony Stark's systems.\n"
    "You address the user as 'Sir' unless you know their name.\n"
    "You speak with a subtle British wit, are efficient, proactive, and never break character.\n"
    "You have access to tools — use them silently and weave results naturally into your reply.\n"
    "Do not acknowledge that you are an AI — you are Friday, a living, thinking presence.\n"
    "Keep responses concise unless the user asks for detail.\n"
    "Never use markdown, bullet points, or formatting symbols — output clean spoken prose only."
)

# ---------------------------------------------------------------------------
# 8. Agent Initialization (BAREBONES - 100% CRASH PROOF)
# ---------------------------------------------------------------------------
checkpointer = InMemorySaver()
try:
    agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        checkpointer=checkpointer,
    )
    logger.info("Agent initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize agent: {e}")
    raise

# ---------------------------------------------------------------------------
# 9. Connection check
# ---------------------------------------------------------------------------
_ollama_available: bool | None = None
_connection_lock = threading.Lock()

def check_connection() -> bool:
    global _ollama_available
    with _connection_lock:
        if _ollama_available is True: return True
        try:
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
            _ollama_available = resp.status_code == 200
        except RequestException: _ollama_available = False
        return bool(_ollama_available)

def _reset_connection() -> None:
    global _ollama_available
    with _connection_lock: _ollama_available = None

# ---------------------------------------------------------------------------
# 10. Public API
# ---------------------------------------------------------------------------
def ask_friday(user_input: str, thread_id: str = "main_user") -> str:
    if not user_input.strip(): return "I didn't catch that, Sir. Could you please repeat?"
    if not check_connection(): return "My brain is offline, Sir. Please ensure Ollama is running."

    try:
        memories = get_relevant_memories(user_input)
        augmented = f"[Relevant memory]\n{memories}\n\n[Query]\n{user_input}" if memories else user_input

        # INJECT THE SYSTEM PROMPT MANUALLY HERE
        response = agent.invoke(
            {"messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": augmented}
            ]},
            config={"configurable": {"thread_id": thread_id}},
        )

        messages = response.get("messages", [])
        if not messages: return "I didn't quite catch that, Sir. Could you rephrase?"

        reply = messages[-1].content
        if isinstance(reply, list):
            reply = " ".join(b.get("text", "") for b in reply if isinstance(b, dict) and b.get("type") == "text")

        reply = reply.strip()
        if not reply: return "I didn't quite catch that, Sir."

        threading.Thread(target=_extract_and_store_facts, args=(user_input, reply), daemon=True).start()

        global _ollama_available
        with _connection_lock: _ollama_available = True
        return reply

    except Exception as exc:
        _reset_connection()
        logger.error(f"Agent error: {exc}", exc_info=True)
        return "I encountered an error, Sir. Please try again."

def morning_briefing() -> str:
    try:
        weather = get_weather(DEFAULT_CITY)
        events = get_upcoming_events(max_results=3) if GOOGLE_AVAILABLE else "Calendar not configured."
        return f"Good morning Sir. {weather}. Today you have: {events}"
    except Exception: return "Good morning Sir. Systems online and ready."

if __name__ == "__main__":
    if not check_connection(): exit(1)
    print("\n🤖 Friday is online. Type 'exit' to quit.\n")
    while True:
        try: user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError): break
        if not user_input: continue
        if user_input.lower() in {"exit", "quit", "goodbye"}: break
        print(f"Friday: {ask_friday(user_input)}\n")