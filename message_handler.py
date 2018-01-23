import json
import urllib

import discord
import utils

from commands import command_help, command_status, \
    commands_git, commands_statsroyale
from datetime import datetime
from mongo_models import command_log


class MessageHandler(object):
    """
    handle messages from discord #secRet channel.
    code here your stuffs keeping the following flow:
    1) add the command to the map (always follow alphabetical order)
    2) add the function handler to this class, which must be async
    3) **OPTIONAL** check other functions to have a very quick understanding
    4) if it's too much code, consider create your own class/scripts inside commands package
       and feed it with client, bus and whatever is needed

    :param: bus
    event bus
    :param: discord_client
    the discord client
    :param: mongo_db
    instance of mongo db
    :param: secret_server
    instance of discord server object holding server id
    :param: secret_channel
    instance of discord channel object holdin #secRet id
    :param: git_client
    instance of git client
    :param: git_repo
    the git repository
    """

    def __init__(self, bus, discord_client, mongo_db, secret_server, secret_channel, git_client, git_repo):
        # load maps
        with open('commands/map/admin_commands.json', 'r') as f:
            self.admin_commands_map = json.load(f)
        with open('commands/map/dev_commands.json', 'r') as f:
            self.dev_commands_map = json.load(f)
        with open('commands/map/user_commands.json', 'r') as f:
            self.commands_map = json.load(f)

        self.last_command = {}
        self.start_time = datetime.now().timestamp()
        self.bus = bus
        self.discord_client = discord_client
        self.mongo_db = mongo_db
        self.secret_server = secret_server
        self.secret_channel = secret_channel
        self.git_client = git_client
        self.git_repo = git_repo

    async def cleanup(self, message):
        """
        clean the whole channel. delete all messages
        """
        c = len(await self.discord_client.purge_from(message.channel, limit=100000))
        await self.discord_client.send_message(
            message.channel,
            embed=utils.simple_embed('done',
                                     str(c) + " message deleted",
                                     discord.Color.dark_green()))

    async def commands(self, message):
        """
        list the commands
        """
        await command_help.commands(message, self.discord_client, self.admin_commands_map,
                                    self.dev_commands_map, self.commands_map)

    async def commands_history(self, message):
        cmd_list = message.content.split(" ")
        if len(cmd_list) == 1:
            embed = utils.build_default_embed('commands history', '-', discord.Color.teal(), icon=False)
            for log in command_log.CommandLog.objects[:10]:
                embed.add_field(name=log.user_name, value=log.command, inline=False)
            await self.discord_client.send_message(message.channel, embed=embed)
        else:
            if cmd_list[1] == 'clear':
                c = command_log.CommandLog.objects.count()
                command_log.CommandLog.drop_collection()
                await self.discord_client.send_message(message.channel,
                                                       embed=utils.simple_embed('done',
                                                                                "removed " + str(c) + " entries",
                                                                                discord.Color.dark_green()))

    async def devme(self, message):
        s = open('DOCUMENTATION.md', 'r')
        msg = s.read()
        l = 0
        msg_len = len(msg)
        # message is too long :S
        while l <= msg_len:
            try:
                m = msg[l:l + 1000]
            except Exception as e:
                m = msg_len[l:msg_len - 1]
            l += 1000
            embed = utils.build_default_embed('', '', discord.Color.dark_green())
            embed.add_field(name="contribute and improve secRet dBot", value=m, inline=False)
            await self.discord_client.send_message(message.channel, embed=embed)

    async def exec(self, message):
        cmd = message.content.replace("!exec ", "")
        r = utils.run_shell_command(cmd)
        for line in r:
            await self.discord_client.send_message(message.channel, line)

    async def git(self, message):
        await commands_git.git(message, self.discord_client, self.git_client, self.git_repo, self.bus)

    async def help(self, message):
        """
        print help
        """
        await command_help.help(message, self.discord_client, [
            self.admin_commands_map, self.dev_commands_map, self.commands_map
        ])

    async def pr(self, message):
        await commands_git.pr(message, self.discord_client, self.git_repo)

    async def qr_generate(self, message):
        embed = discord.Embed(title='QR Code generator', type='rich',
                              color=discord.Colour.green())
        message_data = message.content[4:]
        data = urllib.parse.quote_plus(message_data)
        if data is "":
            embed.add_field(name="Error", value="Please man, give me some data!", inline=False)
        else:
            if len(message_data) > 300:
                embed.add_field(name="Error", value="Data must be < 300 char", inline=False)
            else:
                embed.set_image(url="https://api.qrserver.com/v1/create-qr-code/?data=" + data + "&size=200x200")

        await self.discord_client.send_message(message.channel, embed=embed)

    async def repeat(self, message):
        if 'function' in self.last_command and 'message' in self.last_command:
            if message.author.id == self.last_command['message'].author.id:
                await self.last_command['function'](self.last_command['message'])

    async def restart(self, message):
        """
        restart the scripts (update changes)
        """
        self.bus.emit('secret_restart')

    async def rules(self, message):
        """
        print rules
        """
        embed = utils.build_default_embed('', '', discord.Color.dark_green())
        s = open('RULES.md', 'r')
        msg = s.read()
        embed.add_field(name="Rules of the house", value=msg, inline=False)
        await self.discord_client.send_message(message.channel, embed=embed)

    async def secret_status(self, message):
        await command_status.secret_status(message, self.discord_client, self.git_client,
                                           self.mongo_db, self.start_time, self.secret_channel)

    async def statsroyale(self, message):
        await commands_statsroyale.handle(self.discord_client, message)

    async def on_message(self, message):
        """
        don't touch this! keep it abstract
        """

        # we don't want interaction in any other channels
        if message.channel.id != self.secret_channel.id:
            return

        # quick content reference
        content = message.content

        # we also want to skip anything that doesn't start with the prefix
        if not content.startswith("!"):
            return

        # strip prefix
        content = content[1:]

        # get base command
        base_command = content.split(" ")

        # the function to call
        cmd_funct = None

        if base_command[0] in self.commands_map:
            # user commands
            cmd_funct = self._get_command_function(self.commands_map, base_command)
        elif base_command[0] in self.dev_commands_map and utils.is_dev(message.author):
            # dev commands
            cmd_funct = self._get_command_function(self.dev_commands_map, base_command)
        elif base_command[0] in self.admin_commands_map and utils.is_admin(message.author):
            # admin commands
            cmd_funct = self._get_command_function(self.admin_commands_map, base_command)

        if cmd_funct is not None:
            # store last command function for repeat
            if base_command[0] != '!':
                self.last_command['function'] = cmd_funct
                self.last_command['message'] = message

            # log command issued on mongo
            cmd_log = command_log.CommandLog(user_name=message.author.name,
                                             user_id=message.author.id,
                                             command=content)
            cmd_log.save()

            await cmd_funct(message)

    def _get_command_function(self, map, base_command):
        command = map[base_command[0]]
        return getattr(self, command["function"])
