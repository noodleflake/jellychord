import discord
import discord.ext
import asyncio
import yaml

from jfapi import JFAPI

with open('config.yml', 'r', encoding='utf8') as conffile:
    config = yaml.load(conffile, yaml.loader.Loader)

JF_APICLIENT = JFAPI(config['jf-server'],config['jf-apikey'])
LIMIT = max(1, min(config['search-limit'], 9))

queues = {}
playing = {}

bot = discord.Bot()

'''
Data Classes
'''


'''
Helper Functions
'''
async def searchHelper(term: str, limit: int = LIMIT, type:str = None):
    if type == 'Soundtrack':
        type = ['Audio']
    elif type == 'Album':
        type = ['MusicAlbum']
    else:
        type = ['Audio', 'MusicAlbum']
    
    res = await JF_APICLIENT.search(term, limit, type)
    return res

async def playHelperTrack(item: dict, ctx: discord.ApplicationContext, position: str):
    # url = JF_APICLIENT.getAudioHls(item["Id"])
    entry = {
        "Artists": item["Artists"],
        "Name": item["Name"],
        "Id": item['Id'],
        "Length": item['RunTimeTicks'] // 10000000
    }
    global queues
    if not ctx.guild_id in queues:
        queues[ctx.guild_id] = []
    if position == 'last':
        queues[ctx.guild_id].append(entry)
    else:
        queues[ctx.guild_id].insert(0, entry)

    if not ctx.voice_client:
        await startPlayer(ctx)
    elif position == 'now':
        ctx.voice_client.stop()

async def playHelperAlbum(item: dict, ctx: discord.ApplicationContext, position: str):
    tracks = await JF_APICLIENT.getAlbumTracks(item['Id'])
    entries = [{
        "Artists": item["Artists"],
        "Name": item["Name"],
        "Id": item['Id'],
        "Length": item['RunTimeTicks'] // 10000000
    } for item in tracks]

    global queues
    if not ctx.guild_id in queues:
        queues[ctx.guild_id] = []
    if position == 'last':
        queues[ctx.guild_id].extend(entries)
    else:
        queues[ctx.guild_id][0:0] = entries
    
    if not ctx.voice_client:
        await startPlayer(ctx)
    elif position == 'now':
        ctx.voice_client.stop()

async def startPlayer(ctx: discord.ApplicationContext):
    vc = ctx.voice_client
    if not vc:
        av = ctx.author.voice
        if av:
            vc = await av.channel.connect()
            await playTrack(ctx.guild)

async def playTrack(guild: discord.Guild):
    vc = guild.voice_client
    if vc.paused:
        vc.resume()
    else:
        await asyncio.to_thread(playNextTrack, guild)

def playNextTrack(guild, error=None):
    vc = guild.voice_client
    br = vc.channel.bitrate
    global playing
    global queues
    if guild.id in queues:
        playing[guild.id] = queues[guild.id].pop(0)
        if not queues[guild.id]: 
            queues.pop(guild.id)
        url = JF_APICLIENT.getAudioHls(playing[guild.id]["Id"],br)
        # use libopus until py-cord 2.7
        # change to 'copy' after py-cord 2.7 is out
        audio = discord.FFmpegOpusAudio(url, codec='libopus')
        audio.read() # remove this line when py-cord 2.7 is out
        vc.play(audio, after=lambda e: playNextTrack(guild, e))
    else:
        playing.pop(guild.id)
        asyncio.run_coroutine_threadsafe(vc.disconnect(), vc.loop)


'''
Bot Commands
'''
cmdgrp = bot.create_group(config['command-group'], guild_ids=[969479656069804063])

@cmdgrp.command()
async def search(ctx: discord.ApplicationContext, 
                 term: discord.Option(str),
                 type: discord.Option(str, choices=['Soundtrack', 'Album'], required=False)):
    
    res = await searchHelper(term, type=type)
    entries = [f'{i["Artists"][0]} - {i["Name"]}' for i in res]
    await ctx.respond('\n'.join(entries))

@cmdgrp.command()
async def play(ctx: discord.ApplicationContext,
               term: discord.Option(str),
               type: discord.Option(str, choices=['Soundtrack', 'Album'], required=False),
               when: discord.Option(str, choices=['now', 'next', 'last'], required=False)):

    res = await searchHelper(term, limit=1, type=type)

@cmdgrp.command()
async def playbyid(ctx: discord.ApplicationContext,
                   id: discord.Option(str),
                   when: discord.Option(str, choices=['now', 'next', 'last'], required=False)):
    items = await JF_APICLIENT.getItemsByIds([id])

    if items and not ctx.author.voice:
        await ctx.respond('You are not in any voice channel')
    elif items[0]["Type"] == "Audio":
        await ctx.respond('Playing track')
    elif items[0]["Type"] == "MusicAlbum":
        await ctx.respond('Playing Album')

    if not when:
        when = 'last'
    if not items:
        await ctx.respond('ID does not exist')
    elif items[0]["Type"] == "Audio":
        await playHelperTrack(items[0], ctx, when)
    elif items[0]["Type"] == "MusicAlbum":
        await playHelperAlbum(items[0], ctx, when)

@cmdgrp.command()
async def skip(ctx: discord.ApplicationContext):
    if not ctx.voice_client:
        await ctx.respond('Not currently playing')
    else:
        await ctx.respond('Skipping current track')
        ctx.voice_client.stop()

@cmdgrp.command()
async def nowplaying(ctx: discord.ApplicationContext):
    if ctx.guild_id in playing:
        track = playing[ctx.guild_id]
        if len(track["Artists"]) >= 1:
            await ctx.respond(f'Currently Playing: {track["Artists"][0]} - {track["Name"]}')
        else:
            await ctx.respond(f'Currently Playing: {track["Name"]}')
    else:
        await ctx.respond('Not Currently Playing')

@cmdgrp.command()
async def queue(ctx: discord.ApplicationContext):
    if ctx.guild_id in queues:
        tracks = queues[ctx.guild_id]
        strs = []
        for track in tracks:
            if len(track["Artists"]) >= 1:
                strs.append(f'{track["Artists"][0]} - {track["Name"]}')
            else:
                strs.append(f'{track["Name"]}')
        await ctx.respond(f'Tracks in queue:\n{"\n".join(strs)}')
    else:
        await ctx.respond('Empty Queue')

@cmdgrp.command()
async def start(ctx: discord.ApplicationContext):
    if ctx.guild_id in queues and ctx.author.voice and not ctx.voice_client:
        await ctx.respond('Starting Playback')
        await startPlayer(ctx)
    elif ctx.guild_id not in queues:
        await ctx.respond('No tracks to play')
    elif ctx.guild_id in playing or ctx.voice_client:
        await ctx.respond('Already Playing')
    else:
        await ctx.respond('You are not in any voice channel')

@cmdgrp.command()
async def pause(ctx: discord.ApplicationContext):
    if ctx.voice_client:
        await ctx.respond('Pausing playback')
        ctx.voice_client.pause()
    else:
        await ctx.respond('Not connect to any voice channel')

@cmdgrp.command()
async def resume(ctx: discord.ApplicationContext):
    if ctx.voice_client:
        await ctx.respond('Resuming playback')
        ctx.voice_client.resume()
    else:
        await ctx.respond('Not connect to any voice channel')

bot.run(config['discord-token'])