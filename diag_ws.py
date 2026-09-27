"""用 pdb 诊断：为什么控制台能收到消息，代码却收不到。

思路：直接连到 NapCat 8082 的 websocket 端点，看它是否会推送事件。
NapCat 的 httpServers 配置里有 enableWebsocket 字段——若为 false，
则即使 HTTP API 可用，也不会通过 WS 推送任何事件。
"""

import asyncio
import json
import sys

import websockets


async def probe(token: str):
    # NapCat 的 HTTP server 若开启 enableWebsocket，通常在 / 或 /ws 上接受 WS
    for path in ["/", "/ws", "/onebot/v11/ws", "/api/ws"]:
        url = f"ws://127.0.0.1:8082{path}"
        try:
            async with websockets.connect(
                url,
                additional_headers={"Authorization": f"Bearer {token}"},
                open_timeout=4,
            ) as ws:
                print(f"[OK]    connected {url}")
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=3)
                    print(f"[EVENT] {str(msg)[:300]}")
                except asyncio.TimeoutError:
                    print(f"[IDLE]  {url} connected but no events in 3s")
        except Exception as e:
            print(f"[FAIL]  {url} -> {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("=== probing NapCat 8082 for websocket event push ===")
    asyncio.run(probe("eFyBfrJslorce3Ah"))
