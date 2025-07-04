from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List
import uuid
import json
import os
from game_logic import Game

app = FastAPI(title="6 Nimmt!")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory
app.mount("/static", StaticFiles(directory="front"), name="static")

# Root path to serve index.html
@app.get("/")
async def read_root():
    return FileResponse("front/index.html")

# Join room page
@app.get("/join/{room_id}")
async def join_page(room_id: str):
    if room_id not in rooms:
        return {"error": "Room not found"}
    return FileResponse("front/index.html")

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
    
    # Return with redirect URL
    return {"room_id": room_id, "player_id": player_id, "redirect_url": f"/join/{room_id}"}

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
    game_data = game.start_game()
    
    rooms[room_id]["status"] = "started"
    rooms[room_id]["game"] = game
    rooms[room_id]["player_cards"] = game_data["player_cards"]
    rooms[room_id]["shared_cards"] = game_data["shared_cards"]
    rooms[room_id]["player_points"] = game_data["player_points"]
    rooms[room_id]["shared_piles"] = game_data["shared_piles"]
    rooms[room_id]["current_round"] = 1
    
    # Broadcast game start to all players
    print(f"Starting game for room {room_id} with {len(connections.get(room_id, []))} connections")
    if room_id in connections and connections[room_id]:
        # Initialize player status - all thinking at start
        player_status = {}
        for player in rooms[room_id]["players"]:
            player_status[player["id"]] = {
                "name": player["name"],
                "status": "thinking"
            }
        
        message = {"type": "game_started", "player_cards": game_data["player_cards"], "shared_cards": game_data["shared_cards"], "player_points": game_data["player_points"], "shared_piles": game_data["shared_piles"], "current_round": 1, "player_status": player_status}
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
    
    # Add connection to room
    if room_id not in connections:
        connections[room_id] = []
    connections[room_id].append(websocket)
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        # Remove connection when client disconnects
        if room_id in connections:
            connections[room_id].remove(websocket)

@app.post("/rooms/{room_id}/select")
async def select_card(room_id: str, player_id: str, card: int):
    if room_id not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    
    if rooms[room_id]["status"] != "started":
        raise HTTPException(status_code=400, detail="Game not started")
    
    game = rooms[room_id]["game"]
    if game.select_card(player_id, card):
        rooms[room_id]["player_cards"] = game.player_cards
        rooms[room_id]["current_round"] = game.current_round
        
        # Check if round is complete
        if game.check_round_complete():
            round_results = game.get_round_results(game.current_round)
            
            # Place cards on shared piles (sequential processing)
            placement_results = game.place_cards_on_piles(round_results)
            rooms[room_id]["shared_piles"] = game.shared_piles
            rooms[room_id]["player_points"] = game.player_points
            
            # Check if penalty resolution is needed
            penalty_needed = any(result["action"] == "penalty_required" for result in placement_results)
            
            # Broadcast round results
            if room_id in connections and connections[room_id]:
                # Get player status - check for penalty needed
                player_status = {}
                for player in rooms[room_id]["players"]:
                    pid = player["id"]
                    # Check if this player needs to resolve penalty
                    needs_penalty = any(result["action"] == "penalty_required" and result["player_id"] == pid for result in placement_results)
                    player_status[pid] = {
                        "name": player["name"],
                        "status": "penalty" if needs_penalty else "played"
                    }
                
                message = {
                    "type": "round_complete", 
                    "round": game.current_round,
                    "results": round_results,
                    "player_cards": game.player_cards,
                    "last_selected": game.player_last_card,
                    "shared_piles": game.shared_piles,
                    "player_points": game.player_points,
                    "placement_results": placement_results,
                    "penalty_needed": penalty_needed,
                    "player_status": player_status
                }
                for ws in connections[room_id][:]:
                    try:
                        await ws.send_text(json.dumps(message))
                    except Exception as e:
                        connections[room_id].remove(ws)
            
            # Only move to next round if no penalty is needed
            if not penalty_needed:
                # Broadcast round finished message
                if room_id in connections and connections[room_id]:
                    finish_message = {
                        "type": "round_finished",
                        "round": game.current_round,
                        "message": f"Round {game.current_round} is finished! Ready for next round."
                    }
                    for ws in connections[room_id][:]:
                        try:
                            await ws.send_text(json.dumps(finish_message))
                        except Exception as e:
                            connections[room_id].remove(ws)
                
                if game.next_round():
                    rooms[room_id]["current_round"] = game.current_round
                    # Broadcast round end with reset player status
                    if room_id in connections and connections[room_id]:
                        # Reset all players to thinking for new round
                        reset_player_status = {}
                        for player in rooms[room_id]["players"]:
                            reset_player_status[player["id"]] = {
                                "name": player["name"],
                                "status": "thinking"
                            }
                        
                        end_message = {"type": "round_ended", "next_round": game.current_round, "player_status": reset_player_status}
                        for ws in connections[room_id][:]:
                            try:
                                await ws.send_text(json.dumps(end_message))
                            except Exception as e:
                                connections[room_id].remove(ws)
                else:
                    rooms[room_id]["status"] = "finished"
        else:
            # Broadcast card selection with player status
            if room_id in connections and connections[room_id]:
                # Get player status for current round
                player_status = {}
                for player in rooms[room_id]["players"]:
                    pid = player["id"]
                    has_played = game.player_round_status.get(pid, False)
                    player_status[pid] = {
                        "name": player["name"],
                        "status": "played" if has_played else "thinking"
                    }
                
                message = {
                    "type": "card_selected", 
                    "player_id": player_id, 
                    "card": card, 
                    "round": game.current_round,
                    "player_cards": game.player_cards,
                    "last_selected": game.player_last_card,
                    "player_status": player_status
                }
                for ws in connections[room_id][:]:
                    try:
                        await ws.send_text(json.dumps(message))
                    except Exception as e:
                        connections[room_id].remove(ws)
        
        return {"message": "Card selected", "card": card, "round": game.current_round}
    else:
        raise HTTPException(status_code=400, detail="Card already selected this round or invalid card")

