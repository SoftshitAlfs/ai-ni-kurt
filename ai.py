import os,logging,discord,dotenv,datetime;from openai import OpenAI
logging.basicConfig(level=logging.INFO,format='%(asctime)s|%(levelname)s|%(message)s',datefmt='%H:%M:%S');_l=logging.getLogger(name)
dotenv.load_dotenv();_dt=os.getenv("DISCORD_TOKEN")or"";_gak=os.getenv("XAI_API_KEY")or""
try:
if not _gak:_l.warning("API Key missing.")
_ac=OpenAI(api_key=_gak,base_url="api.x.ai")
except Exception as e:_l.error(f"Client Init Error:{e}")
_i=discord.Intents.default();_i.message_content=True;_c=discord.Client(intents=_i);_am="grok-2-latest"
def _ct(t,l=4000):return[t[i:i+l]for i in range(0,len(t),l)]
@_c.event
async def on_ready():await _c.change_presence(activity=discord.Game(name="Orca AI"));_l.info(f"ONLINE:{_c.user}")
@_c.event
async def on_message(_m):
if _m.author==_c.user:return
if _c.user.mentioned_in(_m) or isinstance(_m.channel,discord.DMChannel):
_p=_m.content.replace(f'<@{_c.user.id}>','').strip()
if not _p:return
_l.info(f"Request from {_m.author}")
async with _m.channel.typing():
try:
_r=_ac.chat.completions.create(model=_am,messages=[{"role":"user","content":_p}])
_text=_r.choices[0].message.content
if _text:
_chs=_ct(_text)
for i,_ch in enumerate(_chs):
_e=discord.Embed(title="Generation Complete",description=_ch,color=0x5865F2,timestamp=datetime.datetime.now())
if i==0:
_u=_c.user.avatar.url if _c.user.avatar else None;_e.set_author(name="Orca AI",icon_url=_u)
if _u:_e.set_thumbnail(url=_u)
_e.set_image(url="cdn.discordapp.com")
_e.add_field(name="User",value=_m.author.display_name,inline=True)
_e.set_footer(text="Orca AI . Greets softshit holy");await _m.channel.send(embed=_e)
_l.info("Response delivered.")
else:await _m.channel.send("Empty response.")
except Exception as e:_l.error(f"Error:{e}");_ee=discord.Embed(title="Error",description=f"\n{str(e)}\n",color=0xED4245);await _m.channel.send(embed=_ee)
if name=="main":_c.run(_dt)
