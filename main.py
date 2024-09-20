import discord
import asyncio
import yaml

with open('config.yml', 'r', encoding='utf8') as conffile:
    config = yaml.load(conffile, yaml.loader())

