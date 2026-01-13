from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import json
import asyncio

router = APIRouter()

# Store active WebSocket connections
active_connections: List[WebSocket] = []

@router.websocket("/ws/gamification")
async def websocket_gamification(websocket: WebSocket):
    """
    WebSocket endpoint for real-time gamification updates.
    
    Usage:
        const ws = new WebSocket('ws://localhost:8000/ws/gamification')
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data)
            if (data.type === 'TIER_UPDATE') {
                // Update UI with new tier
            }
        }
    """
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "CONNECTED",
            "message": "WebSocket connection established"
        })
        
        # Keep connection alive and listen for messages
        while True:
            # Wait for messages from client (if any)
            data = await websocket.receive_text()
            
            # Echo back (for testing)
            await websocket.send_json({
                "type": "ECHO",
                "data": data
            })
            
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print(f"Client disconnected. Active connections: {len(active_connections)}")
    except Exception as e:
        print(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)

async def broadcast_tier_update(equity: float, tier: str):
    """
    Broadcast tier update to all connected WebSocket clients.
    
    Args:
        equity: Current equity balance
        tier: New tier (NEBULA, PROTOSTAR, SUPERNOVA)
    """
    message = {
        "type": "TIER_UPDATE",
        "data": {
            "equity": equity,
            "tier": tier,
            "timestamp": asyncio.get_event_loop().time()
        }
    }
    
    # Broadcast to all connected clients
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception as e:
            print(f"Failed to send to client: {e}")
            disconnected.append(connection)
    
    # Remove disconnected clients
    for conn in disconnected:
        active_connections.remove(conn)
