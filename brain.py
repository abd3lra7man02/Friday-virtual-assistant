# brain.py – Friday, the fully‑featured AI assistant (LangGraph + OpenAI)
import os
import sys
import json
import base64
import threading
import time
from datetime import datetime
from dotenv import load_dotenv
import requests
from langchain_ollama import ChatOllama

# -------------------------------------------------------------------
# Optional imports – will fail gracefully if not installed
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

# Core LangChain / LangGraph
#from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings   # FREE local embeddings
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents import create_agent

# Chroma for long‑term memory
from langchain_chroma import Chroma
from langchain_core.documents import Document

# -------------------------------------------------------------------
# 1. Load environment & setup
# -------------------------------------------------------------------
load_dotenv()

# Configuration
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Cairo")
TIMEZONE = os.getenv("TIMEZONE", "Africa/Cairo")

# -------------------------------------------------------------------
# 2. Core LLM (OpenAI – you can switch to Ollama if API quota runs out)
# -------------------------------------------------------------------
llm = ChatOllama(
    model = "qwen3.5:0.8b",
    temperature=0.7,
)

# -------------------------------------------------------------------
# 3. Long‑term memory with Chroma (uses FREE local embeddings)
# -------------------------------------------------------------------
# IMPORTANT: Install Ollama (https://ollama.com) and run:
#   ollama pull nomic-embed-text
# Then use that model for zero‑cost embeddings.
embeddings = OllamaEmbeddings(model="nomic-embed-text")

vectorstore = Chroma(
    collection_name="friday_memory",
    embedding_function=embeddings,
    persist_directory="./friday_chroma_db",
)

def extract_and_store_facts(user_input: str, assistant_reply: str):
    """Extract personal facts from the latest exchange and store them."""
    extraction_prompt = f"""Extract all important personal facts about the user from this exchange.
Return each fact as a separate line starting with 'FACT:'.

User: {user_input}
Assistant: {assistant_reply}
Facts:"""
    try:
        facts_raw = llm.invoke(extraction_prompt).content
        for line in facts_raw.splitlines():
            line = line.strip()
            if line.startswith("FACT:"):
                fact_text = line.replace("FACT:", "").strip()
                vectorstore.add_documents([Document(page_content=fact_text)])
    except Exception:
        pass  # Don't break conversation if fact extraction fails

def get_relevant_memories(user_input: str, k: int = 3) -> str:
    """Retrieve the most relevant memories for the user's input."""
    docs = vectorstore.similarity_search(user_input, k=k)
    if not docs:
        return ""
    return "\n".join([d.page_content for d in docs])

# -------------------------------------------------------------------
# 4. Tool definitions
# -------------------------------------------------------------------

# ---------- Time & Weather ----------
def get_current_time(input: str = "") -> str:
    """Return the exact current date and time."""
    now = datetime.now()
    return now.strftime("%A, %d %B %Y, %H:%M:%S")

def get_weather(location: str = DEFAULT_CITY) -> str:
    """Get the current weather for a city."""
    url = f"https://wttr.in/{location}?format=%C+%t&u"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return f"Weather in {location}: {resp.text.strip()}"
        else:
            return f"Could not fetch weather for {location} (HTTP {resp.status_code})"
    except Exception as e:
        return f"Weather service unavailable: {e}"

# ---------- Google Calendar & Gmail (requires credentials.json) ----------
if GOOGLE_AVAILABLE:
    SCOPES = ['https://www.googleapis.com/auth/calendar',
              'https://www.googleapis.com/auth/gmail.send']

    def _get_google_creds():
        """Authenticate and return valid Google credentials."""
        creds = None
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        return creds

    def add_calendar_event(summary: str, start_time: str, end_time: str, description: str = "") -> str:
        """Add an event to Google Calendar. start_time/end_time in ISO format: 'YYYY-MM-DDTHH:MM:SS'"""
        creds = _get_google_creds()
        service = build('calendar', 'v3', credentials=creds)
        event = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_time, 'timeZone': TIMEZONE},
            'end': {'dateTime': end_time, 'timeZone': TIMEZONE},
        }
        event = service.events().insert(calendarId='primary', body=event).execute()
        return f"Event created: {event.get('htmlLink')}"

    def get_upcoming_events(max_results: int = 5) -> str:
        """Return the next few upcoming Google Calendar events."""
        creds = _get_google_creds()
        service = build('calendar', 'v3', credentials=creds)
        now = datetime.utcnow().isoformat() + 'Z'
        events_result = service.events().list(
            calendarId='primary', timeMin=now,
            maxResults=max_results, singleEvents=True,
            orderBy='startTime').execute()
        events = events_result.get('items', [])
        if not events:
            return "No upcoming events."
        result = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            result.append(f"{start}: {event['summary']}")
        return "\n".join(result)

    def send_email(to: str, subject: str, body: str) -> str:
        """Send an email via Gmail."""
        creds = _get_google_creds()
        service = build('gmail', 'v1', credentials=creds)
        message = f"To: {to}\r\nSubject: {subject}\r\n\r\n{body}"
        raw = base64.urlsafe_b64encode(message.encode()).decode()
        sent = service.users().messages().send(userId="me", body={'raw': raw}).execute()
        return f"Email sent to {to}."

    google_tools = [add_calendar_event, get_upcoming_events, send_email]
