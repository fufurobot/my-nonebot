---
name: asimo-qq-operator
description: Operate the two NapCat QQ instances (沐风63 bot account on OneBot 8080, ASIMO test account on HTTP 8082) and smoke-test the NoneBot chess plugin inside group 726525232.
whenToUse: When you need to start, restart, inspect or smoke-test the QQ bot stack (NapCat instances, NoneBot on 8080, ASIMO on 8082) or the chess plugin.
---

# Operating the ASIMO / 沐风63 QQ bot stack

## Topology (verified, do not re-derive)

| Role | Account | Instance dir | How it talks to the bot |
| --- | --- | --- | --- |
| Bot account **沐风63** | `369319889` | `NapCat-QCE-Windows-x64` | reverse-WS **client** → `ws://127.0.0.1:8080/onebot/v11/` |
| Test account **ASIMO** | `1362015219` | `NapCat-QCE-Windows-x64 - Copy` | HTTP **server** on `127.0.0.1:8082` |

- NapCat root: `C:\Users\fufu\Downloads\NapCat-QCE-Windows-x64-v6.2.3`
- Bot project: `C:\Users\fufu\Downloads\workspace\poc\qqbot\dsh-bot-nonebot`
- Test group: **`726525232`** ("damebot赛博怪话群"). Restrict every test to this group.
- WebUI: `6099`. `webui.json`'s `token` rotates after QR login, so prefer the OneBot APIs below over WebUI calls.

## THE ONE FAILURE THAT BREAKS EVERYTHING

Both NapCat instances share the **same QQ installation** and therefore the same
internal packet server port. If a stale instance still holds it, the second
instance starts but its core dies immediately:

```
[NapCat] [Error] Unhandled Exception: listen EADDRINUSE: address already in use 0.0.0.0:40653
```

When that happens the symptom is deceptive: the reverse-WS client still connects
and heartbeats still flow, so the bot looks healthy — but **no message events
ever arrive**, because NapCat never converted them. Confirm with:

```powershell
# 0 = pipeline dead; >0 = healthy
(Select-String -Path <newest napcat log> -Pattern "转化为 OB11Message").Count
```

**Always kill every QQ/NapCat process before starting an instance.** Never run
the two instances concurrently from a cold start without clearing the port first.

## Start sequence (order matters)

```powershell
# 1. Clean slate — both instances and the bot
Get-Process | Where-Object { $_.ProcessName -match '^QQ$|NapCatWinBootMain' } |
  ForEach-Object { taskkill /F /PID $_.Id }
# free 8080 too, or the new bot cannot bind
$p = (netstat -ano | Select-String '127.0.0.1:8080.*LISTENING' |
      ForEach-Object { ($_ -split '\s+')[-1] } | Select-Object -First 1)
if ($p) { taskkill /F /PID $p }

# 2. Bot account first — it needs 8080 to already exist, but retries every 30s
Set-Location "C:\Users\fufu\Downloads\NapCat-QCE-Windows-x64-v6.2.3\NapCat-QCE-Windows-x64"
cmd /c "quickmufeng.bat"

# 3. Bot
Set-Location "C:\Users\fufu\Downloads\workspace\poc\qqbot\dsh-bot-nonebot"
$env:PYTHONIOENCODING = "utf-8"
uv run nb run

# 4. Then the ASIMO test instance
Set-Location "C:\Users\fufu\Downloads\NapCat-QCE-Windows-x64-v6.2.3\NapCat-QCE-Windows-x64 - Copy"
cmd /c "quickasimo.bat"
```

`quickmufeng.bat` / `quickasimo.bat` pass the account number straight to QQ as
`-q <uin>` for quick login. They are the correct launchers; do not hand-roll one.

Success looks like this in the bot log:

```
uvicorn | 127.0.0.1:<port> - "WebSocket /onebot/v11/" [accepted]
nonebot | OneBot V11 | Bot 369319889 connected
```

## Auth token: one variable, two directions

`ONEBOT_V11_ACCESS_TOKEN` is used for **both** validating inbound WS clients
**and** authenticating outbound API calls. The two instances have *different*
tokens, so it can only ever satisfy one side.

