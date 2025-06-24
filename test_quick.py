import requests
import json

# Test API endpoints
base_url = "http://localhost:8000"

# Create room
response = requests.post(f"{base_url}/room", json={"name": "TestAdmin"})
room_data = response.json()
print(f"Room created: {room_data}")

# Join room
response = requests.post(f"{base_url}/rooms/{room_data['room_id']}/join", json={"name": "TestPlayer"})
join_data = response.json()
print(f"Player joined: {join_data}")

# Check room
response = requests.get(f"{base_url}/rooms/{room_data['room_id']}")
room_info = response.json()
print(f"Room info: {room_info}")