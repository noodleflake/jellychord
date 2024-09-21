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
        "Title": item["Name"],
        "Id": item['Id']
    }
    global queues
    # TODO: properly do position in queue
    if not ctx.guild_id in queues:
        queues[ctx.guild_id] = []
    queues[ctx.guild_id].append(entry)

    if not ctx.voice_client:
        await startPlayer(ctx)


async def playHelperAlbum(item: str, guild: int | discord.Guild):
    pass


async def startPlayer(ctx: discord.ApplicationContext):
    vc = ctx.voice_client
    if not vc:
        av = ctx.author.voice
        if not av:
            ctx.respond('You are not in any voice channel')
            return
        else:
            vc = await av.channel.connect()
            await playTrack(ctx.guild)

async def playTrack(guild: discord.Guild):
    vc = guild.voice_client
    if vc.paused:
        vc.resume()
    else:
        await asyncio.to_thread(playNextTrack, guild)
        # br = vc.channel.bitrate
        # global playing
        # global queues
        # playing[guild.id] = queues[guild.id].pop(0)
        # url = JF_APICLIENT.getAudioHls(playing[guild.id]["Id"],br)
        # audio = discord.FFmpegOpusAudio(url, codec='copy')
        # await asyncio.to_thread(audio.read())
        # vc.play(audio, after=lambda e: await playNextTrack(guild, e))

def playNextTrack(guild, error=None):
    vc = guild.voice_client
    br = vc.channel.bitrate
    global playing
    global queues
    if queues[guild.id]:
        playing[guild.id] = queues[guild.id].pop(0)
        url = JF_APICLIENT.getAudioHls(playing[guild.id]["Id"],br)
        # use libopus until py-cord 2.7
        # change to 'copy' after py-cord 2.7 is out
        audio = discord.FFmpegOpusAudio(url, codec='libopus')
        audio.read() # remove this line when py-cord 2.7 is out
        vc.play(audio, after=lambda e: playNextTrack(guild, e))
    else:
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
    if not items:
        await ctx.respond('ID does not exist')
    else:
        await ctx.respond('Playing item')
        await playHelperTrack(items[0], ctx, 0)

bot.run(config['discord-token'])