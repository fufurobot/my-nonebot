# dsh-bot

A NoneBot2 QQ bot whose main feature is a group chess plugin: play a full game
of chess by chat command, with a Unicode board, team play, and a PGN record of
who played.

## Requirements

- Python **3.10 – 3.13**
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- A QQ client that speaks the OneBot v11 protocol (e.g. NapCatQQ)

## How to start

1. Install dependencies:

   ```bash
   uv sync --all-groups
   ```

2. Copy the environment template and fill in your own values:

   ```bash
   cp .env.example .env
   ```

   `.env` is gitignored. Set `ONEBOT_V11_ACCESS_TOKEN` to the same token your
   QQ client uses; a mismatch is rejected at the WebSocket handshake with
   HTTP 403 and retried every 30 seconds.

3. Run the bot:

   ```bash
   uv run nb run
   ```

   Point your QQ client at `ws://<HOST>:<PORT>/onebot/v11/` as a
   reverse-WebSocket client.

## Chess plugin

All commands are prefixed with one of `COMMAND_START` (`/`, `.` or `,` by
default). `/chess help` reprints this list in chat.

| Command | Description |
| --- | --- |
| `chess join <white\|black>` | Join a side. A side may hold **several** players, and one player may join both sides. |
| `chess leave` / `chess resign` | Leave the game. The side is only resigned once its **last** player leaves. |
| `chess players` | Show both rosters with player counts. |
| `chess board` | Show the current board. |
| `chess move <move>` | Play a move in SAN or UCI form, e.g. `e4`, `Nf3`, `O-O`, `e2e4`. |
| `chess takeback` | Propose taking a move back; the opponent confirms with `chess agree`. |
| `chess draw` | Propose a draw; the opponent confirms with `chess agree`. |
| `chess agree` | Accept the pending proposal. |
| `chess help` | Show help. |

### The board

The board is drawn as a bordered grid of Unicode pieces, with file letters
`a`–`h` above and below it and a rank digit `1`–`8` on every row, so you can read
a square straight off the picture rather than counting:

```
┌───┬───┬───┬───┬───┬───┬───┬───┐
│ a │ b │ c │ d │ e │ f │ g │ h │
├───┼───┼───┼───┼───┼───┼───┼───┤
│ ♜ │ ♞ │ ♝ │ ♛ │ ♚ │ ♝ │ ♞ │ ♜ │ 8
│ ♟ │ ♟ │ ♟ │ ♟ │ ♟ │ ♟ │ ♟ │ ♟ │ 7
│   │ · │   │ · │   │ · │   │ · │ 6
│ · │   │ · │   │ · │   │ · │   │ 5
│   │ · │   │ · │   │ · │   │ · │ 4
│ · │   │ · │   │ · │   │ · │   │ 3
│ ♙ │ ♙ │ ♙ │ ♙ │ ♙ │ ♙ │ ♙ │ ♙ │ 2
│ ♖ │ ♘ │ ♗ │ ♕ │ ♔ │ ♗ │ ♘ │ ♖ │ 1
├───┼───┼───┼───┼───┼───┼───┼───┤
│ a │ b │ c │ d │ e │ f │ g │ h │
└───┴───┴───┴───┴───┴───┴───┴───┘
```

### Team play and resigning

Any number of players may join either side, and any member of the side to move
may play that side's move. When a player leaves, the game continues for as long
as a teammate remains; only the departure of a side's **last** player resigns
that side. A game that has already finished keeps its recorded result.

### Game record

When a game ends, the bot prints a PGN with both rosters in the `White` and
`Black` headers, so the endgame record identifies every player by QQ number:

```pgn
[Event "群聊对弈"]
[White "10001, 10002"]
[Black "20001"]
[Result "0-1"]
```

## Development

```bash
uv sync --all-groups      # install runtime and dev dependencies
uv run pytest tests -q    # run the test suite
uv run ruff format src tests
uv run ruff check src/plugins/chess tests
```

The suite covers the board renderer, team/resign semantics and PGN headers, and
parses the CI configuration so a pipeline gate cannot silently disappear.

## Continuous integration

- `.github/workflows/ci.yml` — GitHub Actions: lint, tests on Python 3.10–3.13,
  config validation, and a secret scan.
- `.gitlab-ci.yml` — the same gates for GitLab, plus wheel building on the
  default branch and tags.

Both pipelines fail the build if a credential-shaped string is committed.

## Documentation

See the [NoneBot docs](https://nonebot.dev/).

## License

AGPL-3.0. See [LICENSE](LICENSE).
