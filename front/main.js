let ws = null;
let currentRoomId = null;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('createRoomBtn').addEventListener('click', createRoom);
    document.getElementById('joinRoomBtn').addEventListener('click', joinRoom);
});

// Check if we're on a join page
document.addEventListener('DOMContentLoaded', function () {
    const path = window.location.pathname;
    if (path.startsWith('/join/')) {
        const roomId = path.split('/join/')[1];
        document.getElementById('roomId').value = roomId;

        // Hide create room section, only show join section
        document.getElementById('createRoomSection').style.display = 'none';
        document.getElementById('joinRoomSection').style.display = 'block';
        //document.getElementById('gameTitle').textContent = 'Join Game Room';

        // If we have stored credentials, auto-join
        const storedRoomId = localStorage.getItem('currentRoomId');
        const storedPlayerId = localStorage.getItem('currentPlayerId');
        const playerName = localStorage.getItem('playerName');
        const isAdmin = localStorage.getItem('isAdmin') === 'true';

        if (storedRoomId === roomId && storedPlayerId && playerName) {
            // Hide join form too since we're already joined
            document.getElementById('joinRoomSection').style.display = 'none';
            document.getElementById('playerName').value = playerName;

            // Auto-connect for returning players
            currentRoomId = storedRoomId;
            window.currentPlayerId = storedPlayerId;

            // Show appropriate UI
            const resultDiv = document.getElementById('result');
            if (isAdmin) {
                resultDiv.innerHTML = `
                    <h3>Room Created!</h3>
                    <p>Room ID: ${roomId}</p>
                    <p>Player: ${playerName} (Admin)</p>
                    <p>Share this link with others: <strong>${window.location.origin}/join/${roomId}</strong></p>
                    <button onclick="startGame('${roomId}', '${storedPlayerId}')">Start Game</button>
                `;
            } else {
                resultDiv.innerHTML = `
                    <h3>Joined Room!</h3>
                    <p>Room ID: ${roomId}</p>
                    <p>Player: ${playerName}</p>
                    <p>Waiting for admin to start the game...</p>
                `;
            }

            // Connect WebSocket
            connectWebSocket(roomId, storedPlayerId);
            updatePlayerList(roomId);
        }
    } else {
        // On home page, show both sections
        document.getElementById('createRoomSection').style.display = 'block';
        document.getElementById('joinRoomSection').style.display = 'block';
    }
});

async function createRoom() {
    const name = document.getElementById('adminName').value;
    if (!name) return alert('Enter your name');

    const response = await fetch('/room', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    });

    const data = await response.json();
    currentRoomId = data.room_id;
    window.currentPlayerId = data.player_id;

    localStorage.setItem('currentRoomId', data.room_id);
    localStorage.setItem('currentPlayerId', data.player_id);
    localStorage.setItem('playerName', name);
    localStorage.setItem('isAdmin', 'true');

    window.location.href = data.redirect_url;
}

async function joinRoom() {
    const roomId = document.getElementById('roomId').value;
    const name = document.getElementById('playerName').value;
    if (!roomId || !name) return alert('Enter room ID and name');

    const response = await fetch(`/rooms/${roomId}/join`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    });

    const data = await response.json();
    currentRoomId = data.room_id;
    window.currentPlayerId = data.player_id;

    localStorage.setItem('currentRoomId', data.room_id);
    localStorage.setItem('currentPlayerId', data.player_id);
    localStorage.setItem('playerName', name);
    localStorage.setItem('isAdmin', 'false');

    document.getElementById('joinRoomSection').style.display = 'none';
    document.getElementById('createRoomSection').style.display = 'none';

    document.getElementById('result').innerHTML =
        `<h3>Joined Room!</h3>
        <p>Room ID: ${data.room_id}</p>
        <p>Player: ${name}</p>
        <p>Waiting for admin to start the game...</p>`;

    connectWebSocket(data.room_id, data.player_id);
    updatePlayerList(data.room_id);
}