@app.post("/rooms/{room_id}/take_pile")
async def take_pile(room_id: str, player_id: str, pile_idx: int, low_card: int):
    if room_id not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    
    game = rooms[room_id]["game"]
    penalty_points, taken_cards = game.take_pile(player_id, pile_idx, low_card)
    
    rooms[room_id]["shared_piles"] = game.shared_piles
    rooms[room_id]["player_points"] = game.player_points
    
    # Continue processing remaining cards
    round_results = game.get_round_results(game.current_round)
    remaining_placement = game.continue_card_placement(round_results)
    
    # Check if more penalties needed
    more_penalties = any(result["action"] == "penalty_required" for result in remaining_placement)
    
    # Check if all cards are now processed (round complete)
    round_results = game.get_round_results(game.current_round)
    all_cards_processed = len(game.processed_cards) == len(round_results)
    
    # Broadcast pile taken and continue processing
    if room_id in connections and connections[room_id]:
        message = {
            "type": "pile_taken",
            "player_id": player_id,
            "pile_idx": pile_idx,
            "penalty_points": penalty_points,
            "taken_cards": taken_cards,
            "shared_piles": game.shared_piles,
            "player_points": game.player_points,
            "remaining_placement": remaining_placement,
            "more_penalties": more_penalties,
            "all_cards_processed": all_cards_processed,
            "current_round": game.current_round
        }
        for ws in connections[room_id][:]:
            try:
                await ws.send_text(json.dumps(message))
            except Exception as e:
                connections[room_id].remove(ws)
    
    # If all cards processed, move to next round
    if all_cards_processed and not more_penalties:
        # Broadcast round finished message
        if room_id in connections and connections[room_id]:
            finish_message = {
                "type": "round_finished",
                "round": game.current_round,
                "message": f"Round {game.current_round} is finished! Ready for next round."
            }
            for ws in connections[room_id][:]:
                try:
                    await ws.send_text(json.dumps(finish_message))
                except Exception as e:
                    connections[room_id].remove(ws)
        
        if game.next_round():
            rooms[room_id]["current_round"] = game.current_round
            # Broadcast round end with reset player status
            if room_id in connections and connections[room_id]:
                # Reset all players to thinking for new round
                reset_player_status = {}
                for player in rooms[room_id]["players"]:
                    reset_player_status[player["id"]] = {
                        "name": player["name"],
                        "status": "thinking"
                    }
                
                end_message = {"type": "round_ended", "next_round": game.current_round, "player_status": reset_player_status}
                for ws in connections[room_id][:]:
                    try:
                        await ws.send_text(json.dumps(end_message))
                    except Exception as e:
                        connections[room_id].remove(ws)
        else:
            rooms[room_id]["status"] = "finished"
    return {"message": "Pile taken", "penalty_points": penalty_points, "more_penalties": more_penalties}

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