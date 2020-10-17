
class DraftSettings(object):

    def __init__(self):
        self.initial_currency = 1000
        self.n_picks = 4
        self.n_captains = 2
        self.n_rebids_on_tie = 2

    def change_setting(self, setting_str, value_str):
        """
        Attempt to change a particular setting.
        :param setting_str: string representing for the setting to be changed.
        :param value_str: string representing the new value
        :return: bool, string: bool for whether the change was applied, string reason for why not (if it didn't)
        """
        if setting_str == "initial_currency":
            try:
                value = int(value_str)
                if value <= 0:
                    return False, f"*{setting_str}* must be a positive integer"
                elif value > 9223372036854775807:
                    return False, f"*{setting_str}* is capped at 9223372036854775807"
                self.initial_currency = value
            except ValueError:
                return False, f"*{setting_str}* must be a positive integer"
        elif setting_str == "n_picks":
            try:
                value = int(value_str)
                if value <= 0:
                    return False, f"*{setting_str}* must be a positive integer"
                elif value > 80:
                    return False, f"*{setting_str}* is capped at 80"
                self.n_picks = value
            except ValueError:
                return False, f"*{setting_str}* must be a positive integer"
        elif setting_str == "n_captains":
            try:
                value = int(value_str)
                if value <= 0:
                    return False, f"*{setting_str}* must be a positive integer"
                elif value > 80:
                    return False, f"*{setting_str}* is capped at 80"
                self.n_captains = value
            except ValueError:
                return False, f"*{setting_str}* must be a positive integer"
        elif setting_str == "n_rebids_on_tie":
            try:
                value = int(value_str)
                if value < 0:
                    return False, f"*{setting_str}* must be a nonnegative integer"
                elif value > 9223372036854775807:
                    return False, f"*{setting_str}* is capped at 9223372036854775807"
                self.n_rebids_on_tie = value
            except ValueError:
                return False, f"*{setting_str}* must be a nonnegative integer"
        else:
            return False, f"not a valid setting"

        return True, None

    def __str__(self):
        lines = ["**SETTINGS**", "{"]
        for setting, value in vars(self).items():
            lines.append(f"\t{setting}: {value}")
        lines.append("}")
        return '\n'.join(lines)
