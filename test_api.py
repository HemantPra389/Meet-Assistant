import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def test_api():
    print("Testing GET /bots...")
    try:
        resp = requests.get(f"{BASE_URL}/bots")
        resp.raise_for_status()
        bots = resp.json()
        print("Bots:", bots)
        
        # Find bot-1
        bot1 = next(b for b in bots if b["id"] == "bot-1")
        print("Bot-1 Status:", bot1["status"])
        
        print("\nTesting POST /bots/bot-1/signin...")
        resp = requests.post(f"{BASE_URL}/bots/bot-1/signin")
        resp.raise_for_status()
        print("Signin Response:", resp.json())
        
        print("\nChecking status update (poll for a few seconds)...")
        for _ in range(3):
            time.sleep(1)
            resp = requests.get(f"{BASE_URL}/bots")
            bots = resp.json()
            bot1 = next(b for b in bots if b["id"] == "bot-1")
            print(f"Bot-1 Status: {bot1['status']}")
            
    except Exception as e:
        print(f"Test Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_api()
