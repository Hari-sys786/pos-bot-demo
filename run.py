#!/usr/bin/env python3
"""POS Bot Demo — single port, websockets lib handles both HTTP and WS."""

import asyncio
import json
import hashlib
import time
from pathlib import Path
from http import HTTPStatus

import websockets
from websockets.http11 import Request, Response

from server import BotEngine

STATIC_DIR = Path(__file__).parent / "static"
bot = BotEngine()

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8", ".png": "image/png",
    ".svg": "image/svg+xml", ".ico": "image/x-icon", ".json": "application/json",
}

def serve_static(connection, request):
    """Process handler: serve static files for non-WS requests."""
    # Only intercept non-upgrade requests
    if request.headers.get("Upgrade", "").lower() == "websocket":
        return None  # Let websockets handle it

    path = request.path
    if path == "/" or path == "":
        path = "/index.html"
    if "?" in path:
        path = path.split("?")[0]

    file_path = (STATIC_DIR / path.lstrip("/")).resolve()
    if not str(file_path).startswith(str(STATIC_DIR.resolve())):
        return connection.respond(HTTPStatus.FORBIDDEN, "Forbidden\n")

    if file_path.exists() and file_path.is_file():
        ct = CONTENT_TYPES.get(file_path.suffix, "application/octet-stream")
        body = file_path.read_bytes()
        response = connection.respond(HTTPStatus.OK, "")
        # We need to return a Response manually
        return Response(200, "OK", websockets.datastructures.Headers({
            "Content-Type": ct,
            "Content-Length": str(len(body)),
            "Cache-Control": "no-cache",
        }), body)
    else:
        return Response(404, "Not Found", websockets.datastructures.Headers({
            "Content-Type": "text/plain",
            "Content-Length": "9",
        }), b"Not Found")


async def chat_handler(websocket):
    sid = hashlib.md5(f"{time.time()}-{id(websocket)}".encode()).hexdigest()[:10]
    print(f"[WS] Connected: {sid}", flush=True)

    try:
        for msg in bot.process(sid, "start"):
            await websocket.send(json.dumps(msg))

        async for raw in websocket:
            try:
                payload = json.loads(raw)
                text = payload.get("text", "")
                btn = payload.get("button_data")
            except (json.JSONDecodeError, AttributeError):
                text = raw
                btn = None

            print(f"[WS] {sid}: btn={btn} text={text[:60]}", flush=True)

            try:
                responses = bot.process(sid, text, btn)
                for msg in responses:
                    await websocket.send(json.dumps(msg))
            except Exception as e:
                print(f"[WS] Error: {e}", flush=True)
                import traceback; traceback.print_exc()
                await websocket.send(json.dumps({
                    "type": "text", "content": "⚠️ Error. Try again.",
                    "buttons": [{"text": "🏠 Menu", "data": "menu"}]
                }))

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"[WS] Fatal: {sid}: {e}", flush=True)
        import traceback; traceback.print_exc()

    print(f"[WS] Disconnected: {sid}", flush=True)


async def main():
    # Use process_request to handle HTTP, let WS through
    async with websockets.serve(
        chat_handler,
        "0.0.0.0",
        8888,
        process_request=serve_static,
    ) as server:
        print(f"🤖 POS Bot running on http://0.0.0.0:8888 (HTTP + WS)", flush=True)
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
