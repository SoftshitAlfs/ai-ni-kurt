import os
import re
import asyncio
import logging
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

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

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

async def query_virustotal(url):
    headers = {"x-apikey": VIRUSTOTAL_API_KEY}
    submit = requests.post("https://www.virustotal.com/api/v3/urls", headers=headers, data={"url": url})
    if submit.status_code not in (200, 201):
        return None, None
    analysis_id = submit.json()["data"]["id"]
    await asyncio.sleep(10)
    report = requests.get(f"https://www.virustotal.com/api/v3/analyses/{analysis_id}", headers=headers)
    if report.status_code != 200:
        return None, None
    stats = report.json()["data"]["attributes"]["stats"]
    results = report.json()["data"]["attributes"]["results"]
    return stats, results

@bot.command()
async def scan(ctx, url: str):
    if ctx.author.id in bot_whitelist:
        await ctx.send("User is whitelisted")
        return
    if not VIRUSTOTAL_API_KEY:
        await ctx.send("VirusTotal key missing")
        return

    msg = await ctx.send("Scanning ░░░░░░░░░░")

    async def animate():
        bars = [
            "░░░░░░░░░░","█░░░░░░░░░","██░░░░░░░░","███░░░░░░░",
            "████░░░░░░","█████░░░░░","██████░░░░",
            "███████░░░","████████░░","█████████░","██████████"
        ]
        while True:
            for b in bars:
                await msg.edit(content=f"Scanning {b}")
                await asyncio.sleep(0.4)

    anim = asyncio.create_task(animate())
    stats, results = await query_virustotal(url)
    anim.cancel()

    if not stats:
        await msg.edit(content="Scan failed")
        return

    total = sum(stats.values())
    def bar(value):
        filled = int((value / total) * 10) if total > 0 else 0
        return "█" * filled + "░" * (10 - filled)

    embed = discord.Embed(title="VirusTotal Scan Result", color=discord.Color.blue())
    embed.add_field(name="Malicious", value=f"{stats.get('malicious',0)} {bar(stats.get('malicious',0))}", inline=False)
    embed.add_field(name="Suspicious", value=f"{stats.get('suspicious',0)} {bar(stats.get('suspicious',0))}", inline=False)
    embed.add_field(name="Undetected", value=f"{stats.get('undetected',0)} {bar(stats.get('undetected',0))}", inline=False)
    embed.add_field(name="Timeout", value=f"{stats.get('timeout',0)} {bar(stats.get('timeout',0))}", inline=False)

    engine_count = 0
    max_fields = 20
    for engine, data in results.items():
        if engine_count >= max_fields:
            break
        embed.add_field(
            name=engine,
            value=f"Category: {data.get('category','unknown')}\nResult: {data.get('result','Clean')}",
            inline=True
        )
        engine_count += 1

    remaining = len(results) - max_fields
    if remaining > 0:
        embed.add_field(name="And more...", value=f"{remaining} engines not shown", inline=False)

    embed.set_footer(text=f"Total Engines Scanned: {len(results)}")
    await msg.edit(content=None, embed=embed)

@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong {round(bot.latency * 1000)}ms")

@bot.command()
@commands.has_permissions(administrator=True)
async def whitelist(ctx, action: str, user: discord.User = None):
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

class HelpSelect(Select):
    def __init__(self, ctx):
        self.ctx = ctx
        self.categories = {
            "Moderation": ["whitelist", "scanserver"],
            "Scanning": ["scan", "ping"],
            "Templates": ["template", "lexus"]
        }
        options = [discord.SelectOption(label=k, value=k) for k in self.categories.keys()]
        super().__init__(placeholder="Select category", options=options)

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        cmds = self.categories.get(category, [])
        desc = "\n".join([f"!{c}" for c in cmds])
        embed = discord.Embed(title=f"{category} Commands", description=desc, color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed)

@bot.command()
async def help(ctx):
    view = View()
    view.add_item(HelpSelect(ctx))
    embed = discord.Embed(title="Help Menu", description="Select a category to view commands", color=discord.Color.blue())
    await ctx.send(embed=embed, view=view)

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