async function startGame(roomId, playerId) {
    const response = await fetch(`/rooms/${roomId}/start?player_id=${playerId}`, {
        method: 'POST'
    });

    const data = await response.json();
    document.getElementById('result').innerHTML +=
        `<h3>Game Started!</h3>
        <p>Your cards: ${JSON.stringify(data.player_cards[playerId])}</p>`;
}

function connectWebSocket(roomId, playerId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    ws = new WebSocket(`${protocol}//${host}/ws/${roomId}/${playerId}`);
    ws.onopen = () => console.log('WebSocket connected');
    ws.onmessage = (event) => handleWebSocketMessage(event.data, roomId);
    ws.onerror = (error) => console.log('WebSocket error:', error);
}

function handleWebSocketMessage(data, roomId) {
    const msg = JSON.parse(data);
    switch (msg.type) {
        case 'game_started':
            displayGameCards(msg.player_cards, window.currentPlayerId, msg.shared_cards);
            updateSharedPiles(msg.shared_piles);
            updatePlayerStatus(msg.player_status);
            break;
        case 'card_selected':
            updatePlayerCards(msg.player_cards);
            updateLastSelected(msg.last_selected);
            updatePlayerStatus(msg.player_status);
            break;
        case 'round_complete':
            updatePlayerCards(msg.player_cards);
            updateLastSelected(msg.last_selected);
            updateSharedPiles(msg.shared_piles);
            updatePlayerPoints(msg.player_points);
            updatePlayerStatus(msg.player_status);
            if (msg.penalty_needed) handlePlacementResults(msg.placement_results);
            break;
        case 'pile_taken':
            updateSharedPiles(msg.shared_piles);
            updatePlayerPoints(msg.player_points);
            if (msg.more_penalties) {
                handlePlacementResults(msg.remaining_placement);
            } else if (msg.all_cards_processed) {
                updateRoundDisplay(msg.current_round);
            }
            break;
        case 'round_finished':
            showRoundFinishedMessage(msg.round, msg.message);
            break;
        case 'round_ended':
            updateRoundDisplay(msg.next_round);
            updatePlayerStatus(msg.player_status);
            break;
        case 'game_finished':
            showGameFinished(msg.winner_name, msg.winner_points, msg.final_scores);
            break;
        default:
            updatePlayerList(roomId);
    }
}

async function updatePlayerList(roomId) {
    const response = await fetch(`/rooms/${roomId}`);
    const data = await response.json();
    const playersList = data.players.map(p =>
        `<li>${p.name} ${p.role === 'admin' ? '(Admin)' : ''}</li>`
    ).join('');
    document.getElementById('players').innerHTML =
        `<h3>Players in Room (${data.players.length}/10):</h3>
        <ul>${playersList}</ul>`;
}

function displayGameCards(allPlayerCards, myPlayerId, sharedCards) {
    const myCards = allPlayerCards[myPlayerId] || [];
    const myCardsHtml = myCards.map(card =>
        `<button onclick="selectCard(${card})" class="card-button">
            <div class="card">
                <div class="card-number">${card}</div>
                <div class="card-bulls">${getBullPoints(card)}</div>
            </div>
        </button>`
    ).join('');
    const sharedCardsHtml = sharedCards.map((_, i) =>
        `<div style="margin:5px 0;padding:10px;border:1px solid #ccc;">
            <strong>Pile ${i + 1}</strong>
            <div id="pile${i}" style="margin-top:5px;"></div>
        </div>`
    ).join('');

    document.getElementById('result').innerHTML =
        `<h3>Game Started!</h3>
        <p><strong>Round: 1/10</strong></p>
        <p><strong>Your Points:</strong> <span id="myPoints">0</span></p>
        <p><strong>Your Last Selected:</strong> <span id="lastSelected">None</span></p>
        <div id="playerStatus" style="margin:10px 0;padding:10px;border:1px solid #ddd;border-radius:5px;"></div>
        <p><strong>Your Cards:</strong><br>${myCardsHtml}</p>
        <p><strong>Shared Piles:</strong></p>
        <div>${sharedCardsHtml}</div>
        <div id="roundResults"></div>`;
}

