import asyncio
import datetime
import os
from dotenv import load_dotenv
from draftclient import DraftClient

if __name__ == '__main__':
    load_dotenv()
    token = os.getenv('DISCORD_BOT_TOKEN')

    now = datetime.datetime.now()
    if not os.path.exists("logs"):
        os.makedirs("logs")
    log_file_name = os.path.join("logs",
                                 f"{now.year:04d}-{now.month:02d}-{now.day:02d}_"
                                 f"{now.hour:02d}_{now.minute:02d}_{now.second:02d}")

    draft_client = DraftClient(log_file_name)
    draft_client.run(os.getenv('DISCORD_BOT_TOKEN'))
