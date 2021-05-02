# contains all the configurable fields for this cog
import json
import os


class Config:
    """
    stores config info
    """

    def __init__(self, directory):
        self.dir = directory
        self.loaded_cmd_data = {}
        try:
            with open(self.dir, "r") as f:
                self.loaded_cmd_data = json.load(f)
        except IOError:
            # specifies the number of commands granted to specific roles
            self.loaded_cmd_data["role_cmd_limits"] = {
                "Tier 1 Simp": 1,
                "Tier 2 Simp": 3,
                "Tier 3 Simp": 5,
            }

            # admin command management
            # set to false to disable the pre-command creation moderator approval system
            self.loaded_cmd_data["command_moderation"] = True

            # the name of the channel used for moderation
            self.loaded_cmd_data["mod_channel_name"] = "usercommandmgmt-admin-approval"

            # the number of approvals and rejects needed to accept/reject a command request
            self.loaded_cmd_data["number_of_mod_reacts_needed"] = 2

    def save_state_to_file(self):
        """
        saves the current config details to the file
        """
        with open(self.dir, "w") as outfile:
            json.dump(self.loaded_cmd_data, outfile, indent=2)

    def set_command_moderation(self, new_state):
        """
        sets command_moderation to the new and updates the config file
        """
        self.loaded_cmd_data.update({"command_moderation": new_state})
        self.save_state_to_file()

    def set_mod_channel_name(self, new_name):
        """
        sets the mod channel name to the new name and updates the config file
        """
        self.loaded_cmd_data.update({"mod_channel_name": new_name})
        self.save_state_to_file()

    def set_reacts_needed(self, new_amt):
        """
        sets the number of needed reacts for approval/rejection to new_amt and updates the config file
        """
        self.loaded_cmd_data.update({"number_of_mod_reacts_needed": new_amt})
        self.save_state_to_file()

    def add_role_allowance(self, role_name, allowance):
        """
        adds a new role and its associated allowance to the configuration
        """
        self.loaded_cmd_data[role_name] = allowance
        self.save_state_to_file()

    def del_role_allowance(self, role_name):
        """
        removes a role and its allowance from the configuration
        """
        self.loaded_cmd_data.pop(role_name)
        self.save_state_to_file()

    def change_role_allowance(self, role_name, new_allowance):
        """
        gives the given role_name a new allowance in the configuration
        """
        self.loaded_cmd_data.get("role_cmd_limits").update({role_name: new_allowance})
        self.save_state_to_file()

    def get_role_list(self):
        """
        returns a list of roles and their allowances
        """
        return self.loaded_cmd_data.get("role_cmd_limits")[0]

    def is_mod_enabled(self):
        """
        returns whether command moderation is on or off
        """
        return self.loaded_cmd_data.get("command_moderation")

    def get_mod_channel_name(self):
        """
        returns the name of the set command moderation channel
        """
        return self.loaded_cmd_data.get("mod_channel_name")

    def get_reacts_needed(self):
        """
        returns the amount of reacts needed to approve/reject a command request
        """
        return self.loaded_cmd_data.get("number_of_mod_reacts_needed")
