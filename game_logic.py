import random
from typing import Dict, List

class Game:
    def __init__(self, room_id: str, players: List[Dict]):
        self.room_id = room_id
        self.players = players
        self.player_cards = {}
    
    def start_game(self):
        """Step 1: Give each player 10 unique random cards between 1-104"""
        # Create deck of all cards 1-104
        deck = list(range(1, 105))
        random.shuffle(deck)
        
        # Distribute 10 cards to each player and sort them
        for i, player in enumerate(self.players):
            start_idx = i * 10
            cards = deck[start_idx:start_idx + 10]
            self.player_cards[player["id"]] = sorted(cards)
        
        return self.player_cards