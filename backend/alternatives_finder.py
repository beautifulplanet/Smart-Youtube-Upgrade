"""YouTube Safety Inspector - Safe Alternatives Finder
Copyright (c) 2026 beautifulplanet
Licensed under MIT License

Suggests safe/real alternatives to dangerous or AI content.
Uses YouTube Data API to find quality educational replacements.

Data provided by YouTube Data API
https://developers.google.com/youtube
"""

import os
import re
import httpx
import json
from pathlib import Path
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

class SafeAlternativesFinder:
    """Finds safe alternative videos for dangerous/AI content"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with optional YouTube API key and load config files."""
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
        self.enabled = bool(self.api_key)
        self.data_path = Path(__file__).parent / "safety-db" / "alternatives"
        
        # Load configuration from JSON files
        self.animal_keywords = self._load_json("animal_keywords.json", {})
        self.animal_channels = self._load_json("animal_channels.json", {})
        self.safe_search_mappings = self._load_json("safe_search_mappings.json", {})
        self.real_animal_searches = self._load_json("real_animal_searches.json", [])
        self.trusted_channels = self._load_json("trusted_channels.json", [])
        
        # Load fallback data
        self.fallback_tutorials = self._load_json("fallback_tutorials.json", [])
        self.fallback_entertainment = self._load_json("fallback_entertainment.json", [])
        self.fallback_real_animals = self._load_json("fallback_real_animals.json", {})
        
        # Flatten fallback videos for backwards compatibility if needed
        self.fallback_real_videos = self.fallback_real_animals.get("default", [])

    def _load_json(self, filename: str, default: Any) -> Any:
        """Load a JSON config file from the alternatives data directory."""
        try:
            file_path = self.data_path / filename
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            logger.warning(f"Config file not found: {filename}")
            return default
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
            return default
    
    async def find_safe_alternatives(
        self, 
        danger_categories: list[str],
        original_title: str = "",
        is_ai_content: bool = False,
        max_results: int = 10
    ) -> dict:
        """
        Find safe alternative videos based on detected dangers
        
        Args:
            danger_categories: List of flagged danger categories
            original_title: Original video title for context
            is_ai_content: Whether AI-generated content was detected
            max_results: Maximum number of suggestions (increased to 10)
            
        Returns:
            dict with alternative video suggestions
        """
        if not self.enabled:
            return {
                "enabled": False,
                "alternatives": [],
                "message": "YouTube API key not configured"
            }
        
        alternatives = []
        search_queries = []
        detected_animal = None
        
        # If AI content detected, search for real alternatives
        if is_ai_content:
            # Detect specific animal from title
            detected_animal = self._detect_animal(original_title)
            
            if detected_animal:
                # Build targeted searches for this specific animal
                search_queries = self._build_animal_searches(detected_animal, max_results)
                category_type = "real_animals"
            elif self._is_animal_related(original_title):
                # Generic animal content
                search_queries = self.real_animal_searches[:4]
                category_type = "real_animals"
            else:
                # Generic real content searches
                search_queries = self.real_animal_searches[:3]
                category_type = "real_content"
        elif danger_categories:
            # Build search queries from danger categories
            for category in danger_categories:
                if category in self.safe_search_mappings:
                    search_queries.extend(self.safe_search_mappings[category][:2])
            
            # Also check title for specific topics that need alternatives
            title_lower = original_title.lower()
            if any(kw in title_lower for kw in ['smoker', 'bbq', 'grill', 'smoking meat', 'smoke meat']):
                search_queries.extend(self.safe_search_mappings.get('cooking', [])[:2])
                if 'bbq' in self.safe_search_mappings:
                    search_queries.extend(self.safe_search_mappings['bbq'][:2])
            
            # If no specific category, use general safety search
            if not search_queries and original_title:
                search_queries = [f"{original_title} professional tutorial safe"]
            
            category_type = "safe_tutorial"
        else:
            # Check if title suggests we should offer alternatives anyway
            title_lower = original_title.lower() if original_title else ""
            if any(kw in title_lower for kw in ['smoker', 'bbq', 'grill', 'diy', 'hack']):
                search_queries = []
                if any(kw in title_lower for kw in ['smoker', 'bbq', 'grill']):
                    search_queries.extend(self.safe_search_mappings.get('cooking', [])[:2])
                    search_queries.extend(self.safe_search_mappings.get('bbq', [])[:2])
                else:
                    search_queries = [f"{original_title} professional tutorial safe"]
                category_type = "safe_tutorial"
            else:
                # No specific categories, return empty
                return {
                    "enabled": True,
                    "alternatives": [],
                    "message": "No alternatives needed",
                    "category_type": ""
                }
        
        # Search for each query
        seen_ids = set()
        for query in search_queries[:3]:  # Limit to 3 searches
            try:
                results = await self._search_youtube(query, max_results=2)
                for video in results:
                    if video['id'] not in seen_ids:
                        seen_ids.add(video['id'])
                        alternatives.append(video)
                        
                        if len(alternatives) >= max_results:
                            break
                            
            except Exception as e:
                logger.error(f"Search error for '{query}': {e}")
                continue
            
            if len(alternatives) >= max_results:
                break
        
        return {
            "enabled": True,
            "alternatives": alternatives[:max_results],
            "category_type": category_type,
            "message": self._get_message(category_type, len(alternatives), detected_animal),
            "detected_animal": detected_animal,
            "search_queries_used": search_queries[:5]
        }
    
    async def find_real_animal_videos(self, max_results: int = 4) -> dict:
        """Find real animal videos as alternatives to AI animal content"""
        
        if not self.enabled:
            return {"enabled": False, "alternatives": [], "message": "API not configured"}
        
        alternatives = []
        seen_ids = set()
        
        # Search for real animal content
        for query in self.real_animal_searches[:4]:
            try:
                results = await self._search_youtube(query, max_results=2)
                for video in results:
                    if video['id'] not in seen_ids:
                        seen_ids.add(video['id'])
                        # Add a badge for verified real content
                        video['badge'] = '🎬 Real Footage'
                        alternatives.append(video)
                        
                        if len(alternatives) >= max_results:
                            break
            except Exception as e:
                logger.error(f"Animal search error: {e}")
                continue
            
            if len(alternatives) >= max_results:
                break
        
        return {
            "enabled": True,
            "alternatives": alternatives,
            "category_type": "real_animals",
            "message": "🦁 Watch REAL animal videos instead!"
        }
    
    async def search_debunking_videos(self, debunk_queries: list[str], max_results: int = 8) -> dict:
        """
        Search for debunking/educational videos that counter conspiracy or manipulation content.
        
        Args:
            debunk_queries: Targeted search queries from matched signature files
            max_results: Maximum number of videos to return
            
        Returns:
            dict with debunking video alternatives
        """
        if not self.enabled:
            return {
                "enabled": False,
                "alternatives": [],
                "message": "YouTube API key not configured",
                "category_type": "debunking"
            }
        
        alternatives = []
        seen_ids = set()
        
        # Search using the targeted debunk queries from the signature files
        for query in debunk_queries[:4]:  # Limit to 4 searches to conserve API quota
            try:
                results = await self._search_youtube(query, max_results=3)
                for video in results:
                    if video['id'] not in seen_ids:
                        seen_ids.add(video['id'])
                        video['badge'] = '🔬 Debunking'
                        alternatives.append(video)
                        
                        if len(alternatives) >= max_results:
                            break
            except Exception as e:
                logger.error(f"Debunk search error for '{query}': {e}")
                continue
            
            if len(alternatives) >= max_results:
                break
        
        return {
            "enabled": True,
            "alternatives": alternatives[:max_results],
            "category_type": "debunking",
            "message": "🔬 Watch videos that debunk this content"
        }
    
    
    async def find_ai_tutorials(self, detected_subject: str = None, prefer_shorts: bool = False, max_results: int = 8) -> dict:
        """
        Find tutorials on HOW TO MAKE AI videos
        Great for creators who want to learn the craft
        """
        # Return fallback videos if API not available
        if not self.enabled:
            return {
                "enabled": True,
                "alternatives": self.fallback_tutorials[:max_results],
                "category_type": "ai_tutorials", 
                "message": "🎓 Learn to create AI videos! (curated picks)",
                "detected_subject": detected_subject,
                "is_shorts": prefer_shorts
            }
        
        # AI video creation tutorial search queries - high engagement content
        ai_tutorial_searches = []
        
        # If we detected a specific subject (animals, landscapes, etc), personalize
        if detected_subject:
            ai_tutorial_searches.extend([
                f"how to make AI {detected_subject} video tutorial",
                f"AI {detected_subject} video generator tutorial",
                f"create AI {detected_subject} content step by step",
                f"best AI tool for {detected_subject} videos",
            ])
        
        # General AI video creation tutorials
        ai_tutorial_searches.extend([
            "how to make AI video tutorial 2024",
            "AI video generator tutorial beginners",
            "Sora AI tutorial how to use",
            "Runway ML tutorial create video",
            "Pika Labs AI video tutorial",
            "how to make viral AI video",
            "AI video editing tutorial complete guide",
            "stable diffusion video tutorial",
            "AI animation tutorial beginners",
            "midjourney video AI tutorial",
            "best AI video tools 2024 tutorial",
            "create AI content youtube tutorial",
        ])
        
        # Shorts-specific searches
        if prefer_shorts:
            ai_tutorial_searches = [
                f"{q} #shorts" for q in ai_tutorial_searches[:6]
            ] + [
                "AI video tutorial shorts",
                "quick AI video tips shorts",
                "AI tools explained 60 seconds",
            ]
        
        alternatives = []
        seen_ids = set()
        
        for query in ai_tutorial_searches[:6]:
            try:
                results = await self._search_youtube(query, max_results=3)
                for video in results:
                    if video['id'] not in seen_ids:
                        seen_ids.add(video['id'])
                        video['badge'] = '🎓 Tutorial'
                        video['content_type'] = 'ai_tutorial'
                        alternatives.append(video)
                        
                        if len(alternatives) >= max_results:
                            break
            except Exception as e:
                logger.error(f"AI tutorial search error: {e}")
                continue
            
            if len(alternatives) >= max_results:
                break
        
        # Fall back to curated list if search returns nothing
        if not alternatives:
            alternatives = self.fallback_tutorials[:max_results]
        
        subject_text = f" {detected_subject}" if detected_subject else ""
        format_text = "Shorts" if prefer_shorts else "tutorials"
        
        return {
            "enabled": True,
            "alternatives": alternatives[:max_results],
            "category_type": "ai_tutorials",
            "message": f"🎬 Learn to make AI{subject_text} videos! ({len(alternatives)} {format_text})",
            "detected_subject": detected_subject,
            "is_shorts": prefer_shorts
        }
    
    async def find_ai_entertainment(self, detected_subject: str = None, prefer_shorts: bool = False, max_results: int = 8) -> dict:
        """
        Find quality AI entertainment content for users who WANT to watch AI videos
        Curated, high-quality AI content creators
        """
        # Return fallback videos if API not available
        if not self.enabled:
            return {
                "enabled": True,
                "alternatives": self.fallback_entertainment[:max_results],
                "category_type": "ai_entertainment",
                "message": "🎨 Quality AI content (curated picks)",
                "detected_subject": detected_subject,
                "is_shorts": prefer_shorts
            }
        
        # Quality AI content creators and searches
        ai_entertainment_searches = []
        
        # Subject-specific AI content
        if detected_subject:
            ai_entertainment_searches.extend([
                f"best AI {detected_subject} video compilation",
                f"amazing AI {detected_subject} art",
                f"AI {detected_subject} most realistic",
                f"incredible AI generated {detected_subject}",
            ])
        
        # Quality AI entertainment channels/content
        ai_entertainment_searches.extend([
            "best AI generated videos compilation",
            "AI art video showcase amazing",
            "satisfying AI video compilation",
            "AI video most realistic 2024",
            "mind blowing AI generated content",
            "AI animation incredible",
            "futuristic AI video art",
            "AI music video official",
            "creative AI video project",
            "AI short film high quality",
        ])
        
        # Shorts preference
        if prefer_shorts:
            ai_entertainment_searches = [
                f"{q} #shorts" for q in ai_entertainment_searches[:6]
            ] + [
                "AI video shorts viral",
                "AI art shorts amazing",
                "best AI shorts compilation",
            ]
        
        alternatives = []
        seen_ids = set()
        
        for query in ai_entertainment_searches[:6]:
            try:
                results = await self._search_youtube(query, max_results=3)
                for video in results:
                    if video['id'] not in seen_ids:
                        seen_ids.add(video['id'])
                        video['badge'] = '🤖 AI Content'
                        video['content_type'] = 'ai_entertainment'
                        alternatives.append(video)
                        
                        if len(alternatives) >= max_results:
                            break
            except Exception as e:
                logger.error(f"AI entertainment search error: {e}")
                continue
            
            if len(alternatives) >= max_results:
                break
        
        # Fall back to curated list if search returns nothing
        if not alternatives:
            alternatives = self.fallback_entertainment[:max_results]
        
        subject_text = f" {detected_subject}" if detected_subject else ""
        format_text = "Shorts" if prefer_shorts else "videos"
        
        return {
            "enabled": True,
            "alternatives": alternatives[:max_results],
            "category_type": "ai_entertainment",
            "message": f"🎨 Quality AI{subject_text} content ({len(alternatives)} {format_text})",
            "detected_subject": detected_subject,
            "is_shorts": prefer_shorts
        }
    
    def _detect_animal(self, text: str) -> Optional[str]:
        """Detect specific animal type from text"""
        if not text:
            return None
            
        text_lower = text.lower()
        
        for animal, keywords in self.animal_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return animal
        
        return None
    
    def _build_animal_searches(self, animal: str, max_queries: int = 8) -> list:
        """Build diverse search queries for a specific animal"""
        searches = []
        
        # Capitalize for better search results
        animal_cap = animal.capitalize()
        
        # Big network documentaries
        searches.append(f"BBC Earth {animal} documentary")
        searches.append(f"National Geographic {animal} wild")
        
        # Popular wildlife YouTubers
        searches.append(f"Brave Wilderness {animal}")
        searches.append(f"The Dodo {animal} rescue")
        
        # Educational/funny real content
        searches.append(f"{animal} real footage wildlife")
        searches.append(f"{animal} zoo animals real")
        searches.append(f"funny real {animal} compilation")
        
        # Specialized content
        searches.append(f"{animal} behavior documentary")
        searches.append(f"{animal} in the wild nature")
        searches.append(f"cute {animal} real video")
        
        return searches[:max_queries]
    
    def _build_generic_animal_searches(self) -> list:
        """Build diverse generic animal searches"""
        return [
            "BBC Earth animals documentary",
            "National Geographic wildlife",
            "The Dodo animal rescue",
            "Brave Wilderness animals",
            "cute animals real footage",
            "funny animals compilation real",
            "zoo animals documentary",
            "wildlife photography real"
        ]
    
    async def _search_youtube(self, query: str, max_results: int = 3) -> list:
        """Search YouTube for videos"""
        
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "key": self.api_key,
            "q": query,
            "part": "snippet",
            "type": "video",
            "maxResults": max_results,
            "safeSearch": "strict",
            "videoEmbeddable": "true",
            "relevanceLanguage": "en",
            "order": "relevance"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            
            if response.status_code != 200:
                logger.error(f"YouTube search error: {response.status_code}")
                return []
            
            data = response.json()
            videos = []
            
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                video_id = item.get("id", {}).get("videoId")
                
                if video_id:
                    channel = snippet.get("channelTitle", "")
                    is_trusted = any(tc.lower() in channel.lower() for tc in self.trusted_channels)
                    
                    videos.append({
                        "id": video_id,
                        "title": snippet.get("title", ""),
                        "channel": channel,
                        "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                        "description": snippet.get("description", "")[:150],
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "is_trusted": is_trusted,
                        "badge": "✅ Trusted Source" if is_trusted else "📚 Educational"
                    })
            
            # Sort to prioritize trusted channels
            videos.sort(key=lambda x: (not x['is_trusted'], x['title']))
            
            return videos
    
    def _is_animal_related(self, title: str) -> bool:
        """Check if title seems to be about animals"""
        animal_keywords = [
            'animal', 'dog', 'cat', 'bird', 'lion', 'tiger', 'bear',
            'elephant', 'monkey', 'horse', 'rabbit', 'fish', 'shark',
            'whale', 'dolphin', 'pet', 'puppy', 'kitten', 'wildlife',
            'zoo', 'safari', 'nature', 'creature', 'beast', 'wolf',
            'fox', 'deer', 'snake', 'reptile', 'insect', 'butterfly'
        ]
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in animal_keywords)
    
    def _get_message(self, category_type: str, count: int, animal: str = None) -> str:
        """Get appropriate message for alternatives"""
        if count == 0:
            return "No alternatives found"
        
        if animal and category_type == "real_animals":
            animal_cap = animal.capitalize()
            return f"🦁 {count} REAL {animal_cap} videos to watch instead!"
        
        messages = {
            "real_animals": f"🦁 {count} REAL animal videos to watch!",
            "real_content": f"🎬 {count} verified real videos",
            "safe_tutorial": f"✅ {count} safer, professional alternatives",
            "default": f"📚 {count} educational alternatives"
        }
        
        return messages.get(category_type, messages["default"])


# Singleton
_finder = None

def get_alternatives_finder() -> SafeAlternativesFinder:
    """Return the singleton SafeAlternativesFinder instance."""
    global _finder
    if _finder is None:
        _finder = SafeAlternativesFinder()
    return _finder
