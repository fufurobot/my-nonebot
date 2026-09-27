"""诊断：记录 OneBot 适配器从 WebSocket 收到的每一帧。

json_to_event() 会对每一帧（事件与 API 响应）都被调用一次，
因此在这里打印即可判定 NapCat 到底有没有把事件推给 bot。

用法： .venv\\Scripts\\python.exe diag_frames.py
"""

import nonebot
from nonebot.adapters.onebot.v11 import adapter as ob11

_orig_j2e = ob11.Adapter.json_to_event.__func__


def _logged(cls, json_data):
    import json as _json

    try:
        text = _json.dumps(json_data, ensure_ascii=False)
    except Exception:
        text = str(json_data)
    print(f"[DIAG] frame <- {text[:400]}", flush=True)
    return _orig_j2e(cls, json_data)


ob11.Adapter.json_to_event = classmethod(_logged)

print("[DIAG] starting bot with per-frame logging", flush=True)
nonebot.init()
nonebot.load_from_toml("pyproject.toml")
nonebot.run()
