#!/usr/bin/env python3

import os
import time
import traceback
import discord
from dataclasses import dataclass
from discord.ext import commands, tasks
from dotenv import load_dotenv

# ======================
# ENV / CONFIG
# ======================

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

# ======================
# ZONE DATA
# ======================

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
    "Lost City, Ancient Tunnels and Claw Viper Temple",
    "Canyon of the Magi and Tal Rasha's Tomb",
    "Lut Gholein Sewers and the Palace Cellars",
    "Arcane Sanctuary",
    "Spider Forest, Arachnid Lair and Spider Cavern",
    "Great Marsh and the Swampy Pit",
    "Flayer Jungle and the Flayer Dungeon",
    "Lower Kurast and the Kurast Sewers",
    "Kurast Bazaar, Ruined Temple and Disused Fane",
    "Upper Kurast, the Forgotten Reliquary and Forgotten Temple",
    "Travincal, the Ruined Fane and Disused Reliquary",
    "Durance of Hate",
    "Outer Steppes and the Plains of Despair",
    "City of the Damned and the River of Flame",
    "Chaos Sanctuary",
    "Bloody Foothills and the Frigid Highlands",
    "Arreat Plateau, Crystalline Passage and Frozen River",
    "Glacial Trail, Drifter Cavern and Frozen Tundra",
    "Ancients' Way and the Icy Cellar",
    "Nihlathak's Temple",
    "Abaddon, the Pit of Acheron and the Infernal Pit",
    "Worldstone Keep and Throne of Destruction",
]

INTERVAL_MS = 900_000  # 15 minutes

# ======================
# ZONE LOGIC
# ======================

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
    b = ts // 86_400000
    seed = a + b

    idx = get_next_prng(seed, 214013, 2531011) % len(ZONES)
    return ZoneInfo(ZONES[idx], ts, seed)

def current_and_next():
    return [get_zone(n=i) for i in range(5)]

def is_target_zone(zone):
    return zone in {
        "Chaos Sanctuary",
        "Cow Level",
        "Stony Field and Tristram",
        "Abaddon, the Pit of Acheron and the Infernal Pit",
    }

def minutes_left_in_window(active_ts_ms, now_ms):
    return max(0, int((active_ts_ms + INTERVAL_MS - now_ms) // 60000))

def minutes_until(future_ts_ms, now_ms):
    return max(0, int((future_ts_ms - now_ms) // 60000))

ZONE_EMOJI = {
    "Chaos Sanctuary": "⚔️",
    "Cow Level": "🐮",
    "Stony Field and Tristram": "🪨",
    "Abaddon, the Pit of Acheron and the Infernal Pit": "🔥",
}

def cz_message(infos):
    now_ms = int(time.time() * 1000)
    lines = []

    # Current active zone
    active = infos[0]
    left = minutes_left_in_window(active.ts_ms, now_ms)
    emoji = ZONE_EMOJI.get(active.zone, "🗺️")
    lines.append(f"🟢 NOW  {emoji}  {active.zone} — {left}m left")

    # Next 4 upcoming zones
    labels = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
    for i, label in enumerate(labels, start=1):
        z = infos[i]
        mins = minutes_until(z.ts_ms, now_ms)
        emoji = ZONE_EMOJI.get(z.zone, "🗺️")
        lines.append(f"{label}  {emoji}  {z.zone} — in {mins}m")

    return "\n".join(lines)

# ======================
# DISCORD BOT
# ======================

intents = discord.Intents.default()
intents.message_content = True  # MUST also be enabled in Dev Portal

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

last_seed = None
last_cow_seed = None
last_abaddon_seed = None

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id={bot.user.id})")
    print("Loaded commands:", [c.name for c in bot.commands])
    if not zone_watcher.is_running():
        zone_watcher.start()

@bot.event
async def on_command_error(ctx, error):
    # ignore unknown commands
    if isinstance(error, commands.CommandNotFound):
        return

    # unwrap real exception
    original = getattr(error, "original", error)

    print("\n=== COMMAND ERROR ===")
    print("Message:", getattr(ctx.message, "content", None))
    print("Guild  :", getattr(getattr(ctx, "guild", None), "id", None), getattr(getattr(ctx, "guild", None), "name", None))
    print("Channel:", getattr(ctx.channel, "id", None), getattr(ctx.channel, "name", None))
    print("Author :", getattr(ctx.author, "id", None), getattr(ctx.author, "name", None))
    print("Error  :", repr(original))
    traceback.print_exception(type(original), original, original.__traceback__)
    print("=====================\n")

    # don't crash if bot can't reply
    try:
        await ctx.send(f"⚠️ `{type(original).__name__}`: {original}")
    except discord.Forbidden:
        pass

@bot.command(name="cz")
async def cz(ctx: commands.Context):
    await ctx.send(cz_message(current_and_next()))

@bot.command()
async def toggle(ctx: commands.Context):
    global notifications_enabled
    notifications_enabled = not notifications_enabled
    status = "🔔 **Notifications ENABLED**" if notifications_enabled else "🔕 **Notifications DISABLED**"
    await ctx.send(f"{status} Use `!toggle` again to switch back.")

# ======================
# BACKGROUND TASK
# ======================

@tasks.loop(seconds=30)
async def zone_watcher():
    global last_seed, last_cow_seed, last_abaddon_seed

    if not notifications_enabled:
        return

    channel = bot.get_channel(NOTIFY_CHANNEL_ID)
    if channel is None:
        print(f"Cannot see channel id={NOTIFY_CHANNEL_ID} (check permissions / correct ID)")
        return

    now = int(time.time() * 1000)
    cur = get_zone(now)

    if is_target_zone(cur.zone) and cur.seed != last_seed:
        last_seed = cur.seed
        active_emoji = {"Chaos Sanctuary": "⚔️", "Cow Level": "🐮", "Stony Field and Tristram": "🪨", "Abaddon, the Pit of Acheron and the Infernal Pit": "🔥"}.get(cur.zone, "🗺️")
        await channel.send(f"🟥 **ACTIVE NOW:** {active_emoji} {cur.zone}")
        await channel.send(cz_message(current_and_next()))

    # Cow warning
    for i in range(300):
        z = get_zone(now, i)
        if z.zone == "Cow Level":
            warn_at = z.ts_ms - 600_000
            if warn_at <= now < warn_at + 30_000 and z.seed != last_cow_seed:
                last_cow_seed = z.seed
                await channel.send("🐮 Cow Level in 10m")
            break

    # Abaddon warning
    for i in range(300):
        z = get_zone(now, i)
        if z.zone == "Abaddon, the Pit of Acheron and the Infernal Pit":
            warn_at = z.ts_ms - 600_000
            if warn_at <= now < warn_at + 30_000 and z.seed != last_abaddon_seed:
                last_abaddon_seed = z.seed
                await channel.send("🔥 Abaddon, the Pit of Acheron and the Infernal Pit in 10m")
            break

@zone_watcher.before_loop
async def before_zone_watcher():
    await bot.wait_until_ready()

# ======================
# RUN
# ======================

bot.run(DISCORD_TOKEN)