- Must equal `websocketClients[0].token` in the **bot account's** config:
  `Jbs_cqwRuXMHHIJH`.
- A wrong value is rejected at handshake with `Unexpected server response: 403`
  and retried every 30s.
- `ONEBOT_V11_API_ROOTS` pointing at 8082 is **wrong** for this setup: replies
  travel back over the socket. Leave it unset.
- `_check_access_token` runs only on the **WebSocket** path. `_handle_http` never
  checks a token, so don't use HTTP-POST success as evidence about WS auth.

## Smoke test

`/chess help` is the full-stack test. Send it as a real QQ message from ASIMO:

```powershell
$body = @{ group_id = 726525232; message = '/chess help' } | ConvertTo-Json -Compress
Invoke-WebRequest -Uri 'http://127.0.0.1:8082/send_group_msg' -Method Post `
  -Headers @{ Authorization = 'Bearer eFyBfrJslorce3Ah' } `
  -ContentType 'application/json' -Body $body -UseBasicParsing
```

Verify the reply landed, and that it came from 沐风63 (`369319889`):

```powershell
$b = @{ group_id = 726525232; count = 3 } | ConvertTo-Json -Compress
Invoke-WebRequest -Uri 'http://127.0.0.1:8082/get_group_msg_history' -Method Post `
  -Headers @{ Authorization = 'Bearer eFyBfrJslorce3Ah' } `
  -ContentType 'application/json' -Body $b -UseBasicParsing |
  ForEach-Object { ($_.Content | ConvertFrom-Json).data.messages } |
  ForEach-Object { "$($_.sender.nickname) :: $($_.raw_message)" }
```

This is the only trustworthy end-to-end assertion: the bot received a real
NapCat event and NapCat delivered the bot's reply.

### Injecting a synthetic event (isolates bot bugs from NapCat bugs)

When you need to prove the plugin pipeline works while NapCat's event pipeline is
suspect, POST an event straight at the bot. `X-Self-ID` is **required** (400
without it):

```powershell
$ev = @{
  post_type='message'; message_type='group'; sub_type='normal'; message_id=9001
  group_id=726525232; user_id=1362015219; raw_message='/chess help'; font=0
  self_id=369319889; time=1790480000
  sender=@{ user_id=1362015219; nickname='ASIMO'; role='member' }
  message=@(@{ type='text'; data=@{ text='/chess help' } })
} | ConvertTo-Json -Depth 6 -Compress
Invoke-WebRequest -Uri 'http://127.0.0.1:8080/onebot/v11/http' -Method Post `
  -Headers @{ 'X-Self-ID' = '369319889' } -ContentType 'application/json' `
  -Body $ev -UseBasicParsing      # expect 204
```

A synthetic event that *sends* successfully while real messages never arrive
means NapCat's push is broken, not the plugin.

## Waiting for events

Events arrive on a background job; check with `job_output` on the bot job id.
NapCat's WS client retries every **30 seconds**, so after restarting the bot
allow at least that long before concluding the handshake failed.

## Trap: `nb run` spawns detached children

`uv run nb run` forks a detached grandchild, so killing the job **does not** free
port 8080. Always re-check and kill by port before restarting, or the next bot
silently fails to bind (and NapCat logs `ECONNREFUSED`). `taskkill` outside the
workspace needs full access.

## Trap: diagnostics that modify the venv

Instrumenting `_handle_ws` in
`.venv/Lib/site-packages/nonebot/adapters/onebot/v11/adapter.py` is an effective
way to see raw frames (`from . import adapter`) — but it edits a dependency.
Never leave that edit in place after debugging.

## Confirming which account is which

Each instance's log prefixes lines with the account nickname, and the OB11 payload
carries `self_id`. Group names resolve via `get_group_msg_history`. Note the
`- Copy` directory is ASIMO, **not** a duplicate of the bot account.

## Housekeeping

`.uv-cache` and `.uv-cache2` are scratch dirs whose ACLs the sandbox cannot
delete; remove them by hand. `uv.lock` may still list a stale `python-chess`
entry — regenerate with `uv lock`.