async function selectCard(card) {
    const cardButton = event.target.closest('button');
    if (cardButton) cardButton.style.display = 'none';

    const response = await fetch(`/rooms/${currentRoomId}/select?player_id=${window.currentPlayerId}&card=${card}`, {
        method: 'POST'
    });

    if (!response.ok) {
        alert('Failed to select card');
        if (cardButton) cardButton.style.display = 'inline-block';
    }
}

function updatePlayerCards(allPlayerCards) {
    const myCards = allPlayerCards[window.currentPlayerId] || [];
    const myCardsHtml = myCards.map(card =>
        `<button onclick="selectCard(${card})" class="card-button">
            <div class="card">
                <div class="card-number">${card}</div>
                <div class="card-bulls">${getBullPoints(card)}</div>
            </div>
        </button>`
    ).join('');

    document.getElementById('result').innerHTML = document.getElementById('result').innerHTML.replace(
        /<p><strong>Your Cards:<\/strong><br>.*?<\/p>/,
        `<p><strong>Your Cards:</strong><br>${myCardsHtml}</p>`
    );
}



function updateLastSelected(lastSelectedCards) {
    const myLastCard = lastSelectedCards[window.currentPlayerId];
    if (myLastCard) {
        document.getElementById('lastSelected').textContent = myLastCard;
    }
}

function updateSharedPiles(sharedPiles) {
    for (let i = 0; i < 4; i++) {
        const pileCards = sharedPiles[i] || [];
        const pileElement = document.getElementById(`pile${i}`);
        if (pileElement) {
            pileElement.innerHTML = pileCards.map(card =>
                `<div class="card small" style="margin:2px;display:inline-block;">
                    <div class="card-number">${card}</div>
                    <div class="card-bulls">${getBullPoints(card)}</div>
                </div>`
            ).join('');
        }
    }
}

function getBullPoints(card) {
    if (card === 55) return 7;
    if (card % 11 === 0) return 5;
    if (card % 10 === 0) return 3;
    if (card % 5 === 0) return 2;
    return 1;
}

function updatePlayerPoints(points) {
    const myPoints = points[window.currentPlayerId] || 0;
    document.getElementById('myPoints').textContent = myPoints;
}

function handlePlacementResults(results) {
    results.forEach(result => {
        if (result.player_id === window.currentPlayerId && result.action === 'penalty_required') {
            showPenaltyNotification(result.card);
            enablePileSelection(result.card);
        }
    });
}

function showPenaltyNotification(card) {
    freezeCardSelection();
    const messageDiv = document.createElement('div');
    messageDiv.style.cssText = 'background:#ffcccc;border:1px solid #f5c6cb;color:#721c24;padding:10px;margin:10px 0;border-radius:5px;text-align:center;font-weight:bold;';
    messageDiv.textContent = `Your card ${card} is too low! Click on a pile to take it.`;
    messageDiv.id = 'penalty-notification';
    
    const statusDiv = document.getElementById('playerStatus');
    if (statusDiv) {
        statusDiv.appendChild(messageDiv);
    }
}

function enablePileSelection(card) {
    window.penaltyCard = card;
    // Make piles clickable
    for (let i = 0; i < 4; i++) {
        const pileElement = document.getElementById(`pile${i}`);
        if (pileElement) {
            pileElement.style.cursor = 'pointer';
            pileElement.style.border = '2px solid #dc3545';
            pileElement.onclick = () => selectPileForPenalty(i, card);
        }
    }
}

async function selectPileForPenalty(pileIdx, lowCard) {
    const response = await fetch(`/rooms/${currentRoomId}/take_pile?player_id=${window.currentPlayerId}&pile_idx=${pileIdx}&low_card=${lowCard}`, {
        method: 'POST'
    });
    if (response.ok) {
        clearPenaltyNotification();
    } else {
        alert('Failed to take pile');
    }
}

