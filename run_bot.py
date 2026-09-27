"""在进程内直接启动 NoneBot（不经过 nb-cli 的子进程包装）。

nb-cli 的 `nb run` 会通过 asyncio.create_subprocess_exec 以管道方式启动子进程，
在受限沙箱下会因命名管道被拒绝而失败。此脚本直接调用 nonebot.init()/run()，
无需任何子进程，因此可以在沙箱内运行。

用法： .venv\\Scripts\\python.exe run_bot.py
"""

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

nonebot.load_plugins("src/plugins")
nonebot.load_builtin_plugins("echo")

if __name__ == "__main__":
    nonebot.run()
