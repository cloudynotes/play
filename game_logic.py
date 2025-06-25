import random
from typing import Dict, List

class Game:
    def __init__(self, room_id: str, players: List[Dict]):
        self.room_id = room_id
        self.players = players
        self.player_cards = {}
        self.current_round = 1
        self.round_selections = {}  # {round: {player_id: card}}
        self.player_round_status = {}  # {player_id: has_selected_this_round}
        self.player_last_card = {}  # {player_id: last_selected_card}
        self.shared_piles = {0: [], 1: [], 2: [], 3: []}  # 4 piles next to shared cards
        self.player_points = {}  # {player_id: negative_points}
        self.pending_cards = []  # Cards waiting to be processed after penalty
        self.processed_cards = set()  # Cards already processed in current round
    
    def calculate_card_points(self, card):
        """Calculate negative points for a card"""
        if card == 55:
            return 7
        elif card % 11 == 0:  # multiples of 11 (except 55)
            return 5
        elif card % 10 == 0:  # multiples of 10
            return 3
        elif card % 5 == 0:  # multiples of 5 (not 10, not 55)
            return 2
        else:
            return 1
    
    def start_game(self):
        """Step 1: Give each player 10 unique random cards + 4 shared cards"""
        # Create deck of all cards 1-104
        deck = list(range(1, 105))
        random.shuffle(deck)
        
        # Distribute 10 cards to each player and sort them
        for i, player in enumerate(self.players):
            start_idx = i * 10
            cards = deck[start_idx:start_idx + 10]
            self.player_cards[player["id"]] = sorted(cards)
            # Initialize points to 0
            self.player_points[player["id"]] = 0
        
        # Get 4 shared cards from remaining deck
        used_cards = len(self.players) * 10
        self.shared_cards = sorted(deck[used_cards:used_cards + 4])
        
        # Initialize piles with shared cards
        for i, card in enumerate(self.shared_cards):
            self.shared_piles[i] = [card]
        
        return {"player_cards": self.player_cards, "shared_cards": self.shared_cards, "player_points": self.player_points, "shared_piles": self.shared_piles}
        
    def place_cards_on_piles(self, round_selections):
        """Place selected cards on shared piles starting from smallest"""
        # Get all selected cards sorted by value (smallest first)
        card_player_map = {card: player_id for player_id, card in round_selections.items()}
        selected_cards = sorted(round_selections.values())
        
        placement_results = []
        
        # Process each card from smallest to largest
        for card in selected_cards:
            player_id = card_player_map[card]
            
            if self.can_place_card(card):
                best_pile = self.find_best_pile(card)
                
                # Check if pile will have 6 cards (5 + new card)
                if len(self.shared_piles[best_pile]) == 5:
                    # Player must take the 5 cards, leave only the new card
                    taken_cards = self.shared_piles[best_pile].copy()
                    penalty_points = sum(self.calculate_card_points(c) for c in taken_cards)
                    self.player_points[player_id] += penalty_points
                    self.shared_piles[best_pile] = [card]  # Only new card remains
                    
                    self.processed_cards.add(card)
                    placement_results.append({
                        "player_id": player_id,
                        "card": card,
                        "action": "took_pile_6th",
                        "pile": best_pile,
                        "penalty_points": penalty_points,
                        "taken_cards": taken_cards
                    })
                else:
                    # Normal placement
                    self.shared_piles[best_pile].append(card)
                    self.processed_cards.add(card)
                    placement_results.append({
                        "player_id": player_id,
                        "card": card,
                        "action": "placed",
                        "pile": best_pile
                    })
            else:
                # Card too low - needs penalty resolution
                placement_results.append({
                    "player_id": player_id,
                    "card": card,
                    "action": "penalty_required"
                })
                # Stop processing until penalty is resolved
                break
        
        return placement_results
    
    def can_place_card(self, card):
        """Check if card can be placed on any pile incrementally"""
        for pile_idx in range(4):
            pile_top = self.get_pile_top(pile_idx)
            if card > pile_top:
                return True
        return False
    
    def get_pile_top(self, pile_idx):
        """Get the top card of a pile"""
        return self.shared_piles[pile_idx][-1] if self.shared_piles[pile_idx] else 0
    
    def take_pile(self, player_id: str, pile_idx: int, low_card: int):
        """Player takes a pile and gets penalty points"""
        # Calculate penalty points
        pile_cards = self.shared_piles[pile_idx].copy()
        penalty_points = sum(self.calculate_card_points(card) for card in pile_cards)
        
        # Add penalty to player
        self.player_points[player_id] += penalty_points
        
        # Clear the pile and place the low card
        self.shared_piles[pile_idx] = [low_card]
        
        # Mark the low card as processed
        self.processed_cards.add(low_card)
        
        return penalty_points, pile_cards
    
    def continue_card_placement(self, round_selections):
        """Continue placing remaining unprocessed cards"""
        # Get all selected cards sorted by value
        card_player_map = {card: player_id for player_id, card in round_selections.items()}
        selected_cards = sorted(round_selections.values())
        
        placement_results = []
        
        # Process only unprocessed cards from smallest to largest
        for card in selected_cards:
            if card in self.processed_cards:
                continue  # Skip already processed cards
                
            player_id = card_player_map[card]
            
            if self.can_place_card(card):
                best_pile = self.find_best_pile(card)
                
                # Check if pile will have 6 cards (5 + new card)
                if len(self.shared_piles[best_pile]) == 5:
                    # Player must take the 5 cards, leave only the new card
                    taken_cards = self.shared_piles[best_pile].copy()
                    penalty_points = sum(self.calculate_card_points(c) for c in taken_cards)
                    self.player_points[player_id] += penalty_points
                    self.shared_piles[best_pile] = [card]  # Only new card remains
                    
                    self.processed_cards.add(card)
                    placement_results.append({
                        "player_id": player_id,
                        "card": card,
                        "action": "took_pile_6th",
                        "pile": best_pile,
                        "penalty_points": penalty_points,
                        "taken_cards": taken_cards
                    })
                else:
                    # Normal placement
                    self.shared_piles[best_pile].append(card)
                    self.processed_cards.add(card)
                    placement_results.append({
                        "player_id": player_id,
                        "card": card,
                        "action": "placed",
                        "pile": best_pile
                    })
            else:
                # Card too low - needs penalty resolution
                placement_results.append({
                    "player_id": player_id,
                    "card": card,
                    "action": "penalty_required"
                })
                # Stop processing until penalty is resolved
                break
        
        return placement_results
    
    def find_best_pile(self, card):
        """Find the best pile to place the card (incremental rule)"""
        best_pile = 0
        best_diff = float('inf')
        
        for pile_idx in range(4):
            if not self.shared_piles[pile_idx]:
                # Empty pile, use shared card as reference
                pile_top = self.shared_cards[pile_idx] if hasattr(self, 'shared_cards') else 0
            else:
                # Use last card in pile
                pile_top = self.shared_piles[pile_idx][-1]
            
            if card > pile_top:
                diff = card - pile_top
                if diff < best_diff:
                    best_diff = diff
                    best_pile = pile_idx
        
        return best_pile
    
    def select_card(self, player_id: str, card: int):
        """Player selects a card for current round"""
        # Check if player already selected for this round
        if self.player_round_status.get(player_id, False):
            return False
        
        # Check if card is valid
        if player_id in self.player_cards and card in self.player_cards[player_id]:
            # Record selection for this round
            if self.current_round not in self.round_selections:
                self.round_selections[self.current_round] = {}
            self.round_selections[self.current_round][player_id] = card
            
            # Mark player as selected for this round
            self.player_round_status[player_id] = True
            
            # Track last selected card
            self.player_last_card[player_id] = card
            
            # Remove card from player's hand
            self.player_cards[player_id].remove(card)
            
            return True
        return False
    
    def check_round_complete(self):
        """Check if all players have selected cards for current round"""
        return len(self.player_round_status) == len(self.players) and all(self.player_round_status.values())
    
    def next_round(self):
        """Move to next round"""
        if self.current_round < 10:
            self.current_round += 1
            self.player_round_status = {}  # Reset for new round
            self.processed_cards = set()  # Reset processed cards for new round
            return True
        return False  # Game over
    
    def get_round_results(self, round_num: int):
        """Get results for a specific round"""
        return self.round_selections.get(round_num, {})