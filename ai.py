import os,logging,discord,dotenv,datetime,asyncio;from google import genai
logging.basicConfig(level=logging.INFO,format='%(asctime)s|%(levelname)s|%(message)s',datefmt='%H:%M:%S');_l=logging.getLogger(__name__)
dotenv.load_dotenv();_dt=os.getenv("DISCORD_TOKEN")or"";_gak=os.getenv("GEMINI_API_KEY")or""
try:
 if not _gak:_l.warning("API Key missing.")
 _ac=genai.Client(api_key=_gak)
except Exception as e:_l.error(f"Client Init Error:{e}")
_i=discord.Intents.default();_i.message_content=True;_c=discord.Client(intents=_i);_md="gemini-1.5-flash"
def _gm():
 try:
  _ms=list(_ac.models.list())
  for m in _ms:
   if "1.5" in m.name and "flash" in m.name:return m.name
  return "gemini-1.5-flash"
 except:return "gemini-1.5-flash"
def _ct(t,l=4000):return[t[i:i+l]for i in range(0,len(t),l)]
@_c.event
async def on_ready():_l.info(f"ONLINE:{_c.user} MODEL:{_md}")
@_c.event
async def on_message(_m):
 if _m.author==_c.user:return
 if (_c.user in _m.mentions and not _m.mention_everyone) or isinstance(_m.channel,discord.DMChannel):
  _p=_m.content.replace(f'<@{_c.user.id}>','').strip()
  if not _p:return
  _l.info(f"Request from {_m.author}")
  async with _m.channel.typing():
   _r=None;global _md;_last_err=""
   for _t in range(5):
    try:
     _r=_ac.models.generate_content(model=_md,contents=_p);break
    except Exception as e:
     _last_err=str(e)
     if "429" in _last_err:
      _wait=2**(_t+1);_l.warning(f"429 Hit on {_md}. Waiting {_wait}s...");await asyncio.sleep(_wait);continue
     elif "404" in _last_err:
      _l.warning("404 Hit. Switching model...");_md=_gm();await asyncio.sleep(1);continue
     else:break 
   if _r and _r.text:
    _chs=_ct(_r.text)
    for i,_ch in enumerate(_chs):
     _e=discord.Embed(title="Generation Complete",description=_ch,color=0x5865F2,timestamp=datetime.datetime.now())
     if i==0:
      _u=_c.user.avatar.url if _c.user.avatar else None;_e.set_author(name="Orca AI",icon_url=_u)
      if _u:_e.set_thumbnail(url=_u)
      _e.set_image(url="https://cdn.discordapp.com/attachments/1379846639069691965/1432996028126068756/orcawrld.gif?ex=6981a50c&is=6980538c&hm=cfe5d06c8ae07a21d39fcd228547b9226b2c7b8a00ad5164e8430bd2c4683e93&")
      _e.add_field(name="User",value=_m.author.display_name,inline=True)
     _e.set_footer(text="Orca AI • Greets softshit holy");await _m.channel.send(embed=_e)
    _l.info("Response delivered.")
   else:
    _msg="System Busy."
    if "429" in _last_err:_msg="Rate Limit Hit (Wait 30s)."
    elif "404" in _last_err:_msg="Model Config Error."
    await _m.channel.send(_msg)
if __name__=="__main__":_c.run(_dt)