function clearPenaltyNotification() {
    const notification = document.getElementById('penalty-notification');
    if (notification) notification.remove();
    
    // Remove pile selection styling
    for (let i = 0; i < 4; i++) {
        const pileElement = document.getElementById(`pile${i}`);
        if (pileElement) {
            pileElement.style.cursor = 'default';
            pileElement.style.border = 'none';
            pileElement.onclick = null;
        }
    }
    window.penaltyCard = null;
    unfreezeCardSelection();
}

function showRoundFinishedMessage(round, message) {
    freezeCardSelection();
    const messageDiv = document.createElement('div');
    messageDiv.style.cssText = 'background:#d4edda;border:1px solid #c3e6cb;color:#155724;padding:10px;margin:10px 0;border-radius:5px;text-align:center;font-weight:bold;';
    messageDiv.textContent = message;

    const statusDiv = document.getElementById('playerStatus');
    if (statusDiv) {
        statusDiv.appendChild(messageDiv);
        setTimeout(() => {
            messageDiv.remove();
            unfreezeCardSelection();
        }, 3000);
    }
}

function updatePlayerStatus(playerStatus) {
    const statusDiv = document.getElementById('playerStatus');
    if (statusDiv && playerStatus) {
        const statusHtml = Object.entries(playerStatus).map(([pid, info]) => {
            let statusColor, statusIcon;
            if (info.status === 'played') {
                statusColor = '#28a745';
                statusIcon = '✓';
            } else if (info.status === 'penalty') {
                statusColor = '#dc3545';
                statusIcon = '⚠️';
            } else {
                statusColor = '#ffc107';
                statusIcon = '🤔';
            }
            return `<span style="display:inline-block;margin:5px;padding:5px 10px;background:${statusColor};color:white;border-radius:15px;font-size:12px;">
                ${statusIcon} ${info.name}: ${info.status}
            </span>`;
        }).join('');
        
        // Preserve any existing round finished messages
        const existingMessages = statusDiv.querySelectorAll('[style*="background:#d4edda"]');
        statusDiv.innerHTML = `<strong>Player Status:</strong><br>${statusHtml}`;
        
        // Re-append preserved messages
        existingMessages.forEach(msg => statusDiv.appendChild(msg));
    }
}

function showGameFinished(winnerName, winnerPoints, finalScores) {
    freezeCardSelection();
    const messageDiv = document.createElement('div');
    messageDiv.style.cssText = 'background:#28a745;border:1px solid #1e7e34;color:white;padding:20px;margin:20px 0;border-radius:10px;text-align:center;font-weight:bold;font-size:18px;';
    
    const scoresHtml = Object.entries(finalScores).map(([pid, info]) => 
        `<li>${info.name}: ${info.points} points</li>`
    ).join('');
    
    messageDiv.innerHTML = `
        <h2>🎉 Game Finished! 🎉</h2>
        <h3>Winner: ${winnerName}</h3>
        <p>With only ${winnerPoints} penalty points!</p>
        <h4>Final Scores:</h4>
        <ul style="text-align:left;display:inline-block;">${scoresHtml}</ul>
    `;
    
    const statusDiv = document.getElementById('playerStatus');
    if (statusDiv) {
        statusDiv.appendChild(messageDiv);
    }
}

function freezeCardSelection() {
    const cardButtons = document.querySelectorAll('.card-button');
    cardButtons.forEach(button => {
        button.style.pointerEvents = 'none';
        button.style.opacity = '0.5';
    });
}

function unfreezeCardSelection() {
    const cardButtons = document.querySelectorAll('.card-button');
    cardButtons.forEach(button => {
        button.style.pointerEvents = 'auto';
        button.style.opacity = '1';
    });
}

function updateRoundDisplay(roundNumber) {
    document.querySelectorAll('p').forEach(p => {
        if (p.textContent.includes('Round:')) {
            p.innerHTML = `<strong>Round: ${roundNumber}/10</strong>`;
        }
    });
}