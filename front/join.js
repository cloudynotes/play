// Check if we're on a join page
document.addEventListener('DOMContentLoaded', function() {
    const path = window.location.pathname;
    if (path.startsWith('/join/')) {
        const roomId = path.split('/join/')[1];
        document.getElementById('roomId').value = roomId;
        
        // Hide create room section, only show join section
        document.getElementById('createRoomSection').style.display = 'none';
        document.getElementById('joinRoomSection').style.display = 'block';
        document.getElementById('gameTitle').textContent = 'Join Game Room';
        
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