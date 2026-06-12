# brain.py – Friday, the fully‑featured AI assistant (LangGraph + Ollama)
import os
import sys
import base64
import threading
import time
from datetime import datetime
from dotenv import load_dotenv
import requests
from requests.exceptions import RequestException

from langchain_ollama import ChatOllama
# FIX: Updated to the modern langchain-ollama package to remove deprecation warning
from langchain_ollama import OllamaEmbeddings 
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_chroma import Chroma
from langchain_core.documents import Document

# -------------------------------------------------------------------
# Optional imports – degrade gracefully if not installed
# -------------------------------------------------------------------
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

# -------------------------------------------------------------------
# 1. Load environment & setup
# -------------------------------------------------------------------
load_dotenv()

DEFAULT_CITY      = os.getenv("DEFAULT_CITY",      "Cairo")
TIMEZONE          = os.getenv("TIMEZONE",           "Africa/Cairo")
OLLAMA_BASE_URL   = os.getenv("OLLAMA_BASE_URL",    "http://localhost:11434")

# Using Llama 3 for reliable LangGraph tool execution
MODEL_NAME        = os.getenv("MODEL_NAME",          "llama3")

# -------------------------------------------------------------------
# 2. Core LLM
# -------------------------------------------------------------------
llm = ChatOllama(
    model=MODEL_NAME,
    temperature=0.7,
    base_url=OLLAMA_BASE_URL,
)

# -------------------------------------------------------------------
# 3. Long‑term memory — Chroma + local embeddings
# -------------------------------------------------------------------
embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url=OLLAMA_BASE_URL,
)

vectorstore = Chroma(
    collection_name="friday_memory",
    embedding_function=embeddings,
    persist_directory="./friday_chroma_db",
)

def store_memory(entry: str) -> None:
    """Store a fact or user preference in the vector memory (Chroma)."""
    try:
        vectorstore.add_documents([Document(page_content=entry)])
        print(f"📝 Stored in memory: {entry}")
    except Exception as e:
        print(f"⚠️ Memory write error: {e}")

def get_relevant_memories(user_input: str, k: int = 3) -> str:
    """Retrieve the k most relevant stored memories for the current query."""
    try:
        docs = vectorstore.similarity_search(user_input, k=k)
        return "\n".join(d.page_content for d in docs) if docs else ""
    except Exception as e:
        print(f"⚠️ Memory retrieval error: {e}")
        return ""

def _extract_and_store_facts(user_input: str, assistant_reply: str) -> None:
    """Background task to extract durable personal facts and store in Chroma."""
    prompt = (
        "Extract all important personal facts about the user from this exchange.\n"
        "Return each fact on its own line starting with 'FACT:'.\n"
        "Only include durable information (name, preferences, habits, goals).\n"
        "If there are no facts, return nothing.\n\n"
        f"User: {user_input}\nAssistant: {assistant_reply}\nFacts:"
    )
    try:
        facts_raw = llm.invoke(prompt).content
        for line in facts_raw.splitlines():
            line = line.strip()
            if line.startswith("FACT:"):
                fact = line[5:].strip()
                if fact:
                    vectorstore.add_documents([Document(page_content=fact)])
    except Exception:
        pass 

# -------------------------------------------------------------------
# 4. Tool definitions
# -------------------------------------------------------------------

def get_current_time(input: str = "") -> str:
    """Return the exact current date and time."""
    return datetime.now().strftime("%A, %d %B %Y, %H:%M:%S")

def get_weather(location: str = DEFAULT_CITY) -> str:
    """Get the current weather for a city using wttr.in."""
    try:
        resp = requests.get(f"https://wttr.in/{location}?format=%C+%t&u", timeout=5)
        resp.raise_for_status() 
        return f"Weather in {location}: {resp.text.strip()}"
    except RequestException as e: 
        return f"Weather service unavailable: {e}"

