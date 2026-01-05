import asyncio
import os

# Load API key from environment variable
# Set your key: $env:YOUTUBE_API_KEY = "your-key-here"
if not os.environ.get("YOUTUBE_API_KEY"):
    print("ERROR: YOUTUBE_API_KEY environment variable not set")
    print("Set it with: $env:YOUTUBE_API_KEY = 'your-api-key'")
    exit(1)

from youtube_data import YouTubeDataFetcher

async def test():
    f = YouTubeDataFetcher(api_key=os.environ["YOUTUBE_API_KEY"])
    m = await f.get_video_metadata("snFSPA5V_d0")
    if m:
        print(f"Title: {m.title}")
        print(f"Channel: {m.channel}")
    else:
        print("No metadata returned")
    await f.close()

asyncio.run(test())
