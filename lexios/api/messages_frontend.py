# websocket_logic.py
import aioredis
import json
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict
from fastapi import APIRouter

from lexios.settings.main import BROKER_URL
from lexios.api.session_data import backend
from lexios.database.users import update_user_data_in_db
from lexios.core.session_manager import LexiSessionManager

messages_router = APIRouter()
session_manager = LexiSessionManager()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        del self.active_connections[session_id]

    async def send_json(self, session_id: str, message: dict):
        client_socket = self.active_connections.get(session_id)
        if client_socket:
            try:
                await client_socket.send_json(message)
                
            except Exception as e:
                # Handle disconnection if needed
                print("Redis-Websocket Warning:", e)
        else:
            # Handle missing WebSocket, maybe reconnect or notify user
            print("WebSocket not found for session_id:", session_id)

manager = ConnectionManager()

# Stablish a new client connection
@messages_router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
):
    try:
        await manager.connect(session_id, websocket)
        # Keep the connection open
        while True:
            data = await websocket.receive_json()

    except WebSocketDisconnect as e:

        # Retrieve session data
        session_data = await backend.read(session_id=UUID(session_id))

        # Save in database
        update_user_data_in_db(session_data)

        # conversation history
        session_manager.save_session(session_data.user_id)

        # Handle disconnect
        manager.disconnect(session_id)
    
    return JSONResponse({'status':'connected'})

# Active listen messages coming from broker
async def listen_to_redis():
    # Listen to Redis messages and forward them to the corresponding WebSocket connections
    async with aioredis.from_url(BROKER_URL) as broker:
        channel = broker.pubsub()
        await channel.subscribe("fastapi_channel")
        print("Listening to messages from backend.")
        try:
            while True:
                message = await channel.get_message(ignore_subscribe_messages=True)
                if message:
                    message_data = json.loads(message['data'].decode("utf-8"))
                    session_id = message_data.get('session_id')
                    if session_id:
                        try:
                            await manager.send_json(
                                session_id= session_id,
                                message= message_data,
                            )
                        except Exception as e:
                            pass
        except WebSocketDisconnect as e:
            channel.close()
            await channel.wait_closed()

