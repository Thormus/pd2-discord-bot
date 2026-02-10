#!/usr/bin/env python3

import os
import time
import discord
from dataclasses import dataclass
from discord.ext import commands, tasks
from dotenv import load_dotenv
import subprocess

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing from .env")
if not CHANNEL_ID:
    raise RuntimeError("CHANNEL_ID missing from .env")
NOTIFY_CHANNEL_ID = int(CHANNEL_ID)
PREFIX = "!"
notifications_enabled = True

ZONES = [
  "Blood Moor and Den of Evil", "Cold Plains and the Cave", "Stony Field and Tristram",
  "Dark Wood and the Underground Passage", "Black Marsh and the Hole", "Tamoe Highland and the Pit",
  "Burial Ground and Mausoleum", "Forgotten Tower", "Outer Cloister and Barracks",
  "Jail, Inner Cloister, and Cathedral", "Catacombs", "Cow Level",
  "Rocky Waste and the Stony Tomb", "Dry Hills and the Halls of the Dead",
  "Far Oasis and the Maggot Lair", "Lost City, Ancient Tunnels, and Claw Viper Temple",
  "Canyon of the Magi and Tal Rasha's Tomb", "Lut Gholein Sewers and the Palace Cellars",
  "Arcane Sanctuary", "Spider Forest, Arachnid Lair, and Spider Cavern",
  "Great Marsh and the Swampy Pit", "Flayer Jungle and the Flayer Dungeon",
  "Lower Kurast and the Kurast Sewers", "Kurast Bazaar, Ruined Temple, and Disused Fane",
  "Upper Kurast, the Forgotten Reliquary, and Forgotten Temple", "Travincal, the Ruined Fane, and Disused Reliquary",
  "Durance of Hate", "Outer Steppes and the Plains of Despair", "City of the Damned and the River of Flame",
  "Chaos Sanctuary", "Bloody Foothills and the Frigid Highlands", "Arreat Plateau, Crystalline Passage, and Frozen River",
  "Glacial Trail, Drifter Cavern, and Frozen Tundra", "Ancients' Way and the Icy Cellar",
  "Nihlathak's Temple", "Abaddon, the Pit of Acheron, and the Infernal Pit",
  "Worldstone Keep and Throne of Destruction",
]

INTERVAL_MS = 900000

def get_next_prng(seed, mul, inc):
    return ((seed * mul + inc) >> 16) & 32767

@dataclass
class ZoneInfo:
    zone: str
    ts_ms: int
    seed: int

def get_zone(ts_ms=None, n=0):
    if ts_ms is None:
        ts_ms = int(time.time() * 1000)
    base = (ts_ms // INTERVAL_MS) * INTERVAL_MS
    ts = base + INTERVAL_MS * n
    a = ts // INTERVAL_MS
    b = ts // 86400000
    seed = a + b
    idx = get_next_prng(seed, 214013, 2531011) % len(ZONES)
    return ZoneInfo(ZONES[idx], ts, seed)

def current_and_next():
    return [get_zone(n=i) for i in range(5)]

def is_target_zone(z):
    return z in {"Chaos Sanctuary", "Cow Level", "Stony Field and Tristram", "Abaddon, the Pit of Acheron, and the Infernal Pit"}

def minutes_left_in_window(active_ts_ms, now_ms):
    return max(0, int((active_ts_ms + INTERVAL_MS - now_ms) // 60000))

def cz_message(infos):
    now_ms = int(time.time() * 1000)
    active_left = minutes_left_in_window(infos[0].ts_ms, now_ms)
    lines = ["Corrupted Zone Bot"]
    for i in range(min(5, len(infos))):
        if i == 0:
            lines.append(f"🟥 Active : {infos[0].zone:<40}  (Time Left {active_left}m)")
        else:
            mins = int((infos[i].ts_ms - now_ms) // 60000) if i == 1 else int((infos[i].ts_ms - now_ms) // 60000)
            lines.append(f"➡️ Next   : {infos[i].zone:<40}  (In {mins}m)")
    return "```\\n" + "\\n".join(lines) + "```"

def cow_warning(info):
    return "🐮 **Cow Level in 10 minutes**"

def abaddon_warning(info):
    return "🔥 **Abaddon, the Pit of Acheron, and the Infernal Pit in 10 minutes**"

def active_alert(info):
    return f"🟥 **ACTIVE NOW:** `{info.zone}`"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

last_seed = None
last_cow_seed = None
last_abaddon_seed = None

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    zone_watcher.start()

@bot.command()
async def cz(ctx):
    await ctx.send(cz_message(current_and_next()))

@bot.command()
async def toggle(ctx):
    global notifications_enabled
    notifications_enabled = not notifications_enabled
    status = "🔔 **Notifications ENABLED**" if notifications_enabled else "🔕 **Notifications DISABLED**"
    await ctx.send(f"{status} Use `!toggle` again to switch back.")

@tasks.loop(seconds=30)
async def zone_watcher():
    global last_seed, last_cow_seed, last_abaddon_seed
    if not notifications_enabled:
        return
    channel = bot.get_channel(NOTIFY_CHANNEL_ID)
    if not channel:
        return
    now = int(time.time() * 1000)
    cur = get_zone(now)
    if is_target_zone(cur.zone) and cur.seed != last_seed:
        last_seed = cur.seed
        await channel.send(active_alert(cur))
    # Cow warning
    for i in range(300):
        z = get_zone(now, i)
        if z.zone == "Cow Level":
            warn_at = z.ts_ms - 600000
            if warn_at <= now < warn_at + 30000 and z.seed != last_cow_seed:
                last_cow_seed = z.seed
                await channel.send(cow_warning(z))
            break
    # Abaddon warning
    for i in range(300):
        z = get_zone(now, i)
        if z.zone == "Abaddon, the Pit of Acheron, and the Infernal Pit":
            warn_at = z.ts_ms - 600000
            if warn_at <= now < warn_at + 30000 and z.seed != last_abaddon_seed:
                last_abaddon_seed = z.seed
                await channel.send(abaddon_warning(z))
            break

@zone_watcher.before_loop
async def before_zone_watcher():
    await bot.wait_until_ready()

bot.run(DISCORD_TOKEN)