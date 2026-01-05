"""Quick API test"""
import asyncio
from analyzer import SafetyAnalyzer
from safety_db import SafetyDatabase

async def main():
    db = SafetyDatabase()
    analyzer = SafetyAnalyzer(db)
    
    # Test with Rick Astley - Never Gonna Give You Up (music video, should be safe)
    print("Testing with a real YouTube video...")
    try:
        result = await analyzer.analyze("dQw4w9WgXcQ")
        print(f"Video ID: {result['video_id']}")
        print(f"Safety Score: {result['safety_score']}")
        print(f"Transcript Available: {result['transcript_available']}")
        print(f"Warnings: {len(result['warnings'])}")
        print(f"Summary: {result['summary']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
