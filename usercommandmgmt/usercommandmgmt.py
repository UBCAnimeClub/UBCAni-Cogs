from redbot.core import Config, checks, commands, data_manager
from .configurable import *
from .commanddatahandler import *
import inspect
import sys
from .commanddatahandler import Database
import os


# imports customcomm class
path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(inspect.getfile(commands)))),
    "cogs\customcom",
)
sys.path.insert(1, path)

from customcom import (
    CustomCommands,
    CommandObj,
    NotFound,
    ArgParseError,
    CommandNotEdited,
)


class Usercommandmgmt(CustomCommands):
    """My custom cog"""

    def __init__(self, bot):
        super().__init__(bot)
        saveFile = os.path.join(
            data_manager.cog_data_path(cog_instance=self), "user commands.json"
        )
        if not os.path.isfile(saveFile):
            with open(saveFile, "w+") as f:
                empty = {"db": []}
                json.dump(empty, f)

        self.activeDb = Database(saveFile)

    # def createDbInstance(self, path):
    #     if not os.path.isfile(path):
    #         with open(path, "w+") as f:
    #             empty = dict()
    #             json.dump(empty, f)

    #     activeDb = Database(path)

    @commands.command()
    async def testcomm(self, ctx):
        """This does stuff!"""

        pass

    @commands.group(aliases=["cc"])
    @commands.guild_only()
    async def customcom(self, ctx: commands.Context):
        """Base command for Custom Commands management."""
        pass

    @customcom.group(name="create", aliases=["add"], invoke_without_command=True)
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
                await ctx.invoke(self.cc_create_simple, command=command, text=text)
                # marks command as created by admin in database, exempted from count
                await self.activeDb.SaveToDb(command, ctx.message.author.id, True)
            except:
                await ctx.send("something went wrong; could not add command")
                return
        # normal per-role allowance check and moderation process if user isnt an admin
        else:
            # checks if user has any capacity left to make commands based on their allowance
            if self.EnforceUserCmdLimit(ctx.message.author) == False:
                await ctx.send(
                    "Sorry, you have already created the maximum number of commands allowed by your role"
                )
                return
            # regardless of the case, inform user about status of their command
            await ctx.send("Command request submitted")

            # if check is passed, the command is submitted to a specified moderation channel for evaluation
            if self.ModEvaluate(text) == False:
                await ctx.send(
                    "Sorry, your requested command was deemed inappopriate by moderator"
                )
                return
            try:
                await ctx.invoke(self.cc_create_simple, command=command, text=text)
                # marks command as created by non-admin; counted as normal
                await self.activeDb.SaveToDb(command, ctx.message.author.id, False)
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
                await self.activeDb.DeleteFromDb(command)
                await ctx.send("Custom command successfully deleted.")
            except NotFound:
                await ctx.send("That command doesn't exist.")
        # if user isnt an admin, only allows them to delete their own commands
        else:
            if self.activeDb.BelongsToUser(command, ctx.message.author.id) == False:
                await ctx.send("Hey, that's not yours.")
                return

            try:
                await self.commandobj.delete(ctx=ctx, command=command)
                await self.activeDb.DeleteFromDb(command)
                await ctx.send("Custom command successfully deleted.")
            except NotFound:
                await ctx.send("That command doesn't exist.")

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
        else:
            # blocks a user from editing a command that isnt theirs
            if self.activeDb.BelongsToUser(command, ctx.message.author.id) == False:
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

    def GetHighestUserCommAllowance(self, member):
        """
        returns the highest number of custom commands permitted by the user's roles
        """
        # all of the given user's roles
        usr_roles = member.roles
        # the user's roles that confer different command allowances
        rel_usr_roles = [0]

        for cmd in usr_roles:
            allowance = role_cmd_limits.get(cmd.name, 0)
            if allowance != 0:
                rel_usr_roles.append(allowance)

        return max(rel_usr_roles)

    def ModEvaluate(self, proposed_msg):
        """
        posts the proposed command in the specified channel, and waits for a moderator's reaction to either
        reject or accept the command. Will  return true if command_moderation is set to False or command
        passes moderator evalutaion. False if it is rejected by a moderator.
        Note: proposed_msg is the proposed command
        """
        if command_moderation == False:
            return True
        else:
            # submits command for evaluation and awaits response; TODO
            pass

    def EnforceUserCmdLimit(self, member):
        """
        returns true if the current number commands owned by the user is less than the highest amount allowed by any of their roles.
        """
        return self.activeDb.GetUserCommQuantity(
            member.id
        ) < Usercommandmgmt.GetHighestUserCommAllowance(self, member=member)