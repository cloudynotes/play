from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List
import uuid
import json
from game_logic import Game

app = FastAPI(title="Multiplayer Game")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage
rooms: Dict[str, Dict] = {}
connections: Dict[str, List[WebSocket]] = {}

class Player(BaseModel):
    name: str

class Room(BaseModel):
    name: str

@app.post("/room")
async def create_room(player: Player):
    room_id = str(uuid.uuid4())[:5]
    player_id = str(uuid.uuid4())[:8]
    rooms[room_id] = {
        "players": [{
            "id": player_id,
            "name": player.name,
            "role": "admin"
        }],
        "status": "waiting"
    }
    
    # Broadcast to existing connections (if any)
    if room_id in connections:
        message = {"type": "room_created", "admin_name": player.name}
        for ws in connections[room_id][:]:
            try:
                await ws.send_text(json.dumps(message))
            except:
                connections[room_id].remove(ws)
    
    return {"room_id": room_id, "player_id": player_id}

@app.post("/rooms/{room_id}/join")
async def join_room(room_id: str, player: Player):
    if room_id not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if rooms[room_id]["status"] == "started":
        raise HTTPException(status_code=400, detail="Game already started")
    
    if len(rooms[room_id]["players"]) >= 10:
        raise HTTPException(status_code=400, detail="Room is full")
    
    player_id = str(uuid.uuid4())[:8]
    rooms[room_id]["players"].append({
        "id": player_id,
        "name": player.name,
        "role": "player"
    })
    
    # Debug: Print connections
    print(f"Room {room_id} has {len(connections.get(room_id, []))} connections")
    
    # Broadcast to ALL connections in the room
    if room_id in connections and connections[room_id]:
        message = {"type": "player_joined", "player_name": player.name}
        print(f"Broadcasting to {len(connections[room_id])} connections")
        for ws in connections[room_id][:]:
            try:
                await ws.send_text(json.dumps(message))
                print(f"Sent message to WebSocket")
            except Exception as e:
                print(f"Failed to send message: {e}")
                connections[room_id].remove(ws)
    
    return {"player_id": player_id, "room_id": room_id}

@app.get("/rooms")
def list_rooms():
    return [{"id": rid, **room} for rid, room in rooms.items()]

@app.get("/rooms/{room_id}")
def get_room(room_id: str):
    if room_id not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"id": room_id, **rooms[room_id]}

@app.post("/rooms/{room_id}/start")
async def start_game(room_id: str, player_id: str):
    if room_id not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    
    admin = next((p for p in rooms[room_id]["players"] if p["id"] == player_id and p["role"] == "admin"), None)
    if not admin:
        raise HTTPException(status_code=403, detail="Only admin can start the game")
    
    game = Game(room_id, rooms[room_id]["players"])
    player_cards = game.start_game()
    
    rooms[room_id]["status"] = "started"
    rooms[room_id]["game"] = game
    rooms[room_id]["player_cards"] = player_cards
    
    # Broadcast game start to all players
    print(f"Starting game for room {room_id} with {len(connections.get(room_id, []))} connections")
    if room_id in connections and connections[room_id]:
        message = {"type": "game_started", "player_cards": player_cards}
        print(f"Broadcasting game start to {len(connections[room_id])} connections")
        for ws in connections[room_id][:]:
            try:
                await ws.send_text(json.dumps(message))
                print(f"Sent game start message to WebSocket")
            except Exception as e:
                print(f"Failed to send game start message: {e}")
                connections[room_id].remove(ws)
    else:
        print(f"No connections found for room {room_id}")
    
    return {"message": "Game started", "room_id": room_id}

@app.websocket("/ws/{room_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_id: str):
    await websocket.accept()
    
    if room_id not in connections:
        connections[room_id] = []
    connections[room_id].append(websocket)
    print(f"WebSocket connected for room {room_id}, player {player_id}, total connections: {len(connections[room_id])}")
    
    try:
        while True:
            data = await websocket.receive_text()
            print(f"Received WebSocket message: {data}")
    except Exception as e:
        print(f"WebSocket disconnected for player {player_id}: {e}")
        if websocket in connections[room_id]:
            connections[room_id].remove(websocket)
            print(f"Removed WebSocket, remaining connections: {len(connections[room_id])}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)