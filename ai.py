@bot.command()
async def scan(ctx, url: str):
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
