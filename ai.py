import os
import re
import asyncio
import logging
import datetime
import base64
import requests
import discord
from discord.ext import commands
from discord.ui import Select, View
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
VIRUSTOTAL_API_KEY = os.getenv("VIRUSTOTAL_API_KEY")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s:%(message)s")
logger = logging.getLogger("orca")

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

invites = {}
log_channels = {}
quote_channels = {}

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
    activity = discord.Game(name="WATCHING ORCA SERVERS")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    for guild in bot.guilds:
        invites[guild.id] = await guild.invites()
    logger.info(f"ONLINE {bot.user}")

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

async def query_virustotal(url):
    headers = {"x-apikey": VIRUSTOTAL_API_KEY}
    submit = requests.post("https://www.virustotal.com/api/v3/urls", headers=headers, data={"url": url})
    if submit.status_code not in (200, 201):
        return None
    analysis_id = submit.json()["data"]["id"]
    await asyncio.sleep(10)
    report = requests.get(f"https://www.virustotal.com/api/v3/analyses/{analysis_id}", headers=headers)
    if report.status_code != 200:
        return None
    stats = report.json()["data"]["attributes"]["stats"]
    return stats

@bot.command()
async def scan(ctx, url: str):
    if not VIRUSTOTAL_API_KEY:
        await ctx.send("VirusTotal key missing")
        return
    await ctx.send("Scanning")
    stats = await query_virustotal(url)
    if not stats:
        await ctx.send("Scan failed")
        return
    embed = discord.Embed(title="Scan Result", color=discord.Color.blue())
    for k, v in stats.items():
        embed.add_field(name=k, value=str(v), inline=True)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def scanserver(ctx, limit: int = 100):
    found = []
    for channel in ctx.guild.text_channels:
        async for msg in channel.history(limit=limit):
            if contains_suspicious_link(msg.content):
                found.append(msg.jump_url)
    if found:
        await ctx.send("\n".join(found[:10]))
    else:
        await ctx.send("No suspicious links found")

class ChoiceSelect(Select):
    def __init__(self):
        self.message_map = {
            "rtb": "TO ALL ACTIVE MEMBERS CONNECT TO RADIO AND RTB",
            "meetup": "REQUESTING MEET UP AT DESIGNATED LOCATION",
            "issues": "REQUESTING MEETUP TO DISCUSS ISSUES",
            "gwar": "ONGOING GANG WAR DECLARATION"
        }
        options = [
            discord.SelectOption(label="RTB", value="rtb"),
            discord.SelectOption(label="Meetup", value="meetup"),
            discord.SelectOption(label="Issues", value="issues"),
            discord.SelectOption(label="Gang War", value="gwar")
        ]
        super().__init__(placeholder="Choose message", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(self.message_map[self.values[0]], ephemeral=True)

@bot.command()
async def template(ctx):
    view = View()
    view.add_item(ChoiceSelect())
    await ctx.send("Select template", view=view)

class LexusGpackSelect(Select):
    def __init__(self):
        self.message_map = {
            "v7": "LEXUS V7 LINK",
            "v8": "LEXUS V8 LINK",
            "v10": "LEXUS V10 LINK"
        }
        options = [
            discord.SelectOption(label="V7", value="v7"),
            discord.SelectOption(label="V8", value="v8"),
            discord.SelectOption(label="V10", value="v10")
        ]
        super().__init__(placeholder="Choose pack", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(self.message_map[self.values[0]], ephemeral=True)

@bot.command()
async def lexus(ctx):
    view = View()
    view.add_item(LexusGpackSelect())
    await ctx.send("Choose Lexus pack", view=view)

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing")

bot.run(TOKEN)
