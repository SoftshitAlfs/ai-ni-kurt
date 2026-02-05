import os
import re
import asyncio
import logging
import aiohttp
import discord
from discord.ext import commands
from discord.ui import Select, View, Button
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
VIRUSTOTAL_API_KEY = os.getenv("VIRUSTOTAL_API_KEY")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(message)s")
logger = logging.getLogger("orca")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

invites = {}
log_channels = {}
bot_whitelist = []

suspicious_patterns = [
    r"https?://[^\s]*image-logger[^\s]*",
    r"https?://[^\s]*keylogger[^\s]*",
    r"https?://[^\s]*tokengrabber[^\s]*",
    r"https?://[^\s]*grabber[^\s]*",
    r"https?://[^\s]*logger[^\s]*",
]

def contains_suspicious_link(text):
    for pattern in suspicious_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

@bot.event
async def on_ready():
    activity = discord.Game(name="WATCHING THIS SERVER")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    for guild in bot.guilds:
        invites[guild.id] = await guild.invites()
    logger.info(f"ONLINE {bot.user}")

@bot.event
async def on_guild_join(guild):
    if guild.owner_id not in bot_whitelist:
        await guild.leave()

async def send_log_message(guild_id, member, action):
    channel_id = log_channels.get(guild_id)
    if not channel_id:
        return
    channel = bot.get_channel(channel_id)
    if not channel:
        return
    embed = discord.Embed(color=discord.Color.dark_red(), timestamp=discord.utils.utcnow())
    embed.set_author(name="ORCA")
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.add_field(name="Member", value=f"{member}", inline=True)
    embed.add_field(name="ID", value=str(member.id), inline=True)
    embed.add_field(name="Action", value=action, inline=False)
    await channel.send(embed=embed)

@bot.event
async def on_member_join(member):
    await send_log_message(member.guild.id, member, "Member joined")

@bot.event
async def on_member_remove(member):
    await send_log_message(member.guild.id, member, "Member left")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if contains_suspicious_link(message.content):
        embed = discord.Embed(description="Suspicious link detected", color=discord.Color.red())
        await message.channel.send(embed=embed)
    for attachment in message.attachments:
        if contains_suspicious_link(attachment.url) or contains_suspicious_link(attachment.filename):
            embed = discord.Embed(description="Suspicious attachment detected", color=discord.Color.red())
            await message.channel.send(embed=embed)
            break
    await bot.process_commands(message)

async def vt_scan_url(session, url):
    headers = {"x-apikey": VIRUSTOTAL_API_KEY}
    async with session.post("https://www.virustotal.com/api/v3/urls", headers=headers, data={"url": url}) as resp:
        if resp.status not in (200, 201):
            return None, None
        data = await resp.json()
    analysis_id = data["data"]["id"]
    await asyncio.sleep(10)
    async with session.get(f"https://www.virustotal.com/api/v3/analyses/{analysis_id}", headers=headers) as r:
        if r.status != 200:
            return None, None
        report = await r.json()
    stats = report["data"]["attributes"]["stats"]
    results = report["data"]["attributes"]["results"]
    return stats, results

class VTPageView(View):
    def __init__(self, embed_pages):
        super().__init__()
        self.pages = embed_pages
        self.current = 0

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray)
    async def prev(self, interaction: discord.Interaction, button: Button):
        if self.current > 0:
            self.current -= 1
            await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next(self, interaction: discord.Interaction, button: Button):
        if self.current < len(self.pages)-1:
            self.current += 1
            await interaction.response.edit_message(embed=self.pages[self.current], view=self)

@bot.command()
async def scan(ctx, url: str):
    if ctx.author.id in bot_whitelist:
        await ctx.send("User is whitelisted")
        return
    if not VIRUSTOTAL_API_KEY:
        await ctx.send("VirusTotal key missing")
        return

    async with aiohttp.ClientSession() as session:
        msg = await ctx.send("Scanning ░░░░░░░░░░")
        await ctx.trigger_typing()

        stats, results = await vt_scan_url(session, url)
        if not stats:
            await msg.edit(content="Scan failed")
            return

        total = sum(stats.values())
        def bar(value):
            filled = int((value / total) * 10) if total > 0 else 0
            return "█"*filled + "░"*(10-filled)

        embed_main = discord.Embed(title="VirusTotal Scan Result", color=discord.Color.blue())
        embed_main.add_field(name="Malicious", value=f"{stats.get('malicious',0)} {bar(stats.get('malicious',0))}", inline=False)
        embed_main.add_field(name="Suspicious", value=f"{stats.get('suspicious',0)} {bar(stats.get('suspicious',0))}", inline=False)
        embed_main.add_field(name="Undetected", value=f"{stats.get('undetected',0)} {bar(stats.get('undetected',0))}", inline=False)
        embed_main.add_field(name="Timeout", value=f"{stats.get('timeout',0)} {bar(stats.get('timeout',0))}", inline=False)

        # Split results into pages of 20 fields each
        embeds = []
        engines = list(results.items())
        while engines:
            embed = discord.Embed(color=discord.Color.orange())
            for _ in range(20):
                if not engines:
                    break
                engine, data = engines.pop(0)
                category = data.get("category","unknown")
                result = data.get("result","Clean")
                color = discord.Color.green() if category in ["undetected","harmless"] else discord.Color.red()
                embed.add_field(name=engine, value=f"Category: {category}\nResult: {result}", inline=True)
            embeds.append(embed)

        if embeds:
            view = VTPageView(embeds)
            await msg.edit(content=None, embed=embeds[0], view=view)
        else:
            await msg.edit(content=None, embed=embed_main)

@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong {round(bot.latency*1000)}ms")

@bot.command()
@commands.has_permissions(administrator=True)
async def whitelist(ctx, action: str, user: discord.User=None):
    action = action.lower()
    if action == "add" and user:
        if user.id not in bot_whitelist:
            bot_whitelist.append(user.id)
            await ctx.send("User added")
        else:
            await ctx.send("User already whitelisted")
    elif action == "remove" and user:
        if user.id in bot_whitelist:
            bot_whitelist.remove(user.id)
            await ctx.send("User removed")
        else:
            await ctx.send("User not in whitelist")
    elif action == "list":
        if not bot_whitelist:
            await ctx.send("Whitelist empty")
        else:
            await ctx.send("\n".join([f"<@{u}>" for u in bot_whitelist]))
    else:
        await ctx.send("Invalid usage")

@bot.command()
@commands.has_permissions(administrator=True)
async def scanserver(ctx, limit: int=100):
    found = []
    for channel in ctx.guild.text_channels:
        async for msg in channel.history(limit=limit):
            if contains_suspicious_link(msg.content):
                found.append(msg.jump_url)
    if found:
        await ctx.send("\n".join(found[:10]))
    else:
        await ctx.send("No suspicious links found")



if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing")
bot.run(TOKEN)
s
