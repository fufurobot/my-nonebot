"""用 pdb 停在 OneBot WS 握手上，实时观察 NapCat 到底有没有连进来。

用法： python diag_pdb_ws.py
然后另开一个终端发消息，观察这里是否被 pdb 打断。
按 c 继续，q 退出。
"""

import nonebot

# 在适配器加载前打补丁：给 _handle_ws 和 _handle_http 装上 pdb 断点
from nonebot.adapters.onebot.v11 import adapter as ob11_adapter

_orig_ws = ob11_adapter.Adapter._handle_ws
_orig_http = ob11_adapter.Adapter._handle_http


async def _ws_with_pdb(self, websocket):
    import pdb

    print("\n*** [PDB] _handle_ws CALLED — a WS client is dialing in! ***")
    print("    headers:", dict(websocket.request.headers))
    pdb.set_trace()
    return await _orig_ws(self, websocket)


async def _http_with_pdb(self, request):
    import pdb

    print("\n*** [PDB] _handle_http CALLED — an HTTP report arrived! ***")
    print("    headers:", dict(request.headers))
    print("    body:", request.content)
    pdb.set_trace()
    return await _orig_http(self, request)


ob11_adapter.Adapter._handle_ws = _ws_with_pdb
ob11_adapter.Adapter._handle_http = _http_with_pdb

print("=== starting NoneBot with pdb traps on WS/HTTP ingress ===")
nonebot.init()
nonebot.load_plugins("src/plugins")
nonebot.run()
