import requests
import sys

BASE_URL = "http://localhost:8000"
MEETING_URL = "https://meet.google.com/huv-veqw-wee"

def test_join_api():
    print("Testing POST /bots/bot-1/join...")
    try:
        payload = {"meeting_url": MEETING_URL}
        resp = requests.post(f"{BASE_URL}/bots/bot-1/join", json=payload)
        
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"Request failed with {e}")
            print("Response:", resp.text)
            sys.exit(1)

        data = resp.json()
        print("Response:", data)
        
        if data["meeting_url"] == MEETING_URL:
            print("SUCCESS: Endpoint returned correct meeting URL.")
        else:
            print("FAILURE: Endpoint returned incorrect meeting URL.")
            
    except Exception as e:
        print(f"Test Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_join_api()
