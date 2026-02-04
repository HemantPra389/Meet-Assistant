from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sys
import os
import threading
import uuid

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bot import MeetBot
from src.logger import setup_logger

logger = setup_logger("api")


app = FastAPI()

# Enable CORS for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the exact origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- State Management (In-Memory for MVP) ---

class BotStatus:
    LOGGED_IN = "LOGGED_IN"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    LOGIN_IN_PROGRESS = "LOGIN_IN_PROGRESS"
    LOGGED_OUT = "LOGGED_OUT"
    IN_MEETING = "IN_MEETING"

class BotModel(BaseModel):
    id: str
    email: str
    status: str

class JoinMeetingRequest(BaseModel):
    meeting_url: str

# Mock Database
BOTS_DB = {
    "bot-1": {"id": "bot-1", "email": "hemantpra.techsaga@gmail.com", "status": BotStatus.LOGIN_REQUIRED},
    "bot-2": {"id": "bot-2", "email": "user2@company.com", "status": BotStatus.LOGGED_IN},
    "bot-3": {"id": "bot-3", "email": "user3@company.com", "status": BotStatus.LOGIN_IN_PROGRESS},
    "bot-4": {"id": "bot-4", "email": "admin@company.com", "status": BotStatus.LOGIN_REQUIRED},
}

# Active Bot Instances (to keep them alive if needed, though for signin we might stop them)
ACTIVE_BOTS = {}

# --- Background Tasks ---

def run_manual_signin_flow(bot_id: str, email: str):
    """
    Executes the MeetBot manual sign-in flow in a background thread.
    Updates the global BOTS_DB state based on outcome.
    """
    logger.info(f"Starting background sign-in for {bot_id} ({email})")
    
    # Update state
    if bot_id in BOTS_DB:
        BOTS_DB[bot_id]["status"] = BotStatus.LOGIN_IN_PROGRESS

    # Define unique auth dir for this bot to avoid collisions (or use a shared one if intended)
    # For this MVP, we'll assume a dedicated profile per bot ID
    auth_dir = os.path.join(os.getcwd(), "user_data", bot_id)
    
    # Initialize Bot (Force visible)
    # Note: MeetBot constructor expects (meeting_url, auth_dir, headless)
    # For signin, meeting_url can be dummy
    bot = MeetBot(meeting_url="https://meet.google.com", auth_dir=auth_dir, headless=False)
    
    try:
        # This blocks until success or timeout
        bot.start(bootstrap_signin=True)
        
        # If we reached here without exception, success
        if bot_id in BOTS_DB:
            BOTS_DB[bot_id]["status"] = BotStatus.LOGGED_IN
        logger.info(f"Sign-in SUCCESS for {bot_id}")
        
    except Exception as e:
        logger.error(f"Sign-in FAILED for {bot_id}: {e}")
        if bot_id in BOTS_DB:
            BOTS_DB[bot_id]["status"] = BotStatus.LOGIN_REQUIRED
    finally:
        # Cleanup is handled inside bot.start() -> stop(), but we made need to ensure it's closed
        # MeetBot.start(bootstrap_signin=True) calls perform_manual_signin which doesn't explicitly close browser if it returns normally?
        # Let's check bot.py. 
        # perform_manual_signin just does the work. 
        # bot.start calls perform_manual_signin. 
        # It does NOT call stop() automatically in start() unless exception?
        # Actually in main.py it just exits.
        # We should explicitly close the bot to free resources.
        try:
            bot.stop()
        except:
            pass

def run_meeting_bot(bot_id: str, meeting_url: str, auth_dir: str):
    """
    Executes the MeetBot join meeting flow in a background thread.
    Updates the global BOTS_DB state based on outcome.
    """
    logger.info(f"Starting meeting bot for {bot_id} (URL: {meeting_url})")
    
    # Update state
    if bot_id in BOTS_DB:
        BOTS_DB[bot_id]["status"] = BotStatus.IN_MEETING

    # Initialize Bot (Force visible as requested)
    bot = MeetBot(meeting_url=meeting_url, auth_dir=auth_dir, headless=False)
    
    # Store active bot reference so we can stop it later if needed (future improvement)
    ACTIVE_BOTS[bot_id] = bot

    try:
        # This blocks until meeting ends or error
        bot.start()
        
        logger.info(f"Meeting ended for {bot_id}")
        
    except Exception as e:
        logger.error(f"Meeting bot {bot_id} execution FAILED: {e}")
    finally:
        # Cleanup
        try:
            bot.stop()
        except:
            pass
        
        if bot_id in ACTIVE_BOTS:
            del ACTIVE_BOTS[bot_id]

        if bot_id in BOTS_DB:
            # We don't really know if they are logged out, but assuming back to required/ready state
            # For now, let's revert to LOGIN_REQUIRED if we don't track persistent login state perfectly,
            # or keep previous state. 
            # Simplest for this MVP:
            BOTS_DB[bot_id]["status"] = BotStatus.LOGGED_IN # Assuming success means they were logged in?
            # Or revert to what it was? 
            # Let's set to LOGGED_IN for now as a safe default after a meeting.



# --- API Endpoints ---

@app.get("/")
def read_root():
    return {"message": "Meet Assistant API is running. Go to /docs for Swagger UI."}

@app.get("/bots", response_model=List[BotModel])
def get_bots():
    return list(BOTS_DB.values())

@app.get("/bots/{bot_id}", response_model=BotModel)
def get_bot(bot_id: str):
    if bot_id not in BOTS_DB:
        raise HTTPException(status_code=404, detail="Bot not found")
    return BOTS_DB[bot_id]

@app.post("/bots/{bot_id}/signin")
def trigger_signin(bot_id: str, background_tasks: BackgroundTasks):
    if bot_id not in BOTS_DB:
        raise HTTPException(status_code=404, detail="Bot not found")
        
    bot_data = BOTS_DB[bot_id]
    
    # Trigger background task
    background_tasks.add_task(run_manual_signin_flow, bot_id, bot_data["email"])
    
    return {
        "message": "Sign-in process initiated. Check VNC.",
        # The frontend uses this URL to open a tab. 
        # Since we are doing server-side VNC login, we can't give a real client-side login URL.
        # We'll return a generic google account page or a placeholder.
        "login_url": "https://accounts.google.com/ServiceLogin", 
        "expires_in": 300
    }

@app.post("/bots/{bot_id}/join")
def trigger_join(bot_id: str, request: JoinMeetingRequest, background_tasks: BackgroundTasks):
    if bot_id not in BOTS_DB:
        raise HTTPException(status_code=404, detail="Bot not found")
        
    bot_data = BOTS_DB[bot_id]

    # Check if bot is already busy?
    if bot_data["status"] in [BotStatus.LOGIN_IN_PROGRESS, BotStatus.IN_MEETING]:
        # Optional: block new requests or just allow it (killing previous?)
        # For this MVP, we'll just allow it to spawn. 
        # Ideally we should stop the previous one.
        pass

    # Directory
    auth_dir = os.path.join(os.getcwd(), "user_data", bot_id)

    # Trigger background task
    background_tasks.add_task(run_meeting_bot, bot_id, request.meeting_url, auth_dir)
    
    return {
        "message": f"Bot {bot_id} is joining the meeting.",
        "meeting_url": request.meeting_url
    }

if __name__ == "__main__":
    print("API Module Loaded. Starting Uvicorn...")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