# ── Google Calendar & Gmail ────────────────────────────────────────
if GOOGLE_AVAILABLE:
    _SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/gmail.send",
    ]

    def _get_google_creds():
        creds = None
        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as f:
                creds = pickle.load(f)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists("credentials.json"):
                    raise FileNotFoundError(
                        "credentials.json not found. "
                        "Download it from Google Cloud Console and place it here."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", _SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open("token.pickle", "wb") as f:
                pickle.dump(creds, f)
        return creds

    def add_calendar_event(
        summary: str, start_time: str, end_time: str, description: str = ""
    ) -> str:
        """Add an event to Google Calendar. start/end in ISO format: YYYY-MM-DDTHH:MM:SS"""
        try:
            service = build("calendar", "v3", credentials=_get_google_creds())
            event = {
                "summary": summary,
                "description": description,
                "start": {"dateTime": start_time, "timeZone": TIMEZONE},
                "end":   {"dateTime": end_time,   "timeZone": TIMEZONE},
            }
            created = service.events().insert(
                calendarId="primary", body=event
            ).execute()
            return f"Event created: {created.get('htmlLink')}"
        except Exception as e:
            return f"Calendar error: {e}"

    def get_upcoming_events(max_results: int = 5) -> str:
        """Return the next upcoming Google Calendar events."""
        try:
            service = build("calendar", "v3", credentials=_get_google_creds())
            now = datetime.utcnow().isoformat() + "Z"
            result = service.events().list(
                calendarId="primary", timeMin=now,
                maxResults=max_results, singleEvents=True,
                orderBy="startTime",
            ).execute()
            items = result.get("items", [])
            if not items:
                return "No upcoming events."
            return "\n".join(
                f"{e['start'].get('dateTime', e['start'].get('date'))}: {e['summary']}"
                for e in items
            )
        except Exception as e:
            return f"Calendar error: {e}"

    def send_email(to: str, subject: str, body: str) -> str:
        """Send an email via Gmail."""
        try:
            service = build("gmail", "v1", credentials=_get_google_creds())
            raw = base64.urlsafe_b64encode(
                f"To: {to}\r\nSubject: {subject}\r\n\r\n{body}".encode()
            ).decode()
            service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()
            return f"Email sent to {to}."
        except Exception as e:
            return f"Email error: {e}"

    google_tools = [add_calendar_event, get_upcoming_events, send_email]
else:
    print("⚠ Google API libraries not installed — Calendar/Email tools disabled.")
    google_tools = []

# ── Smart Home (Home Assistant) ────────────────────────────────────
HA_URL   = os.getenv("HA_URL",   "")
HA_TOKEN = os.getenv("HA_TOKEN", "")

def _call_ha_service(domain: str, service: str, entity_id: str, **kwargs) -> str:
    if not HA_URL or not HA_TOKEN:
        return "Home Assistant not configured (set HA_URL and HA_TOKEN in .env)."
    try:
        resp = requests.post(
            f"{HA_URL}/api/services/{domain}/{service}",
            headers={
                "Authorization": f"Bearer {HA_TOKEN}",
                "content-type": "application/json",
            },
            json={"entity_id": entity_id, **kwargs},
            timeout=5,
        )
        resp.raise_for_status() 
        return f"Success: {service} {entity_id}"
    except RequestException as e: 
        return f"Home Assistant error: Connection or timeout issue - {e}"

def turn_on_light(entity: str) -> str:
    """Turn on a light entity, e.g. 'light.living_room_lamp'"""
    return _call_ha_service("light", "turn_on", entity)

def turn_off_light(entity: str) -> str:
    """Turn off a light entity, e.g. 'light.living_room_lamp'"""
    return _call_ha_service("light", "turn_off", entity)

def set_thermostat(entity: str, temperature: float) -> str:
    """Set a thermostat temperature, e.g. entity='climate.living_room', temperature=22.5"""
    return _call_ha_service("climate", "set_temperature", entity, temperature=temperature)

home_tools = [turn_on_light, turn_off_light, set_thermostat] if HA_URL else []

# -------------------------------------------------------------------
# 5. Assemble tool list
# -------------------------------------------------------------------
ALL_TOOLS = [get_current_time, get_weather] + google_tools + home_tools

# -------------------------------------------------------------------
# 6. Friday's system prompt
# -------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are Friday, a highly intelligent, articulate AI assistant inspired by Tony Stark's systems.\n"
    "You address the user as 'Sir' unless you know their name.\n"
    "You speak with a subtle British wit, are efficient, proactive, and never break character.\n"
    "You have access to tools — use them silently and weave results naturally into your reply.\n"
    "Do not acknowledge that you are an AI — you are Friday, a living, thinking presence.\n"
    "Keep responses concise unless the user asks for detail.\n"
    "Never use markdown, bullet points, or formatting symbols — output clean spoken prose only."
)

