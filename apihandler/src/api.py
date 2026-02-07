from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import sys
import os
import subprocess
import threading
import uuid

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

# Active Bot Processes (to keep track of subprocesses)
ACTIVE_BOT_PROCESSES = {}

# --- Background Tasks ---

def run_manual_signin_flow(bot_id: str, email: str):
    """
    Executes the MeetBot manual sign-in flow via CLI in a separate process.
    Updates the global BOTS_DB state based on outcome.
    """
    logger.info(f"Starting background sign-in for {bot_id} ({email})")
    
    # Update state
    if bot_id in BOTS_DB:
        BOTS_DB[bot_id]["status"] = BotStatus.LOGIN_IN_PROGRESS

    auth_dir = os.path.join(os.getcwd(), "user_data", bot_id)
    
    # Construct command
    # Assuming running from project root or /app in Docker
    # Path to main.py
    script_path = os.path.join("meetbot", "src", "main.py")
    if not os.path.exists(script_path):
         # Fallback if running from a different context, but strict separation implies standardized paths
         logger.error(f"Could not find bot script at {script_path}")
         return

    cmd = [
        sys.executable, "-u", script_path,
        "--signin",
        "--auth-dir", auth_dir
    ]
    
    try:
        logger.info(f"Running command: {' '.join(cmd)}")
        # Run synchronous for signin (it waits for user interaction)
        # In a real async architecture we might mistakenly block the thread pool, 
        # but BackgroundTasks runs in a thread pool so it's okay.
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode == 0:
            if bot_id in BOTS_DB:
                BOTS_DB[bot_id]["status"] = BotStatus.LOGGED_IN
            logger.info(f"Sign-in SUCCESS for {bot_id}")
        else:
            logger.error(f"Sign-in FAILED for {bot_id}. Exit code: {process.returncode}")
            logger.error(f"Stdout: {process.stdout}")
            logger.error(f"Stderr: {process.stderr}")
            if bot_id in BOTS_DB:
                BOTS_DB[bot_id]["status"] = BotStatus.LOGIN_REQUIRED
        
    except Exception as e:
        logger.error(f"Sign-in process FAILED for {bot_id}: {e}")
        if bot_id in BOTS_DB:
            BOTS_DB[bot_id]["status"] = BotStatus.LOGIN_REQUIRED

def run_meeting_bot(bot_id: str, meeting_url: str, auth_dir: str):
    """
    Executes the MeetBot join meeting flow via CLI in a separate process.
    Updates the global BOTS_DB state based on outcome.
    """
    logger.info(f"Starting meeting bot for {bot_id} (URL: {meeting_url})")
    
    # Update state
    if bot_id in BOTS_DB:
        BOTS_DB[bot_id]["status"] = BotStatus.IN_MEETING

    script_path = os.path.join("meetbot", "src", "main.py")
    
    cmd = [
        sys.executable, "-u", script_path,
        "--meeting-url", meeting_url,
        "--auth-dir", auth_dir
        # No --headless flag passed, so it defaults to False (Headful) as requested by logic
    ]

    try:
        logger.info(f"Running command: {' '.join(cmd)}")
        
        # Popen allows us to keep track of it if needed
        process = subprocess.Popen(
            cmd,
            stdout=sys.stdout, # Stream to main log for now
            stderr=sys.stderr
        )
        
        ACTIVE_BOT_PROCESSES[bot_id] = process
        
        # Wait for completion (blocking this thread in the pool)
        exit_code = process.wait()
        
        logger.info(f"Meeting ended for {bot_id} (Exit code: {exit_code})")
        
    except Exception as e:
        logger.error(f"Meeting bot {bot_id} execution FAILED: {e}")
    finally:
        if bot_id in ACTIVE_BOT_PROCESSES:
            del ACTIVE_BOT_PROCESSES[bot_id]

        if bot_id in BOTS_DB:
            # Revert status
            BOTS_DB[bot_id]["status"] = BotStatus.LOGGED_IN # Default safe state


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
