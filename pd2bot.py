# pd2_corruption_bot.py

import os
import time
import discord
from dataclasses import dataclass
from discord.ext import commands, tasks
from dotenv import load_dotenv

# ------------------ ENV ------------------
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing from .env")

if not CHANNEL_ID:
    raise RuntimeError("CHANNEL_ID missing from .env")

NOTIFY_CHANNEL_ID = int(CHANNEL_ID)
PREFIX = "!"
# -----------------------------------------

ZONES = [
  "Blood Moor and Den of Evil",
  "Cold Plains and the Cave",
  "Stony Field and Tristram",
  "Dark Wood and the Underground Passage",
  "Black Marsh and the Hole",
  "Tamoe Highland and the Pit",
  "Burial Ground and Mausoleum",
  "Forgotten Tower",
  "Outer Cloister and Barracks",
  "Jail, Inner Cloister, and Cathedral",
  "Catacombs",
  "Cow Level",
  "Rocky Waste and the Stony Tomb",
  "Dry Hills and the Halls of the Dead",
  "Far Oasis and the Maggot Lair",
  "Lost City, Ancient Tunnels, and Claw Viper Temple",
  "Canyon of the Magi and Tal Rasha's Tomb",
  "Lut Gholein Sewers and the Palace Cellars",
  "Arcane Sanctuary",
  "Spider Forest, Arachnid Lair, and Spider Cavern",
  "Great Marsh and the Swampy Pit",
  "Flayer Jungle and the Flayer Dungeon",
  "Lower Kurast and the Kurast Sewers",
  "Kurast Bazaar, Ruined Temple, and Disused Fane",
  "Upper Kurast, the Forgotten Reliquary, and Forgotten Temple",
  "Travincal, the Ruined Fane, and Disused Reliquary",
  "Durance of Hate",
  "Outer Steppes and the Plains of Despair",
  "City of the Damned and the River of Flame",
  "Chaos Sanctuary",
  "Bloody Foothills and the Frigid Highlands",
  "Arreat Plateau, Crystalline Passage, and Frozen River",
  "Glacial Trail, Drifter Cavern, and Frozen Tundra",
  "Ancients' Way and the Icy Cellar",
  "Nihlathak's Temple",
  "Abaddon, the Pit of Acheron, and the Infernal Pit",
  "Worldstone Keep and Throne of Destruction",
]

INTERVAL_MS = 900_000  # 15 minutes

def get_next_prng(seed: int, mul: int, inc: int) -> int:
    return ((seed * mul + inc) >> 16) & 32767

@dataclass(frozen=True)
class ZoneInfo:
    zone: str
    ts_ms: int
    seed: int

def get_zone(ts_ms=None, n=0) -> ZoneInfo:
    if ts_ms is None:
        ts_ms = int(time.time() * 1000)

    base = (ts_ms // INTERVAL_MS) * INTERVAL_MS
    ts = base + INTERVAL_MS * n

    a = ts // INTERVAL_MS
    b = ts // 86_400_000
    seed = a + b

    idx = get_next_prng(seed, 214013, 2531011) % len(ZONES)
    return ZoneInfo(ZONES[idx], ts, seed)

def current_and_next():
    # Active + next 4 (Next .. Next +3)
    return [get_zone(n=i) for i in range(5)]

def is_target_zone(z):
    return z in {
        "Chaos Sanctuary",
        "Cow Level",
        "Stony Field and Tristram"
    }

def discord_time(ts):
    return f"<t:{ts//1000}:f>"

def minutes_left_in_window(active_ts_ms: int, now_ms: int) -> int:
    # Remaining minutes until the end of the current 15-minute corruption window
    end_ms = active_ts_ms + INTERVAL_MS
    return max(0, int((end_ms - now_ms) // 60000))

def cz_message(infos):
    # Fixed-width alignment using a monospace code block.

    now_ms = int(time.time() * 1000)
    zone_width = 40  # fixed width for cleaner columns

    def mins_until(ts_ms: int) -> int:
        return max(0, int((ts_ms - now_ms) // 60000))

    def mins_left_in_window(active_start_ms: int) -> int:
        return mins_until(active_start_ms + INTERVAL_MS)

    lines = ["Corrupted Zone Bot"]

    active_left = mins_left_in_window(infos[0].ts_ms)

    for i, z in enumerate(infos):
        if i == 0:
            label = "Active"
            icon = "🟥"
            timing = f"(Time Left {active_left}m)"
        elif i == 1:
            # Next should match active time left
            label = "Next"
            icon = "➡️"
            timing = f"(In {active_left}m)"
        else:
            label = f"Next +{i-1}"
            icon = "⏭️"
            timing = f"(In {mins_until(z.ts_ms)}m)"

        left_col = f"{icon} {label}"
        lines.append(f"{left_col:<10} : {z.zone:<{zone_width}}  {timing}")

    return f"""```
{chr(10).join(lines)}
```"""

    now_ms = int(time.time() * 1000)
    zone_width = 40  # fixed width for cleaner columns

    def mins_until(ts_ms: int) -> int:
        return max(0, int((ts_ms - now_ms) // 60000))

    lines = ["Corrupted Zone Bot"]

    for i, z in enumerate(infos):
        if i == 0:
            left = minutes_left_in_window(z.ts_ms, now_ms)
            label = "Active"
            icon = "🟥"
            timing = f"(Time Left {left}m)"
        else:
            label = "Next" if i == 1 else f"Next +{i-1}"
            icon = "➡️" if i == 1 else "⏭️"
            timing = f"(In {mins_until(z.ts_ms)}m)"

        left_col = f"{icon} {label}"
        lines.append(f"{left_col:<10} : {z.zone:<{zone_width}}  {timing}")

    return f"""```
{chr(10).join(lines)}
```"""
def cow_warning(info):
    return f"🐮 **Cow Level in 10 minutes** — starts {discord_time(info.ts_ms)}"

def active_alert(info):
    return f"🟥 **ACTIVE NOW:** `{info.zone}` — {discord_time(info.ts_ms)}"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

last_seed = None
last_cow_seed = None

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    zone_watcher.start()

@bot.command()
async def cz(ctx):
    await ctx.send(cz_message(current_and_next()))

@tasks.loop(seconds=30)
async def zone_watcher():
    global last_seed, last_cow_seed

    channel = bot.get_channel(NOTIFY_CHANNEL_ID)
    if not channel:
        return

    now = int(time.time() * 1000)
    cur = get_zone(now)

    if is_target_zone(cur.zone) and cur.seed != last_seed:
        last_seed = cur.seed
        await channel.send(active_alert(cur))

    # Cow warning (10 min before)
    for i in range(300):
        z = get_zone(now, i)
        if z.zone == "Cow Level":
            warn_at = z.ts_ms - 600_000
            if warn_at <= now < warn_at + 30_000 and z.seed != last_cow_seed:
                last_cow_seed = z.seed
                await channel.send(cow_warning(z))
            break

@zone_watcher.before_loop
async def before_zone_watcher():
    await bot.wait_until_ready()

bot.run(DISCORD_TOKEN)
