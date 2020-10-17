import asyncio
import collections
import discord
import random
from draftsettings import DraftSettings


class DraftClient(discord.Client):

    PREFIX = "$$"

    def __init__(self, log_file_name=None):
        super().__init__()
        self.guild = None
        self.log_file_name = log_file_name

        self.draft_task = None

        self.captains = set([])
        self.players = None
        self.reset_state()
        self.settings = DraftSettings()

    def reset_state(self):
        self.captains = set([])
        self.players = set([])

    @staticmethod
    async def direct_message(user, s):
        dm_channel = await user.create_dm() if user.dm_channel is None else user.dm_channel
        return await dm_channel.send(s)

    async def on_ready(self):
        if len(self.guilds) == 0:
            self.terminate("Connected, but there are no client guilds.")
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

    async def on_message(self, message):
        try:
            content = message.content
            if not message.content.startswith(self.PREFIX):
                return

            words = content[len(self.PREFIX):].split()
            command = words[0].lower()
            self.log(f"message received, parsed words: [{', '.join(words)}]")
            if command == "help":
                await self.react_thumbs_up(message)
                await message.channel.send(self.get_help_string())
                return
            elif command == "stop_draft":
                if self.draft_task:
                    await self.react_thumbs_up(message)
                    self.draft_task.cancel()
                else:
                    await message.channel.send("There is no draft in progress.")
                return

            if self.draft_task:
                await message.channel.send('I\'m not listening to commands other than "help" and "stop_draft"; '
                                           'drafting is currently in progress.')
                return
            if command in {"awaken", "reset", "reset_state"}:
                self.reset_state()
                await self.react_thumbs_up(message)
                await message.channel.send("Draft state has been cleared.")
                return
            elif command in {"state", "view_state"}:
                await self.react_thumbs_up(message)
                await message.channel.send(self.get_state_string())
                return
            elif command in {"settings", "view_settings"}:
                await self.react_thumbs_up(message)
                await message.channel.send(self.get_settings_string())
                return
            elif command == "change_setting":
                valid, reason = self.settings.change_setting(words[1].lower(), words[2].lower())
                if valid:
                    self.reset_state()
                    await self.react_thumbs_up(message)
                    await message.channel.send("Since settings have changed, the draft state has been reset.")
                else:
                    await self.react_thumbs_down(message)
                    await message.channel.send(f"Error: These settings changes were invalid ({reason}).")
                return
            elif command in {"add_player", "add_players"}:
                named_players = words[1:]
                if len(named_players) == 0:
                    await self.react_thumbs_down(message)
                    await message.channel.send("Error: No players to add.")
                    return
                for player in named_players:
                    valid, reason = self.can_add_player(player)
                    if valid:
                        await self.react_thumbs_up(message)
                        self.players.add(player)
                    else:
                        await self.react_thumbs_down(message)
                        await message.channel.send(f"Couldn't add a player ({reason}).")
                await message.channel.send(self.get_state_string())
                return
            elif command == "claim_captain":
                user = message.author
                if user in self.captains:
                    await self.react_thumbs_down(message)
                    await message.channel.send("Error: You are already a captain.")
                elif len(self.captains) >= self.settings.n_captains:
                    await self.react_thumbs_down(message)
                    await message.channel.send("Error: There are already enough captains.")
                else:
                    await self.react_thumbs_up(message)
                    self.captains.add(user)
                await message.channel.send(self.get_state_string())
                return
            elif command in {"commence", "start", "begin"}:
                if message.author not in self.captains:
                    await self.react_thumbs_down(message)
                    await message.channel.send("Error: You aren't a captain.")
                elif len(self.captains) < self.settings.n_captains:
                    await self.react_thumbs_down(message)
                    await message.channel.send("Error: Insufficient captains.")
                elif len(self.players) < self.settings.n_captains * self.settings.n_picks:
                    await self.react_thumbs_down(message)
                    min_players = self.settings.n_captains * self.settings.n_picks
                    await message.channel.send(f"Error: Insufficient players to draft ({min_players} required).")
                else:
                    await message.channel.send("Drafting has now started:\n" + self.get_state_string())
                    self.draft_task = asyncio.create_task(self.execute_draft())
                    try:
                        teams = await self.draft_task
                        teams_lines = []
                        for captain, members in teams.items():
                            teams_lines.append(', '.join([f"{captain.display_name} (captain)"] + members))
                        await message.channel.send("**DRAFTING COMPLETE. TEAMS:**\n" + '\n'.join(teams_lines))
                    except asyncio.CancelledError:
                        await message.channel.send("Drafting has been cancelled.")
                    finally:
                        self.draft_task = None
                    return
            else:
                await self.react_confused_face(message)
                if random.random() < 0.03:
                    await message.channel.send("what")
                return
        except UnicodeEncodeError:
            self.log("UnicodeEncodeError")

    async def collect_bid(self, captain, currency):
        dm_channel = await captain.create_dm() if captain.dm_channel is None else captain.dm_channel

        bid = None

        while True:
            bid_message = await self.wait_for('message',
                                              check=lambda m: m.author == captain and m.channel == dm_channel)

            try:
                bid = int(bid_message.content)
                if bid > currency:
                    await self.direct_message(captain, "You don't have that much currency. Try again.")
                    continue
                elif bid < -1:
                    await self.direct_message(captain, "-1 is a rejection bid. You can't bid lower than that.")
                else:
                    await self.react_thumbs_up(bid_message)
                    bid_ok_str = f"Your bid of {bid} is acknowledged. Waiting for other captains..."
                    await self.direct_message(captain, bid_ok_str)
                    break
            except ValueError:
                continue

        return captain, bid

    async def execute_draft(self):
        initial_currency = self.settings.initial_currency
        n_picks = self.settings.n_picks

        # By captain
        teams = {}
        currencies = {}

        # By player
        n_rebids_remaining = {player: self.settings.n_rebids_on_tie for player in self.players}

        for user in self.captains:
            teams[user] = []
            currencies[user] = initial_currency
            await self.direct_message(user,
                                      "You are a captain! Here are the players and captains: \n" +
                                      self.get_state_string())
            await self.direct_message(user, self.get_auction_rules_string())

        player_queue = collections.deque(random.sample(self.players, len(self.players)))
        while player_queue:
            unfinished_captains = [c for c in self.captains if len(teams[c]) < n_picks]
            if len(unfinished_captains) == 0:
                break

            progress_lines = ["**DRAFT PROGRESS**"]
            for user in self.captains:
                progress_lines.append(f"{user.display_name} (${currencies[user]}): {', '.join(teams[user])}")
            progress_lines.append(f"Bidding Queue: {' -> '.join([p for p in player_queue])}")
            progress_str = "\n".join(progress_lines)

            for user in self.captains:
                await self.direct_message(user, progress_str)

            player = player_queue.popleft()

            for user in self.captains:
                bid_message = f'Bidding on **{player}**. # rebids available: {n_rebids_remaining[player]}\n' \
                              f'Input an integer bid up to your current currency (or -1 to bid rejection)'
                await self.direct_message(user, bid_message)
                if user not in unfinished_captains:
                    await self.direct_message(user, f"You can't bid because your team is full.")
                    continue

            highest_bid = -2

            collect_bid_tasks = [self.collect_bid(user, currencies[user]) for user in unfinished_captains]
            bid_pairs = await asyncio.gather(*collect_bid_tasks)

            highest_bidding_captains = []
            for captain, bid in bid_pairs:
                if bid > highest_bid:
                    highest_bidding_captains = [captain]
                    highest_bid = bid
                elif bid == highest_bid:
                    highest_bidding_captains.append(captain)

            if len(highest_bidding_captains) > 1:
                if n_rebids_remaining[player] > 0:
                    if highest_bid >= 0:
                        for user in self.captains:
                            await self.direct_message(user, f"There was a tie of 0 or more, "
                                                            f"so we will rebid immediately.")
                        player_queue.appendleft(player)

                    else:
                        for user in self.captains:
                            await self.direct_message(user, f"There was a rejection bid tie, so the player will be"
                                                            f"moved to the back of the queue.")
                        player_queue.append(player)
                    n_rebids_remaining[player] -= 1
                    continue
                else:
                    for user in self.captains:
                        await self.direct_message(user, "There was a tie with no rebids remaining, "
                                                        "so I will randomly choose the winner.")
                    winning_captain = random.sample(highest_bidding_captains, 1)[0]
                    highest_bid = max(highest_bid, 0)
            else:
                winning_captain = highest_bidding_captains[0]

            # By here there must only be a singular winning captain.

            if highest_bid >= 0:
                teams[winning_captain].append(player)
                currencies[winning_captain] -= highest_bid
                for user in self.captains:
                    await self.direct_message(user, f'**{player}** is secured by **{winning_captain.display_name}** '
                                                    f'for ${highest_bid}')
            else:
                # Singular remaining captain rejecting a player.
                for user in self.captains:
                    await self.direct_message(user, f"Due to a rejection, the player will be moved to the back of "
                                                    f"the queue.")
                player_queue.append(player)

        for user in self.captains:
            team = teams[user]
            random.shuffle(team)
            await self.direct_message(user, f"Drafting has finished. Your team: {', '.join(team)}")
        return teams

    def can_add_player(self, name):
        """
        Checks if the player name is valid and if it can be added.
        :param name:
        :return: bool, string: A boolean indicating whether the name is valid. If invalid, a string explaining why.
        """
        if len(name) > 30:
            return False, "the player's name exceeds 20 characters"
        elif not name.isalnum():
            return False, "the player's name contains non-alphanumeric characters"
        elif name in self.players:
            return False, "the player's name is already added"
        elif len(self.players) >= 80:
            return False, f"there are already too many players ({len(self.players)})"
        else:
            return True, None

    @staticmethod
    async def react_thumbs_up(message):
        await message.add_reaction("\U0001F44D")

    @staticmethod
    async def react_thumbs_down(message):
        await message.add_reaction("\U0001F44E")

    @staticmethod
    async def react_confused_face(message):
        await message.add_reaction("\U0001F615")

    def get_settings_string(self):
        return str(self.settings)

    def get_state_string(self):
        lines = ['**STATE**',
                 f"Captains ({len(self.captains)}): {', '.join([u.display_name for u in self.captains])}",
                 f"Players ({len(self.players)}): {', '.join(self.players)}"]
        return '\n'.join(lines)

    @staticmethod
    def get_help_string():
        lines = [
            '**HELP MENU**',
            'All arguments are whitespace-separated.',
            f'Example: {DraftClient.PREFIX} add_player player1 player2',
            '"help": Shows this menu',
            '"state", "view_state": Views the state (captains & players)',
            '"awaken", "reset", "reset_state": Resets the state (captains & players)',
            '"settings", "view_settings": Views settings',
            '"change_setting": Change a particular setting. Two arguments: setting name and value.',
            '"add_player", "add_players": Adds a nonzero number of players specified by the remaining arguments',
            '"claim_captain": Register as a captain for the draft.',
            '"commence", "start", "begin": Start the drafting phase (in DMs); captains and players must be set.',
            '"stop_draft": Stops an in-progress draft'
        ]
        return "\n".join(lines)

    def get_auction_rules_string(self):
        if self.settings.n_rebids_on_tie == 0:
            rebid_line = "There are no rebids, so ties are immediately broken randomly."
        else:
            rebid_line = f"In case of ties among winning bids, you can rebid on each player " \
                         f"{self.settings.n_rebids_on_tie} times. Rejection bid ties place the player at the back of " \
                         f"the queue; otherwise, rebidding happens immediately."
        bidding_lines = [
            "**Bidding:**",
            "When a player is up for bidding, I will ask you for your bids privately.",
            "Your bid must be between -1 and your current currency, inclusive. -1 represents rejection.",
            rebid_line
        ]

        lines = [
            "**RULES**",
            "**Format:** This is a first-price blind auction.",
            "**Ordering:** Players will be queued up for consideration in a random order."
        ]
        lines += bidding_lines
        return "\n".join(lines)
