import discord
import discord.ext
import asyncio
import yaml

from jfapi import JFAPI

with open('config.yml', 'r', encoding='utf8') as conffile:
    config = yaml.load(conffile, yaml.loader.Loader)

JF_APICLIENT = JFAPI(config['jf-server'],config['jf-apikey'])
LIMIT = max(1, min(config['search-limit'], 25))
DEBUG = config["enable-debug"]
if DEBUG:
    DEBUG_SERVER = config["debug-server"]

queues = {}
playing = {}

bot = discord.Bot()

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

async def playHelperGeneric(item: dict, ctx: discord.ApplicationContext, position: str):
    if item["Type"] == "MusicAlbum":
        await playHelperAlbum(item, ctx, position)
    else:
        await playHelperTrack(item, ctx, position)

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

def getTrackString(item: dict, artistLimit: int = 1, type: bool = False):

    if not type:
        res = ''
    elif item["Type"] == "MusicAlbum":
        res = 'Album: '
    else:
        res = 'Track: '

    if len(item["Artists"]) > artistLimit:
        res += 'Various Artists'
    elif item["Artists"]:
        res += ','.join(item["Artists"])
    
    if item["Artists"]:
        res += ' - '
    
    res += item["Name"]
    return res

'''
Bot Commands
'''
if DEBUG:
    cmdgrp = bot.create_group(config['command-group'], guild_ids=[DEBUG_SERVER])
else:
    cmdgrp = bot.create_group(config['command-group'])

@cmdgrp.command()
async def search(ctx: discord.ApplicationContext, 
                 term: discord.Option(str),
                 type: discord.Option(str, choices=['Soundtrack', 'Album'], required=False),
                 when: discord.Option(str, choices=['now', 'next', 'last'], required=False) = 'last'):
    
    await ctx.defer(invisible=True)
    res = await searchHelper(term, type=type)
    if not res:
        await ctx.respond("No items match your query.")
    elif not ctx.author.voice and not ctx.voice_client:
        await ctx.respond('You are not in any voice channel')
    else:
        entries = []
        for i in range(len(res)):
            entries.append(discord.SelectOption(
                label = getTrackString(res[i]),
                value = str(i)
            ))
        # entries = [discord.SelectOption(label=getTrackString(i, type=True)) for i in res]

        class searchSelectView(discord.ui.View):
            def __init__(self):
                super(searchSelectView, self).__init__()
                self._selected = False

            async def on_timeout(self):
                if not self._selected:
                    self.disable_all_items()
                    await self.message.edit("Selection timed out.")

            @discord.ui.select(
                select_type=discord.ComponentType.string_select,
                max_values=1, min_values=1,
                options=entries
            )
            async def select_callback(self, select: discord.ui.Select, interaction: discord.Interaction):
                self._selected = True
                await interaction.response.edit_message(content=f'Playing {getTrackString(res[0], type=True)}',view=None)
                await playHelperGeneric(res[int(select.values[0])], ctx, when)

        await ctx.respond('Select an item to play:', view=searchSelectView())

@cmdgrp.command()
async def play(ctx: discord.ApplicationContext,
               term: discord.Option(str),
               type: discord.Option(str, choices=['Soundtrack', 'Album'], required=False),
               when: discord.Option(str, choices=['now', 'next', 'last'], required=False) = 'last'):
    
    await ctx.defer(invisible=True)
    res = await searchHelper(term, limit=1, type=type)

    if not res:
        await ctx.respond('No items match your query')
    elif not ctx.author.voice and not ctx.voice_client:
        await ctx.respond('You are not in any voice channel')
    else:
        await ctx.respond(f'Playing {getTrackString(res[0], type=True)}')
        await playHelperGeneric(res[0], ctx, when)

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
        await ctx.respond(f'Currently Playing: {getTrackString(track)}')
    else:
        await ctx.respond('Not Currently Playing')

@cmdgrp.command()
async def queue(ctx: discord.ApplicationContext):
    if ctx.guild_id in queues:
        tracks = queues[ctx.guild_id]
        strs = [getTrackString(track) for track in tracks]
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

'''
Debug Commands
'''
if DEBUG:
    dbgcmd = bot.create_group('jfmbdbg', guild_ids=[DEBUG_SERVER])

    @dbgcmd.command()
    async def playbyid(ctx: discord.ApplicationContext,
                    id: discord.Option(str),
                    when: discord.Option(str, choices=['now', 'next', 'last'], required=False) = 'last'):
        
        await ctx.defer(invisible=True)
        res = await JF_APICLIENT.getItemsByIds([id])

        if not res:
            await ctx.respond('No items match your query')
        elif not ctx.author.voice:
            await ctx.respond('You are not in any voice channel')
        else:
            await ctx.respond(f'Playing {getTrackString(res[0], type=True)}')
            await playHelperGeneric(res[0], ctx, when)


bot.run(config['discord-token'])