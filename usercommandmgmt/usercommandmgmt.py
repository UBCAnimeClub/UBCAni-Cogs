from redbot.core import Config, checks, commands, data_manager
from .configurable import *
from .commanddatahandler import *
import discord
from discord.utils import get
import inspect
import sys
import os
import pickle
from redbot.cogs.customcom import CustomCommands
from redbot.cogs.customcom.customcom import (
    CustomCommands,
    CommandObj,
    NotFound,
    ArgParseError,
    CommandNotEdited,
)


class CCError(Exception):
    pass


class AlreadyExists(CCError):
    pass


class ArgParseError(CCError):
    pass


class NotFound(CCError):
    pass


class OnCooldown(CCError):
    pass


class CommandNotEdited(CCError):
    pass


class Usercommandmgmt(CustomCommands):
    """Custom user command limit enforcements for user"""

    def __init__(self, bot):
        super().__init__(bot)
        self.save_file = os.path.join(
            data_manager.cog_data_path(cog_instance=self), "user commands.json"
        )

        self.config_file = os.path.join(
            data_manager.cog_data_path(cog_instance=self), "config.json"
        )

        self.queue_cache = os.path.join(
            data_manager.cog_data_path(cog_instance=self), "queue.p"
        )

        if not os.path.isfile(self.save_file):
            with open(self.save_file, "w+") as f:
                empty = {"db": []}
                json.dump(empty, f, indent=2)

        if not os.path.isfile(self.config_file):
            with open(self.config_file, "w+") as f:
                default = {
                    "role_cmd_limits": [
                        {"Tier 1 Simp": 1, "Tier 2 Simp": 3, "Tier 3 Simp": 5}
                    ],
                    "command_moderation": True,
                    "mod_channel_name": "usercommandmgmt-admin-approval",
                    "number_of_mod_reacts_needed": 2,
                }
                json.dump(default, f, indent=2)

        self.mod_config = Config(self.config_file)
        self.activeDb = Database(self.save_file)
        intents = discord.Intents.default()
        intents.reactions = True
        self.create_command_queue = {}
        self.commandobj = CommandObjMod(
            config=self.config, bot=self.bot, database=self.activeDb
        )

        if not os.path.isfile(self.queue_cache):
            with open(self.queue_cache, "wb") as f:
                pickle.dump(self.create_command_queue, f)
        elif os.path.getsize(self.queue_cache) > 0:
            with open(self.queue_cache, "rb") as f:
                self.create_command_queue = pickle.load(f)
        else:
            """
            no need to do anything
            """

    @commands.command()
    async def test(self, ctx, echo: str, echo2: str):
        await ctx.send(echo + " " + echo2)

    # cc commmands
    @commands.group(aliases=["cc"])
    @commands.guild_only()
    async def customcom(self, ctx: commands.Context):
        """Base command for Custom Commands management."""
        pass

    @customcom.group(name="create", aliases=["add", "new"], invoke_without_command=True)
    async def cc_create(self, ctx: commands.Context, command: str.lower, *, text: str):
        """Create custom commands.

        If a type is not specified, a simple CC will be created.
        CCs can be enhanced with arguments, see the guide
        [here](https://docs.discord.red/en/stable/cog_customcom.html).
        """

        # overrides the mod process and limit check if user is an admin
        if ctx.message.author.top_role.permissions.administrator:
            await ctx.send("Admin request detected. Bypassing checks")
            # custom command is created and the entry is added to the database
            try:
                await self.cc_create_simple_modified(
                    command,
                    text,
                    ctx.message.id,
                    ctx.message.channel.id,
                    ctx.message.channel.guild.id,
                    False,
                )
            except:
                await ctx.send("something went wrong; could not add command")
                return
        # normal per-role allowance check and moderation process if user isnt an admin
        else:
            # checks if user has any capacity left to make commands based on their allowance
            if not self.enforce_user_cmd_limit(
                ctx.message.author, ctx.message.guild.id
            ):
                await ctx.send(
                    "Sorry, you have already created the maximum number of commands allowed by your role"
                )
                return
            # inform user about status of their command
            if self.mod_config.is_mod_enabled():
                await self.submit_for_approval(ctx, command, text)
                await ctx.send("Command request submitted")
            else:
                try:
                    await self.cc_create_simple_modified(
                        command,
                        text,
                        ctx.message.id,
                        ctx.message.channel.id,
                        ctx.message.channel.guild.id,
                        False,
                    )
                except:
                    await ctx.send("something went wrong; could not add command")
                    return

    @customcom.command(name="delete", aliases=["del", "remove"])
    async def cc_delete(self, ctx, command: str.lower):
        """Delete a custom command.

        Example:
            - `[p]customcom delete yourcommand`

        **Arguments:**

        - `<command>` The custom command to delete.
        """
        # if user is admin, allows them to delete any command
        if ctx.message.author.top_role.permissions.administrator:
            try:
                await ctx.send("Admin Override.")
                await self.commandobj.delete(ctx=ctx, command=command)
            except NotFound:
                await ctx.send("That command doesn't exist.")
                return
            self.activeDb.delete_from_db(command)
            await ctx.send("Custom command successfully deleted.")
        # if user isnt an admin, only allows them to delete their own commands
        else:
            if not self.activeDb.belongs_to_user(command, ctx.message.author.id):
                await ctx.send("Hey, that's not yours.")
                return

            try:
                await self.commandobj.delete(ctx=ctx, command=command)
            except NotFound:
                await ctx.send("That command doesn't exist.")
                return
            self.activeDb.delete_from_db(command)
            await ctx.send("Custom command successfully deleted.")

    @customcom.command(name="edit")
    async def cc_edit(self, ctx, command: str.lower, *, text: str = None):
        """Edit a custom command.

        Example:
            - `[p]customcom edit yourcommand Text you want`

        **Arguments:**

        - `<command>` The custom command to edit.
        - `<text>` The new text to return when executing the command.
        """
        if ctx.message.author.top_role.permissions.administrator:
            await ctx.send("Admin Override.")

            try:
                await self.commandobj.edit(ctx=ctx, command=command, response=text)
                await ctx.send("Custom command successfully edited.")
            except NotFound:
                await ctx.send(
                    "That command doesn't exist. Use" + ctx.clean_prefix + " to add it."
                )
            except ArgParseError as e:
                await ctx.send(e.args[0])
            except CommandNotEdited:
                pass
        else:
            # blocks a user from editing a command that isnt theirs
            if not self.activeDb.belongs_to_user(command, ctx.message.author.id):
                await ctx.send("Hey, that's not yours.")
                return

            try:
                await self.commandobj.edit(ctx=ctx, command=command, response=text)
                await ctx.send("Custom command successfully edited.")
            except NotFound:
                await ctx.send(
                    (
                        "That command doesn't exist. Use"
                        + ctx.clean_prefix
                        + " to add it."
                    )
                )
            except ArgParseError as e:
                await ctx.send(e.args[0])
            except CommandNotEdited:
                pass

    async def submit_for_approval(self, ctx, command, text):
        """
        posts the proposed command in the specified channel, and waits for a moderator's reaction to either
        reject or accept the command.
        """
        # create message to submit for mod approval
        MESSAGE_TEMPLATE = """Sender: {author}
        Proposed Command: {command}
        {text}
        {jump_url}
        """

        message_to_submit = MESSAGE_TEMPLATE.format(
            author=ctx.author.name,
            command=command,
            text=text,
            jump_url=ctx.message.jump_url,
        )

        # finds the channel to send this message to: the moderator one; specified in configurable.py
        mod_channel = self.find_channel_by_name(
            self.mod_config.get_mod_channel_name(), ctx.message.guild.channels
        )
        # submit proposed command and relavant info to specified moderation channel
        msg = await mod_channel.send(message_to_submit)
        # adds reacts
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        self.create_command_queue[msg.id] = [
            command,
            text,
            ctx.message.id,
            ctx.message.channel.id,
        ]
        with open(self.queue_cache, "wb") as f:
            pickle.dump(self.create_command_queue, f)

    # reaction listener
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """
        listens for reacts on the mod channel
        """
        channel = self.bot.get_channel(payload.channel_id)

        if self.mod_config.get_mod_channel_name() == channel.name:
            if payload.emoji.name == "✅" or payload.emoji.name == "❌":
                message = await channel.fetch_message(payload.message_id)
                reaction = get(message.reactions, emoji=payload.emoji.name)
                if (
                    reaction
                    and reaction.count >= 1 + self.mod_config.get_reacts_needed()
                ):
                    req_data = self.create_command_queue.get(message.id)
                    # find the command data in queue, if none then do nothing
                    if req_data == None:
                        return
                    else:
                        original_channel = self.bot.get_channel(req_data[3])
                        original_request_message = await original_channel.fetch_message(
                            req_data[2]
                        )

                        if payload.emoji.name == "✅":
                            try:
                                await self.cc_create_simple_modified(
                                    req_data[0],
                                    req_data[1],
                                    req_data[2],
                                    original_request_message.channel.id,
                                    channel.guild.id,
                                    False,
                                )
                            except:
                                await original_request_message.author.send(
                                    "Your command proposal was accepted, but something went wrong with command creation, please try again"
                                )
                        elif payload.emoji.name == "❌":
                            await original_request_message.author.send(
                                "Sorry, your proposed command was deemed inappropriate by the moderators"
                            )

                        self.create_command_queue.pop(message.id)

    # utility commands for users
    @commands.command()
    async def command_count(self, ctx):
        """
        gets the number of commands created by the caller of this command
        """
        currently_used = self.activeDb.get_user_comm_quantity(
            ctx.message.author.id, ctx.message.guild.id
        )
        current_max = self.get_highest_user_comm_allowance(ctx.message.author)

        MESSAGE_TEMPLATE = """You have assigned {currrent_amt} out of {max_amt} commands available to you"""

        msg = MESSAGE_TEMPLATE.format(currrent_amt=currently_used, max_amt=current_max)

        await ctx.send(msg)

    # utility commands for moderators
    @checks.mod_or_permissions(administrator=True)
    @commands.command()
    async def togglemoderation(self, ctx):
        """
        sets command_moderation to false if true, and vice versa
        """
        new_state = True if not self.mod_config.is_mod_enabled() else False
        self.mod_config.set_command_moderation(new_state)
        await ctx.send("moderation set to " + str(self.mod_config.is_mod_enabled()))

    @checks.mod_or_permissions(administrator=True)
    @commands.command()
    async def setmodchannel(self, ctx, channel_name: str):
        """
        sets the name of the mod channel to to channel_name in the configuration
        """
        if self.find_channel_by_name(channel_name, ctx.message.guild.channels):
            self.mod_config.set_mod_channel_name(channel_name)
            await ctx.send(
                "mod channel set to #" + self.mod_config.get_mod_channel_name()
            )
        else:
            await ctx.send("Could not find a channel with that name")

    @checks.mod_or_permissions(administrator=True)
    @commands.command()
    async def setapprovalreq(self, ctx, new_req: int):
        """
        sets the number of needed reacts for approval/rejection of proposed functions in the configuration. Number must be >= 1, otherwise does nothing and alerts user
        """
        if new_req < 1:
            await ctx.send("You must provide a number >=1")
        else:
            self.mod_config.set_reacts_needed(new_req)
            await ctx.send(
                "Reaction requirement set to "
                + str(self.mod_config.get_reacts_needed())
            )

    @checks.mod_or_permissions(administrator=True)
    @commands.command()
    async def addallowancedrole(self, ctx, new_role: str, allowance: int):
        """
        adds a new allowance setting for a role in the dictionary with the given allowance, if it doesn't already exist. Allowance must be >= 1
        """
        if self.mod_config.get_role_list.get(new_role) == None:
            if allowance < 1:
                await ctx.send("you must provide a number >= 1")
            else:
                self.mod_config.add_role_allowance(new_role, allowance)
                await ctx.send(
                    "Allowance of " + str(allowance) + " has been set for " + new_role
                )
        else:
            await ctx.send("that role already has an allowance set")

    @checks.mod_or_permissions(administrator=True)
    @commands.command()
    async def removeallowancedrole(self, ctx, role_to_delete: str):
        """
        removes an allowance setting for a role in the dictionary, if it exists
        """
        if self.mod_config.get_role_list.get(role_to_delete) == None:
            await ctx.send("That role has no defined allowance")
        else:
            self.mod_config.del_role_allowance(role_to_delete)
            await ctx.send(
                "Allowance settings for " + role_to_delete + " role cleareds"
            )

    @checks.mod_or_permissions(administrator=True)
    @commands.command()
    async def changeroleallowance(self, ctx, role: str, new_allowance: int):
        """
        changes role allowance to the given number for the given role. Must be greater or equal to 1
        """
        if self.mod_config.get_role_list.get(role) == None:
            await ctx.send("Could not find the command you specified")
        else:
            self.mod_config.change_role_allowance(role, new_allowance)
            await ctx.send(
                "New Allowance of " + str(new_allowance) + " set for " + role
            )

    # helper functions
    def enforce_user_cmd_limit(self, member, server):
        """
        returns true if the current number commands owned by the user is less than the highest amount allowed by any of their roles.
        """
        return self.activeDb.get_user_comm_quantity(
            member.id, server_id=server
        ) < self.get_highest_user_comm_allowance(member)

    def get_highest_user_comm_allowance(self, member):
        """
        returns the highest number of custom commands permitted by the user's roles
        """
        # all of the given user's roles
        usr_roles = member.roles
        # the user's roles that confer different command allowances
        rel_usr_roles = [0]
        for cmd in usr_roles:
            allowance = self.mod_config.get_role_list().get(cmd.name, 0)
            if allowance != 0:
                rel_usr_roles.append(allowance)

        return max(rel_usr_roles)

    def find_channel_by_name(self, channel_name, channel_List):

        """
        finds the discord channel in the list with the given name, and returns it. Will return none if a channel can't be found
        """

        for i in channel_List:
            if i.name == channel_name:
                return i
        return None

    async def cc_create_simple_modified(
        self, command, text, message_id, channel_id, guild_id, made_by_admin
    ):
        """Add a simple custom command.
        Example:
            - `[p]customcom create simple yourcommand Text you want`
        **Arguments:**
        - `<command>` The command executed to return the text. Cast to lowercase.
        - `<text>` The text to return when executing the command. See guide for enhanced usage.
        """
        guild = self.bot.get_guild(guild_id)
        channel = self.bot.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        user = message.author

        if any(char.isspace() for char in command):
            # Haha, nice try
            await user.send("Custom command names cannot have spaces in them.")
            return
        if command in (*self.bot.all_commands, *commands.RESERVED_COMMAND_NAMES):
            await user.send("There already exists a bot command with the same name.")
            return
        try:
            await self.commandobj.create_modified(
                command, text, message, guild, user, made_by_admin
            )
        except AlreadyExists:
            await user.send(
                "This command already exists. Use `customcom edit` command to edit it."
            )
        except ArgParseError as e:
            await user.send(e.args[0])


class CommandObjMod(CommandObj):
    def __init__(self, config, bot, database):
        super().__init__(config=config, bot=bot)
        self.activeDb = database

    async def create_modified(
        self, command, response, message, guild, user, made_by_admin
    ):
        """Create a custom command"""
        # Check if this command is already registered as a customcommand
        if await self.db(guild).commands.get_raw(command, default=None):
            raise AlreadyExists()
        # test to raise
        CustomCommands.prepare_args(
            response if isinstance(response, str) else response[0]
        )
        author = user
        ccinfo = {
            "author": {"id": author.id, "name": str(author)},
            "command": command,
            "cooldowns": {},
            "created_at": self.get_now(),
            "editors": [],
            "response": response,
        }
        await self.db(guild).commands.set_raw(command, value=ccinfo)
        # marks command as created by non-admin; counted as normal
        self.activeDb.save_to_db(command, user.id, made_by_admin, guild.id)
        MESSAGE_TEMPLATE = (
            """command successfully created!: You can now use: >{command}"""
        )

        can_use_alert = MESSAGE_TEMPLATE.format(command=command)
        await author.send(can_use_alert)