else:
    print("⚠ Google API libraries not installed. Calendar/Email tools disabled.")
    google_tools = []

# ---------- Smart Home (Home Assistant) ----------
HA_URL = os.getenv("HA_URL", "")
HA_TOKEN = os.getenv("HA_TOKEN", "")

def _call_ha_service(domain: str, service: str, entity_id: str, **kwargs):
    if not HA_URL or not HA_TOKEN:
        return "Home Assistant is not configured (set HA_URL and HA_TOKEN in .env)."
    url = f"{HA_URL}/api/services/{domain}/{service}"
    headers = {"Authorization": f"Bearer {HA_TOKEN}", "content-type": "application/json"}
    data = {"entity_id": entity_id}
    data.update(kwargs)
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code == 200:
        return f"Success: {service} {entity_id}"
    else:
        return f"Failed: {resp.text}"

def turn_on_light(entity: str) -> str:
    """Turn on a light entity, e.g. 'light.living_room_lamp'"""
    return _call_ha_service("light", "turn_on", entity)

def turn_off_light(entity: str) -> str:
    """Turn off a light entity."""
    return _call_ha_service("light", "turn_off", entity)

def set_thermostat(entity: str, temperature: float) -> str:
    """Set a thermostat to a given temperature, e.g. 'climate.living_room' to 22.5"""
    return _call_ha_service("climate", "set_temperature", entity, temperature=temperature)

home_tools = [turn_on_light, turn_off_light, set_thermostat] if HA_URL else []

# -------------------------------------------------------------------
# 5. Assemble all tools
# -------------------------------------------------------------------
ALL_TOOLS = [
    get_current_time,
    get_weather,
] + google_tools + home_tools

# -------------------------------------------------------------------
# 6. Friday’s personality
# -------------------------------------------------------------------
SYSTEM_PROMPT = """You are Friday, a highly intelligent, articulate AI assistant inspired by Tony Stark's systems.
You address the user as "Sir" (unless you know their name).
You speak with a subtle British wit, are efficient, proactive, and never break character.
You have access to tools; use them silently and incorporate the results naturally.
Do not mention you are an AI – you are Friday, a living, thinking presence.
Keep responses concise unless elaboration is requested."""

# -------------------------------------------------------------------
# 7. Agent with checkpointing
# -------------------------------------------------------------------
checkpointer = InMemorySaver()
agent = create_agent(
    model=llm,
    tools=ALL_TOOLS,
    system_prompt=SYSTEM_PROMPT,
    checkpointer=checkpointer,
)

# This config is used to keep conversation history across turns (thread "main_user")
config = {"configurable": {"thread_id": "main_user"}}

# -------------------------------------------------------------------
# 8. Proactive morning briefing (background thread)
# -------------------------------------------------------------------
def morning_briefing():
    """Gather today's data and print (or speak) a brief summary."""
    weather = get_weather(DEFAULT_CITY)
    events = "No calendar access."
    if GOOGLE_AVAILABLE:
        try:
            events = get_upcoming_events(max_results=3)
        except Exception:
            events = "Calendar unavailable."
    briefing = f"Good morning Sir. {weather}. Today you have: {events}"
    print("\n[Proactive Briefing]", briefing)
    # Optionally trigger TTS – here we just print, but you can add an asyncio call

# -------------------------------------------------------------------
# 9. Import guard – only run the following when executed directly
# -------------------------------------------------------------------
if __name__ == "__main__":
    if SCHEDULE_AVAILABLE:
        schedule.every().day.at("07:00").do(morning_briefing)

        def scheduler_loop():
            while True:
                schedule.run_pending()
                time.sleep(30)

        threading.Thread(target=scheduler_loop, daemon=True).start()
        print("⌛ Proactive scheduler started (daily briefing at 07:00).")
    else:
        print("⚠ 'schedule' not installed – proactive briefings disabled. Install with: pip install schedule")

    print("\n🤖 Friday is online. Type 'exit' to quit.")

    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Friday: Goodbye, Sir.")
            break

        # Retrieve long‑term memories
        memories = get_relevant_memories(user_input)
        memory_context = ""
        if memories:
            memory_context = f"Relevant personal memories:\n{memories}"

        # Build input messages
        input_messages = []
        if memory_context:
            input_messages.append({"role": "system", "content": memory_context})
        input_messages.append({"role": "user", "content": user_input})

        # Get Friday’s response
        response = agent.invoke(
            {"messages": input_messages},
            config=config,
        )
        reply = response["messages"][-1].content
        print(f"Friday: {reply}")

        # Store new facts in the background (ignore errors)
        def extract_and_store_facts(user_input: str, assistant_response: str):
            # Use the same small model you have
            llm = ChatOllama(model="qwen3.5:0.8b", temperature=0)
    ...