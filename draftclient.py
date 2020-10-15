import asyncio
import collections
import discord
import random
from discord.ext import commands


class DraftClient(discord.Client):

    PREFIX = "$$"

    def __init__(self, log_file_name=None):
        super().__init__()
        self.guild = None
        self.log_file_name = log_file_name

        self.currently_drafting = False
        self.captains = set([])
        self.players = None
        self.reset_state()
        self.settings = {
            "initial_currency": 1000,
            "n_picks": 4,
            "n_captains": 2
        }

    def reset_state(self):
        self.captains = set([])
        self.players = set([])

    def get_settings_string(self):
        lines = ["{"]
        for key, value in self.settings.items():
            lines.append(f"\t{key}: {value}")
        lines.append("}")
        return "\n".join(lines)

    def get_specifics_string(self):
        lines = [f"Captains ({len(self.captains)}): {', '.join([u.display_name for u in self.captains])}",
                 f"Players ({len(self.players)}): {', '.join(self.players)}"]
        return "\n".join(lines)

    def change_setting(self, setting, value_str):
        try:
            if setting == "initial_currency":
                value = int(value_str)
                if value > 0:
                    self.settings[setting] = value
                    return True
                else:
                    return False
            elif setting == "n_picks":
                value = int(value_str)
                if value > 0:
                    self.settings[setting] = value
                    return True
                else:
                    return False
            elif setting == "n_captains":
                value = int(value_str)
                if value > 0:
                    self.settings[setting] = value
                    return True
                else:
                    return False
        except ValueError:
            return False

    async def on_ready(self):
        if len(self.guilds) == 0:
            self.terminate("Connected, but there are no client guilds.")
        elif len(self.guilds) >= 2:
            self.terminate("Connected, but there is more than one client guild.")
        else:
            for g in self.guilds:
                self.log(f"{self.user} has connected to guild {g.name} (id = {g.id}).")

    def log(self, s):
        if self.log_file_name is not None:
            with open(self.log_file_name, "a+") as f:
                f.write(s + "\n")

    def terminate(self, reason):
        self.log(f"ERROR CAUSING TERMINATION: {reason}")
        raise ValueError

    @staticmethod
    async def react_thumbs_up(message):
        await message.add_reaction("\U0001F44D")

    @staticmethod
    async def react_thumbs_down(message):
        await message.add_reaction("\U0001F44E")

    @staticmethod
    async def react_confused_face(message):
        await message.add_reaction("\U0001F615")

    @staticmethod
    def get_help_string():
        lines = [
            'All arguments are whitespace-separated.',
            f'Example: {DraftClient.PREFIX} add_player player1 player2',
            '"help": Shows this menu',
            '"awaken", "clear", "reset": Resets the specifics (captains/players) of the draft',
            '"settings", "view_settings": Views settings',
            '"change_setting": Change a particular setting. Two arguments: setting name and value.',
            '"add_player", "add_players": Adds a nonzero number of players specified by the remaining arguments',
            '"claim_captain": Register as a captain for the draft.',
            '"commence", "start", "begin": Start the drafting phase (in DMs); captains and players must be set.'
        ]
        return "\n".join(lines)

    @staticmethod
    def get_auction_rules_string():
        lines = [
            "Players will be queued up for consideration in a random order.",
            "When a player is up for bidding, I will ask you for your bids privately.",
            "Obviously, you may not bid higher than your current currency.",
            "A captain who makes a larger nonnegative bid will secure the player at that price.",
            "Ties in winning bids ($0 or above) are broken randomly."
            "If neither captain bids $0 or above, the player is placed at the back of the queue."
        ]
        return "\n".join(lines)

    async def on_message(self, message):
        content = message.content
        if not message.content.startswith(self.PREFIX):
            return

        words = content[len(self.PREFIX):].split(" ")
        command = words[0].lower()
        if command == "help":
            await self.react_thumbs_up(message)
            await message.channel.send(self.get_help_string())
            return

        if self.currently_drafting:
            await message.channel.send("I'm not listening to commands; drafting is currently in progress.")
            return

        if command in {"awaken", "clear", "reset"}:
            self.reset_state()
            await self.react_thumbs_up(message)
            await message.channel.send("Draft specifics have been reset! Use \"help\" for a list of commands")
            return
        elif command in {"settings", "view_settings"}:
            await self.react_thumbs_up(message)
            await message.channel.send("CURRENT SETTINGS:\n" + self.get_settings_string())
            return
        elif command == "change_setting":
            if self.change_setting(words[1].lower(), words[2].lower()):
                self.reset_state()
                await self.react_thumbs_up(message)
                await message.channel.send("Since settings have changed, the draft specifics have been reset.")
            else:
                await self.react_thumbs_down(message)
                await message.channel.send("Error: These settings changes were invalid.")
            return
        elif command in {"add_player", "add_players"}:
            named_players = words[1:]
            if len(named_players) == 0:
                await self.react_thumbs_down(message)
                await message.channel.send("Error: No players to add.")
                return
            for player in named_players:
                if player in self.players:
                    await self.react_thumbs_down(message)
                    await message.channel.send("Error: This player has already been added.")
                else:
                    await self.react_thumbs_up(message)
                    self.players.add(player)
            await message.channel.send(self.get_specifics_string())
            return
        elif command == "claim_captain":
            user = message.author
            if user in self.captains:
                await self.react_thumbs_down(message)
                await message.channel.send("Error: You are already a captain.")
            elif len(self.captains) >= self.settings["n_captains"]:
                await self.react_thumbs_down(message)
                await message.channel.send("Error: There are already enough captains.")
            else:
                await self.react_thumbs_up(message)
                self.captains.add(user)
            await message.channel.send(self.get_specifics_string())
            return
        elif command in {"commence", "start", "begin"}:
            if message.author not in self.captains:
                await self.react_thumbs_down(message)
                await message.channel.send("Error: You aren't a captain.")
            elif len(self.captains) < self.settings["n_captains"]:
                await self.react_thumbs_down(message)
                await message.channel.send("Error: Insufficient captains.")
            elif len(self.players) < self.settings["n_captains"] * self.settings["n_picks"]:
                await self.react_thumbs_down(message)
                min_players = self.settings["n_captains"] * self.settings["n_picks"]
                await message.channel.send(f"Error: Insufficient players to draft ({min_players} required).")
            else:
                await message.channel.send("Drafting has now started:\n" + self.get_specifics_string())
                teams = await self.execute_draft()
                teams_lines = []
                for captain, members in teams.items():
                    teams_lines.append(', '.join([f"{captain.display_name} (captain)"] + members))
                await message.channel.send("DRAFTING COMPLETE. TEAMS:\n" + '\n'.join(teams_lines))
                return
        else:
            await self.react_confused_face(message)
            return

    @staticmethod
    async def direct_message(user, s):
        dm_channel = await user.create_dm() if user.dm_channel is None else user.dm_channel
        return await dm_channel.send(s)

    async def collect_bid(self, captain, currency):
        dm_channel = await captain.create_dm() if captain.dm_channel is None else captain.dm_channel

        bid = None

        while True:
            bid_message = await self.wait_for('message', check=lambda m: m.author == captain and m.channel == dm_channel)
            try:
                bid = int(bid_message)
                if bid > currency:
                    await self.direct_message(captain, "You don't have that much currency. Try again.")
                else:
                    await self.react_thumbs_up(bid_message)
                    bid_ok_str = f"Your bid of {bid} is acknowledged. Waiting for other captains..."
                    await self.direct_message(captain, bid_ok_str)
                    break
            except ValueError:
                continue

        return captain, bid

    async def execute_draft(self):
        self.currently_drafting = True

        initial_currency = self.settings["initial_currency"]
        n_picks = self.settings["n_picks"]

        # By captain
        teams = {}
        currencies = {}

        for user in self.captains:
            teams[user] = []
            currencies[user] = initial_currency
            await self.direct_message(user,
                                      "You are a captain! Here are the players and captains: \n" +
                                      self.get_specifics_string())
            await self.direct_message(user, self.get_auction_rules_string())

        player_queue = collections.deque(random.sample(self.players, len(self.players)))
        while player_queue:
            unfinished_captains = [c for c in self.captains if len(teams[c]) < n_picks]
            if len(unfinished_captains) == 0:
                break

            state_lines = ["CURRENT STATE:"]
            for user in self.captains:
                state_lines.append(f"{user.display_name} (${currencies[user]}): {', '.join(teams[user])}")
            state_lines.append(f"Bidding Queue: {' -> '.join([p for p in player_queue])}")
            state_str = "\n".join(state_lines)

            for user in self.captains:
                await self.direct_message(user, state_str)

            player = player_queue.popleft()

            for user in self.captains:
                if user not in unfinished_captains:
                    await self.direct_message(user, f"You can't bid because your team is full.")
                    continue

            collect_bid_tasks = [self.collect_bid(user, currencies[user]) for user in unfinished_captains]
            bid_pairs = await asyncio.gather(collect_bid_tasks)

            highest_bid = -float('inf')
            highest_bidding_captains = []
            for captain, bid in bid_pairs:
                if bid > highest_bid:
                    highest_bidding_captains = [captain]
                    highest_bid = bid
                elif bid == highest_bid:
                    highest_bidding_captains.append(captain)

            if highest_bid >= 0:
                winning_captain = random.sample(highest_bidding_captains, 1)[0]
                teams[winning_captain].append(player)
                currencies[winning_captain] -= highest_bid
                for user in self.captains:
                    await self.direct_message(user, f'"{player}" is secured by {winning_captain.display_name} '
                                                    f'for ${highest_bid}')
            else:
                player_queue.append(player)
                for user in self.captains:
                    await self.direct_message(user, f'"{player}" was not drafted and was re-enqueued.')

        for user in self.captains:
            await self.direct_message(user, f"Drafting has finished. Your team: {', '.join(teams[user])}")
        self.currently_drafting = False
        return teams