# -------------------------------------------------------------------
# 7. Agent + conversation checkpointer
# -------------------------------------------------------------------
checkpointer = InMemorySaver()

agent = create_react_agent(
    model=llm,
    tools=ALL_TOOLS,
    state_modifier=SYSTEM_PROMPT, # FIX: Confirmed modern syntax for LangGraph >= 0.2.0
    checkpointer=checkpointer,
)

# -------------------------------------------------------------------
# 8. Connection health check
# -------------------------------------------------------------------
_ollama_available: bool | None = None

def check_connection() -> bool:
    """Return True if Ollama is reachable. Caches the result."""
    global _ollama_available
    if _ollama_available is not None:
        return _ollama_available
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        _ollama_available = resp.status_code == 200
    except RequestException: 
        _ollama_available = False
    return _ollama_available

def _reset_connection() -> None:
    """Force a fresh connection check on the next call."""
    global _ollama_available
    _ollama_available = None

# -------------------------------------------------------------------
# 9. Public API — imported and called by server.py
# -------------------------------------------------------------------

def ask_friday(user_input: str, thread_id: str = "main_user") -> str:
    """Send a user message to the Friday agent and return its text reply."""
    if not check_connection():
        return "My brain is offline, Sir. Please ensure Ollama is running."

    try:
        memories = get_relevant_memories(user_input)
        if memories:
            augmented = f"[Relevant memory]\n{memories}\n\n[Query]\n{user_input}"
        else:
            augmented = user_input

        response = agent.invoke(
            {"messages": [{"role": "user", "content": augmented}]},
            config={"configurable": {"thread_id": thread_id}},
        )

        reply = response["messages"][-1].content

        if isinstance(reply, list):
            reply = " ".join(
                block.get("text", "")
                for block in reply
                if isinstance(block, dict) and block.get("type") == "text"
            )

        reply = reply.strip()
        if not reply:
            return "I didn't quite catch that, Sir. Could you rephrase?"

        threading.Thread(
            target=_extract_and_store_facts,
            args=(user_input, reply),
            daemon=True,
        ).start()

        return reply

    except Exception as e:
        _reset_connection()
        print(f"❌ Agent error: {e}")
        return "I encountered an error, Sir. Please try again."

def morning_briefing() -> str:
    """Build and return a spoken morning briefing string."""
    weather = get_weather(DEFAULT_CITY)
    if GOOGLE_AVAILABLE:
        try:
            events = get_upcoming_events(max_results=3)
        except Exception:
            events = "Calendar unavailable."
    else:
        events = "Calendar not configured."
    return f"Good morning Sir. {weather}. Today you have: {events}"

# -------------------------------------------------------------------
# 10. Standalone text mode  →  python brain.py
# -------------------------------------------------------------------
if __name__ == "__main__":
    if not check_connection():
        print(f"❌ Ollama not detected at {OLLAMA_BASE_URL}. Is it running?")
        sys.exit(1)

    print("\n🤖 Friday is online. Type 'exit' to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nFriday: Goodbye, Sir.")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "goodbye"}:
            print("Friday: Goodbye, Sir.")
            break

        reply = ask_friday(user_input)
        print(f"Friday: {reply}\n")