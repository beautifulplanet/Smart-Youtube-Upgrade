"""
Test script for YouTube Safety Inspector
Run this to test the analyzer without the Chrome extension
"""

import asyncio
import sys
sys.path.insert(0, '.')

from analyzer import SafetyAnalyzer
from safety_db import SafetyDatabase

# Test transcripts simulating dangerous content
TEST_CASES = [
    {
        "name": "Dangerous Fitness Advice",
        "transcript": """
        Welcome to my workout channel! Today I'm going to show you the best way to do leg press.
        The key is to lock your knees at the top of every rep for maximum muscle activation.
        Also, bouncing at the bottom helps you lift more weight.
        No warm up needed if you're already feeling pumped!
        """,
        "expected_issues": ["lock knees", "bouncing", "no warmup"]
    },
    {
        "name": "Dangerous DIY BBQ",
        "transcript": """
        Hey guys, today we're building a cheap BBQ grill. I got this galvanized pipe for the 
        main structure - it's perfect because it won't rust! We're going to use this 
        galvanized steel grill grate too. Some people say you shouldn't use galvanized for 
        cooking but that's just being overly cautious.
        """,
        "expected_issues": ["galvanized cooking"]
    },
    {
        "name": "Dangerous Cooking Advice",
        "transcript": """
        Quick tip for putting out grease fires - just add water to the hot oil and it 
        will cool right down. Also, pink chicken is fine as long as it looks cooked on 
        the outside. And don't worry about leaving rice out overnight, it's perfectly safe.
        """,
        "expected_issues": ["water in oil", "pink chicken", "rice out"]
    },
    {
        "name": "Safe Fitness Video",
        "transcript": """
        Welcome back! Today we're focusing on proper squat form. Remember to warm up
        for at least 5-10 minutes before heavy lifting. Keep your knees tracking over
        your toes naturally, and maintain a slight bend - never lock your knees. 
        Use controlled movements, no bouncing at the bottom.
        """,
        "expected_issues": []  # Should be mostly safe
    },
    {
        "name": "Dangerous Electrical Advice",
        "transcript": """
        Easy fix for a blown fuse - just put a penny in the fuse box! Works every time.
        Also, you can daisy chain power strips if you need more outlets. Extension cords
        to extension cords is fine for permanent use.
        """,
        "expected_issues": ["penny fuse", "daisy chain"]
    },
    {
        "name": "Mixed Content",
        "transcript": """
        Let's talk about car maintenance. First, always work on a cool engine. For 
        cleaning parts, gasoline works great as a degreaser. Also, if you're doing 
        electrical work, you should always turn off power at the breaker first for safety.
        """,
        "expected_issues": ["gasoline cleaner"]  # One issue mixed with good advice
    }
]


async def test_analyzer():
    """Test the safety analyzer with various transcripts"""
    
    print("=" * 60)
    print("🛡️  YouTube Safety Inspector - Test Suite")
    print("=" * 60)
    
    # Initialize
    safety_db = SafetyDatabase()
    analyzer = SafetyAnalyzer(safety_db)
    
    print(f"\n📊 Loaded {len(safety_db.signatures)} danger signatures")
    print(f"📁 Categories: {', '.join(safety_db.categories.keys())}")
    print("\n" + "-" * 60)
    
    for i, test in enumerate(TEST_CASES, 1):
        print(f"\n🧪 Test {i}: {test['name']}")
        print("-" * 40)
        
        # Override the transcript fetching by directly testing signature matching
        matches = analyzer._match_signatures(test['transcript'].lower())
        warnings = analyzer._generate_warnings(matches)
        score = analyzer._calculate_safety_score(matches, {})
        
        # Display results
        print(f"   Safety Score: {score}/100", end=" ")
        if score < 40:
            print("🔴 DANGER")
        elif score < 70:
            print("🟡 CAUTION")
        else:
            print("🟢 SAFE")
        
        if warnings:
            print(f"   Warnings Found: {len(warnings)}")
            for w in warnings[:3]:  # Show first 3
                print(f"      • [{w['severity'].upper()}] {w['category']}: {w['message'][:60]}...")
        else:
            print("   ✅ No warnings detected")
        
        # Check if we found expected issues
        expected = test.get('expected_issues', [])
        if expected:
            found_count = len(matches)
            if found_count >= len(expected):
                print(f"   ✓ Found expected {len(expected)}+ issues")
            else:
                print(f"   ⚠ Expected ~{len(expected)} issues, found {found_count}")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


async def test_real_video(video_id: str):
    """Test with a real YouTube video"""
    print(f"\n🎬 Analyzing real video: {video_id}")
    print("-" * 40)
    
    safety_db = SafetyDatabase()
    analyzer = SafetyAnalyzer(safety_db)
    
    try:
        results = await analyzer.analyze(video_id)
        
        print(f"Safety Score: {results['safety_score']}/100")
        print(f"Transcript Available: {results['transcript_available']}")
        print(f"Warnings: {len(results['warnings'])}")
        
        for w in results['warnings']:
            print(f"  • [{w['severity']}] {w['category']}: {w['message']}")
        
        print(f"\nSummary: {results['summary']}")
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    # Run test suite
    asyncio.run(test_analyzer())
    
    # Optionally test with a real video ID
    # asyncio.run(test_real_video("dQw4w9WgXcQ"))
