import asyncio
import discord
import utils

from commands import command_status, commands_git, commands_statsroyale
from datetime import datetime, time, timedelta
from mongo_models import command_log

admin_commands_map = {
    "cleanup": {
        "author": "iGio90",
        "description": "cleanup the channel.",
        "function": "cleanup"
    },
    "exec": {
        "author": "iGio90",
        "description": "run shell command",
        "function": "exec"
    },
    "restart": {
        "author": "iGio90",
        "description": "restart secRet. flush scripts",
        "function": "restart"
    },
    "status": {
        "author": "iGio90",
        "description": "bot services status",
        "function": "secret_status"
    }
}

dev_commands_map = {
    "history": {
        "author": "iGio90",
        "description": "commands history",
        "function": "commands_history"
    }
}

commands_map = {
    "commits": {
        "author": "iGio90",
        "description": "last 10 commits on secRet repo",
        "function": "commits"
    },
    "help": {
        "author": "iGio90",
        "description": "initial help",
        "function": "help"
    },
    "statsroyale": {
        "author": "iGio90",
        "description": "statsroyale commands",
        "function": "statsroyale"
    }
}


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
    :param: git_repo
    the git repository
    """

    def __init__(self, bus, discord_client, mongo_db, secret_server, secret_channel, git_repo):
        self.start_time = datetime.now().timestamp()
        self.bus = bus
        self.discord_client = discord_client
        self.mongo_db = mongo_db
        self.secret_server = secret_server
        self.secret_channel = secret_channel
        self.git_repo = git_repo

    async def cleanup(self, message):
        """
        clean the whole channel. delete all messages
        """
        c = len(await self.discord_client.purge_from(message.channel, limit=100000))
        await self.discord_client.send_message(message.channel, '**[*]** ' + str(c) + ' message deleted!')

    async def commands(self, message):
        """
        list the commands from both the maps
        """
        # admin commands
        embed = utils.build_commands_embed(admin_commands_map, 'admin commands', discord.Color.red())
        await self.discord_client.send_message(message.channel, embed=embed)

        # dev commands
        embed = utils.build_commands_embed(dev_commands_map, 'dev commands', discord.Color.blue())
        await self.discord_client.send_message(message.channel, embed=embed)

        # user commands
        embed = utils.build_commands_embed(commands_map, 'user commands', discord.Color.light_grey())
        await self.discord_client.send_message(message.channel, embed=embed)

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
                await self.discord_client.send_message(message.channel, "**[*]** removed " + str(c) + " entries")

    async def commits(self, message):
        """
        list last 10 commits in the repo
        """
        commits_embed = commands_git.build_commit_list_embed(self.git_repo)
        await self.discord_client.send_message(message.channel, embed=commits_embed)

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

    async def help(self, message):
        """
        print help
        """
        embed = discord.Embed(title='', type='rich',
                              description="goal is to build me as an automated **bot** with whatever feature "
                                          "people would like to code. I'll soon run on a virtual"
                                          " machine with **root** privileges,"
                                          "but meanwhile, I can already do something:\n\n",
                              color=discord.Colour.dark_red())
        embed.set_thumbnail(url="http://paulcilwa.com/Content/Science/Science.png")
        embed.set_author(name="secRet", url="https://secret.re")
        embed.add_field(name="!commands", value="something to interact with me", inline=False)
        embed.add_field(name="!devme", value="info and help about coding features", inline=False)
        embed.add_field(name="!rules", value="a world without rules... mhhh chaos", inline=False)
        await self.discord_client.send_message(message.channel, embed=embed)

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
        await command_status.secret_status(message, self.discord_client, self.mongo_db,
                                    self.start_time, self.secret_channel)

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

        # parse base commands (not mapped)
        if content == 'commands':
            await self.commands(message)
        elif content == 'rules':
            await self.rules(message)
        elif content == 'devme':
            await self.devme(message)
        elif base_command[0] in commands_map:
            # user commands
            cmd_funct = self._get_command_function(commands_map, base_command)
        elif base_command[0] in dev_commands_map and utils.is_dev(message.author):
            # dev commands
            cmd_funct = self._get_command_function(dev_commands_map, base_command)
        elif base_command[0] in admin_commands_map and utils.is_admin(message.author):
            # admin commands
            cmd_funct = self._get_command_function(admin_commands_map, base_command)

        if cmd_funct is not None:
            # log command issued on mongo
            cmd_log = command_log.CommandLog(user_name=message.author.name,
                                             user_id=message.author.id,
                                             command=content)
            cmd_log.save()

            await cmd_funct(message)

    def _get_command_function(self, map, base_command):
        command = map[base_command[0]]
        return getattr(self, command["function"])
