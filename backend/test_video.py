"""Test a specific video"""
import asyncio
from analyzer import SafetyAnalyzer
from safety_db import SafetyDatabase

async def test():
    db = SafetyDatabase()
    analyzer = SafetyAnalyzer(db)
    
    # The dryer duct grill video
    video_id = "hpLbGKkuG-w"
    
    print(f"Testing video: {video_id}")
    print("-" * 40)
    
    # Get raw transcript first
    transcript, available = await analyzer._get_transcript(video_id)
    print(f"Transcript available: {available}")
    if transcript:
        print(f"Transcript preview: {transcript[:500]}...")
    else:
        print("No transcript found")
    
    print("-" * 40)
    
    result = await analyzer.analyze(video_id)
    print(f"Safety Score: {result['safety_score']}")
    print(f"Warnings: {len(result['warnings'])}")
    for w in result['warnings']:
        print(f"  - [{w['severity']}] {w['message']}")
    print(f"Summary: {result['summary']}")

asyncio.run(test())
