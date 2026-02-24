"""YouTube Safety Inspector - Safety Analyzer
Copyright (c) 2026 beautifulplanet
Licensed under MIT License

Core analysis engine that combines transcript extraction, 
signature matching, comment analysis, and AI analysis.

Data provided by YouTube Data API
https://developers.google.com/youtube
"""

import re
import asyncio
import os
from typing import Optional, TYPE_CHECKING
from youtube_transcript_api import YouTubeTranscriptApi
from safety_db import SafetyDatabase
from youtube_data import YouTubeDataFetcher, analyze_comments

if TYPE_CHECKING:
    from ai_reviewer import AIContextReviewer

import logging
logger = logging.getLogger(__name__)

# --- Analysis constants ---
# Input truncation limits (ReDoS prevention)
MAX_TITLE_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 2000
MAX_CHANNEL_LENGTH = 200
MAX_FULL_TEXT_LENGTH = 3000
MAX_SIGNATURE_TEXT_LENGTH = 50000

# Scoring thresholds
AI_CONTENT_MAX_SCORE = 20          # Max score when AI content detected
DANGEROUS_ANIMAL_MAX_SCORE = 10    # Max score when dangerous animal/child detected
DEFAULT_SAFE_SCORE = 95            # Score when no issues found
BASE_SCORE = 100                   # Starting score before penalties

# Score weighting (transcript vs community feedback)
TRANSCRIPT_WEIGHT = 0.6            # Weight for transcript analysis when available
COMMENT_WEIGHT = 0.4               # Weight for comment analysis when transcript available
NO_TRANSCRIPT_WEIGHT = 0.3         # Weight for transcript when unavailable
NO_TRANSCRIPT_COMMENT_WEIGHT = 0.7 # Weight for comments when no transcript

# Severity penalty weights for category scoring
CATEGORY_SEVERITY_WEIGHTS = {"high": 30, "medium": 15, "low": 5}

# Severity penalty weights for overall scoring
OVERALL_SEVERITY_PENALTIES = {"high": 25, "medium": 12, "low": 5}

# Score weighting for final calculation (base vs categories)
BASE_SCORE_WEIGHT = 0.6
CATEGORY_SCORE_WEIGHT = 0.4

# AI detection thresholds
AI_HASHTAG_THRESHOLD = 2           # Hashtags needed to flag as "very likely AI"
AI_HASHTAG_WITH_CHANNEL = 1        # Hashtags needed when combined with suspicious channel

# Comment fetching
MAX_COMMENTS_TO_FETCH = 100


class SafetyAnalyzer:
    """
    Main analysis engine that:
    1. Extracts video transcripts
    2. Fetches and analyzes community comments
    3. Matches content against danger signatures
    4. Optionally uses AI for contextual analysis
    5. Generates safety scores and warnings
    """
    
    # Trusted channels - skip AI flagging for these verified sources
    TRUSTED_CHANNELS = [
        "bbc earth", "bbc", "national geographic", "nat geo wild",
        "discovery", "discovery channel", "animal planet",
        "smithsonian channel", "pbs", "nova pbs",
        "this old house", "bob vila", 
        "doctor mike", "medlife crisis", "chubbyemu",
        "scishow", "veritasium", "mark rober", "kurzgesagt",
        "crash course", "ted", "ted-ed",
        "the dodo", "brave wilderness",
        "gordon ramsay", "bon appétit", "america's test kitchen",
        "home repair tutor", "see jane drill",
        "engineering explained", "practical engineering",
        "technology connections", "bigclivedotcom"
    ]
    
    def __init__(self, safety_db: SafetyDatabase, youtube_api_key: Optional[str] = None, ai_reviewer: Optional['AIContextReviewer'] = None):
        """Initialize with safety signature database, optional YouTube API key, and optional AI reviewer."""
        self.safety_db = safety_db
        self.signatures = safety_db.get_all_signatures()
        # Get API key from param, env, or None
        self.youtube_api_key = youtube_api_key or os.environ.get("YOUTUBE_API_KEY")
        # AI context reviewer for verifying metadata signature matches
        self.ai_reviewer = ai_reviewer
        
        # Suspicious channel name patterns (channels that typically post AI content)
        self._suspicious_channel_patterns = [
            re.compile(r"talk\s*(with|to|ing)?\s*(rico|pet|animal|bird|parrot|cat|dog)", re.IGNORECASE),
            re.compile(r"(pet|animal|bird|parrot|cat|dog)\s*talk", re.IGNORECASE),
            re.compile(r"(funny|cute)\s*(pet|animal|bird|parrot|cat|dog)\s*video", re.IGNORECASE),
            re.compile(r"ai\s*(pet|animal|content|video|generated)", re.IGNORECASE),
        ]

        # Hashtag patterns that suggest AI-generated animal content
        self._ai_hashtag_patterns = [
            re.compile(r"#talkingbird", re.IGNORECASE),
            re.compile(r"#talkingparrot", re.IGNORECASE),
            re.compile(r"#talkingcat", re.IGNORECASE),
            re.compile(r"#talkingdog", re.IGNORECASE),
            re.compile(r"#talkinganimal", re.IGNORECASE),
            re.compile(r"#funnybirds", re.IGNORECASE),
            re.compile(r"#funnypetvideos", re.IGNORECASE),
            re.compile(r"#parrottalking", re.IGNORECASE),
            re.compile(r"#birdtalking", re.IGNORECASE),
            re.compile(r"#cattalking", re.IGNORECASE),
            re.compile(r"#dogtalking", re.IGNORECASE),
            re.compile(r"#aianimals", re.IGNORECASE),
            re.compile(r"#aigenerated", re.IGNORECASE),
            re.compile(r"#aiart", re.IGNORECASE),
            re.compile(r"#aivideo", re.IGNORECASE),
        ]
        
        # Heuristic patterns for impossible/AI content
        # Animals that appear to talk, have conversations, or do impossible things
        self._impossible_patterns = [
            # TWO animals having a conversation (dead giveaway for AI)
            (re.compile(r"\b(two|2|both|pair)\b.{0,20}\b(parrot|bird|cat|dog|animal)s?\b.{0,30}\b(talk|convers|chat|argue|discuss|debate)", re.IGNORECASE),
             "Two animals having a conversation (AI content)"),
            (re.compile(r"\b(parrot|bird|cat|dog)s?\b.{0,20}\b(talk|convers|chat|argue)\b.{0,20}\b(each other|together|to one another)", re.IGNORECASE),
             "Animals conversing with each other (AI content)"),
            # Parrot/bird specific conversations
            (re.compile(r"\b(parrot|parakeet|cockatoo|budgie|macaw)s?\b.{0,30}\b(conversation|talking to|chatting with|argues with|debates)", re.IGNORECASE),
             "Parrots having human-like conversation (likely AI)"),
            (re.compile(r"\b(parrot|bird)s?\b.{0,15}\b(having a|in a|long|full|real|actual)\b.{0,10}\b(conversation|discussion|debate|argument)", re.IGNORECASE),
             "Animals having extended conversation (AI content)"),
            # Generic talking animals - conversation keywords
            (re.compile(r"\b(parrot|bird|cat|dog|monkey|ape|gorilla|chimp|elephant|lion|tiger|bear|fox|raccoon|squirrel|rabbit|hamster|horse|cow|pig|chicken|duck|goose|owl|crow|raven|fish|shark|whale|dolphin|seal|penguin|frog|turtle|snake|lizard|gecko|iguana|crocodile|alligator)\b.{0,40}\b(talk|talking|speaks|speaking|says|said|conversation|chat|chatting|argue|arguing|debate|interview|podcast|call|phone|answer|respond|tells|told|ask|asking|wants|demanded|yells|screaming|complain|rant|confess|admit|explain|announce|declare|insist|refuse|agree|disagree)\b", re.IGNORECASE),
             "Animal appearing to communicate like a human"),
            (re.compile(r"\b(talk|talking|speaks|speaking|says|said|conversation|chat|chatting|argue|arguing|debate|interview|podcast|call|phone|answer|respond|tells|told|ask|asking|wants|demanded|yells|screaming|complain|rant|confess|admit|explain|announce|declare|insist|refuse|agree|disagree)\b.{0,40}\b(parrot|bird|cat|dog|monkey|ape|gorilla|chimp|elephant|lion|tiger|bear|fox|raccoon|squirrel|rabbit|hamster|horse|cow|pig|chicken|duck|goose|owl|crow|raven|fish|shark|whale|dolphin|seal|penguin|frog|turtle|snake|lizard|gecko|iguana|crocodile|alligator)\b", re.IGNORECASE),
             "Animal appearing to communicate like a human"),
            # Animals wanting/demanding things (AI trope)
            (re.compile(r"\b(parrot|bird|cat|dog|monkey|gorilla|raccoon|fox|bear|elephant|lion|tiger)\b.{0,20}\b(wants|needs|demands|orders|requests|insists|refuses|complains)\b.{0,20}\b(fbi|police|911|lawyer|manager|refund|divorce|custody|money|revenge)\b", re.IGNORECASE),
             "Animal demanding human services (common AI trope)"),
            # Animals doing impossible human activities
            (re.compile(r"\b(cat|dog|bird|parrot|monkey|bear|lion|tiger|elephant|gorilla|raccoon|fox|squirrel|rabbit|fish|penguin|owl)\b.{0,30}\b(drive|driving|drove|cook|cooking|cooked|play piano|playing piano|type|typing|typed|text|texting|texted|email|emailing|read|reading|write|writing|wrote|paint|painting|painted|sing|singing|sang|dance|dancing|danced|ballet|opera|graduate|graduating|married|wedding|divorce|court|sue|lawsuit)\b", re.IGNORECASE),
             "Animal performing impossible human activity"),
            # Animals with jobs/professions
            (re.compile(r"\b(cat|dog|bird|parrot|raccoon|monkey|bear)\b.{0,20}\b(lawyer|doctor|chef|pilot|driver|ceo|manager|employee|boss|judge|cop|officer|agent|detective)\b", re.IGNORECASE),
             "Animal with human profession (likely AI)"),
            # Impossible animal interactions
            (re.compile(r"\b(cat|dog|bird|mouse|rabbit|hamster|fish|parrot)\b.{0,30}\b(save|saves|saved|rescue|rescues|rescued|hero|call 911|calls 911|called 911|call police|calls police|ambulance|fire department)\b", re.IGNORECASE),
             "Animal performing heroic human actions"),
            # Viral AI tropes
            (re.compile(r"\b(animal|cat|dog|bird|parrot).{0,20}(facetime|video call|zoom|teams call|skype)\b", re.IGNORECASE),
             "Animal on video call (common AI trope)"),
            (re.compile(r"\b(cat|dog|parrot|bird).{0,20}(order|ordering|ordered|uber|doordash|pizza|food delivery|amazon|online shopping)\b", re.IGNORECASE),
             "Animal ordering services (common AI trope)"),
            # Animals in legal/dramatic situations
            (re.compile(r"\b(cat|dog|parrot|bird|raccoon|monkey).{0,30}(court|trial|testif|lawyer|sue|custody|arrested|jail|prison|fbi|cia|police|detective|investigate)\b", re.IGNORECASE),
             "Animal in legal/dramatic situation (likely AI)"),
            # Animals with human emotions/drama
            (re.compile(r"\b(cat|dog|parrot|bird|raccoon).{0,20}(breakup|broke up|cheating|cheated|divorce|married|wedding|pregnant|baby daddy|custody battle)\b", re.IGNORECASE),
             "Animal in human relationship drama (likely AI)"),
        ]
        
        # SAFETY patterns - dangerous animals near children/babies
        self._dangerous_animal_child_patterns = [
            (re.compile(r"\b(parrot|cockatoo|macaw|cockatiel|conure|african grey|amazon parrot|eclectus|bird)\b.{0,50}\b(baby|infant|newborn|toddler|child|kid|sleeping|nap|crib|bed)\b", re.IGNORECASE),
             "SAFETY: Large parrot/bird near baby/child - parrots have powerful beaks (300+ PSI) that can cause serious injury"),
            (re.compile(r"\b(baby|infant|newborn|toddler|child|kid|sleeping)\b.{0,50}\b(parrot|cockatoo|macaw|cockatiel|conure|african grey|bird)\b", re.IGNORECASE),
             "SAFETY: Baby/child near large bird - birds can bite unpredictably and cause serious injury"),
            (re.compile(r"(?=.*\b(baby|infant|newborn|toddler)\b)(?=.*\b(parrot|cockatoo|macaw|bird)\b)", re.IGNORECASE),
             "SAFETY: Video shows baby with parrot/bird - large birds have dangerous beaks and can injure infants"),
            (re.compile(r"\b(pit ?bull|rottweiler|german shepherd|doberman|husky|malamute|akita|chow|mastiff|great dane|wolf ?dog)\b.{0,50}\b(baby|infant|newborn|toddler|sleep|alone|unsupervised)\b", re.IGNORECASE),
             "SAFETY: Large/powerful dog near unsupervised baby - never leave children unattended with dogs"),
            (re.compile(r"\b(baby|infant|newborn|toddler)\b.{0,50}\b(pit ?bull|rottweiler|husky|german shepherd|dog)\b.{0,30}\b(sleep|alone|unsupervised)\b", re.IGNORECASE),
             "SAFETY: Baby sleeping near dog - dogs should never be left unsupervised with infants"),
            (re.compile(r"(?=.*\b(baby|infant|newborn|toddler)\b)(?=.*\b(pit ?bull|rottweiler|husky|wolf|malamute)\b)", re.IGNORECASE),
             "SAFETY: Video shows baby with large/powerful dog - dogs should never be left unsupervised with infants"),
            (re.compile(r"\b(cat|kitten)\b.{0,40}\b(baby|infant|newborn)\b.{0,30}\b(sleep|sleeping|crib|face|breathing)\b", re.IGNORECASE),
             "SAFETY: Cat near sleeping baby - cats can accidentally suffocate infants"),
            (re.compile(r"\b(snake|python|boa|constrictor|reptile|monitor lizard|alligator|crocodile|wolf|coyote|fox|raccoon|monkey|chimp|chimpanzee|primate)\b.{0,50}\b(baby|infant|toddler|child|kid|play|hug|cuddle|sleep)\b", re.IGNORECASE),
             "SAFETY: Wild/exotic animal near child - extremely dangerous, wild animals are unpredictable"),
            (re.compile(r"\b(baby|infant|toddler|child|kid)\b.{0,50}\b(snake|python|boa|monitor|alligator|crocodile|wolf|coyote|monkey|chimp|primate)\b", re.IGNORECASE),
             "SAFETY: Child near wild/exotic animal - these animals can cause severe injury or death"),
            (re.compile(r"\b(baby|infant|newborn|toddler)\b.{0,40}\b(sleep|sleeping|nap)\b.{0,40}\b(with|next to|beside|near)\b.{0,30}\b(pet|animal|dog|cat|bird|parrot)\b", re.IGNORECASE),
             "SAFETY: Baby sleeping with pet - animals should never be left unsupervised with sleeping infants"),
        ]

        # Title/description red flag patterns — catch dangerous content even without transcript
        # These detect misinformation, dangerous advice, and harmful content from metadata alone
        self._title_red_flag_patterns = [
            # Medical misinformation
            (re.compile(r"\b(cur(e|ed|es|ing)|heal(s|ed|ing)?|treat(s|ed|ing)?|fix(es|ed|ing)?|revers(e|ed|es|ing)|eliminat(e|ed|es|ing)|destroy(s|ed|ing)?)\b.{0,40}\b(cancer|tumor|diabetes|alzheimer|parkinson|autism|hiv|aids|herpes|lupus|ms|multiple sclerosis|depression|anxiety|adhd|ptsd|epilepsy|arthritis|asthma)\b", re.IGNORECASE),
             ("medical", "high", "Claims to cure/treat serious medical conditions — may be dangerous misinformation")),
            (re.compile(r"\b(doctors?|big pharma|hospital|they|government|fda|cdc)\b.{0,30}\b(don'?t want|hiding|won'?t tell|secret|lying|cover.?up|suppress|conceal|conspir)", re.IGNORECASE),
             ("medical", "high", "Uses conspiracy framing against medical establishment — potential medical misinformation")),
            (re.compile(r"\b(stop|quit|ditch|throw away|don'?t take|never take|avoid)\b.{0,20}\b(chemo|medication|medicine|pills?|insulin|vaccine|antibiotics|prescri)", re.IGNORECASE),
             ("medical", "high", "Advises stopping medical treatment — dangerous medical misinformation")),
            (re.compile(r"\b(miracle|secret|ancient|natural|home)\b.{0,20}\b(cure|remedy|treatment|healing|medicine|solution)\b", re.IGNORECASE),
             ("medical", "medium", "Promotes unverified 'miracle' or 'secret' cure — verify with healthcare provider")),
            (re.compile(r"\b(ivermectin|hydroxychloroquine|mms|turpentine|borax|colloidal silver|black salve|apricot seeds|laetrile)\b.{0,30}\b(cure|treat|heal|cancer|covid|virus)", re.IGNORECASE),
             ("medical", "high", "Promotes debunked/dangerous substance as medical treatment")),

            # Chemical dangers
            (re.compile(r"\b(mix|combine|blend|add)\b.{0,20}\b(bleach|ammonia|chlorine|acid|hydrogen peroxide|vinegar)\b.{0,20}\b(and|with|plus|\+)\b.{0,20}\b(bleach|ammonia|chlorine|acid|hydrogen peroxide|vinegar)\b", re.IGNORECASE),
             ("chemical", "high", "Mixing household chemicals can create toxic/lethal gases")),
            (re.compile(r"\b(bleach|ammonia)\b.{0,40}\b(ammonia|bleach)\b", re.IGNORECASE),
             ("chemical", "high", "Bleach and ammonia together create deadly chloramine gas")),
            (re.compile(r"\b(drink|ingest|consume|swallow|eat)\b.{0,20}\b(bleach|ammonia|hydrogen peroxide|borax|turpentine|gasoline|kerosene|antifreeze|tide pod|detergent|cleaning)", re.IGNORECASE),
             ("chemical", "high", "Ingesting household chemicals is potentially fatal")),

            # Dangerous DIY / fire hazards
            (re.compile(r"\b(make|build|diy|homemade)\b.{0,20}\b(bomb|explosive|grenade|gun|taser|flame ?thrower|weapon|napalm|thermite|firework|rocket fuel)\b", re.IGNORECASE),
             ("diy", "high", "DIY weapons/explosives — extremely dangerous and potentially illegal")),
            (re.compile(r"\b(microwave|oven|toaster)\b.{0,30}\b(metal|aluminum|foil|battery|aerosol|lighter|spray can|phone)\b", re.IGNORECASE),
             ("diy", "high", "Microwaving metal/batteries/aerosol is an explosion/fire hazard")),
            (re.compile(r"\b(penny|coin)\b.{0,15}\b(in|into)\b.{0,10}\b(outlet|socket|fuse|electrical)\b", re.IGNORECASE),
             ("electrical", "high", "Inserting objects into outlets can cause electrocution/fire")),

            # Dangerous fitness / body modification
            (re.compile(r"\b(inject|injecting|injection)\b.{0,20}\b(synthol|oil|silicone|saline)\b.{0,20}\b(muscle|arm|bicep|chest|calf)\b", re.IGNORECASE),
             ("fitness", "high", "Injecting substances into muscles is extremely dangerous — risk of embolism, infection, death")),
            (re.compile(r"\b(dry|water)\b.{0,5}\bfast(ing)?\b.{0,20}\b(\d{2,}|week|month|30|40|21)\b", re.IGNORECASE),
             ("medical", "high", "Extended fasting without supervision can cause organ failure and death")),

            # Electrical dangers
            (re.compile(r"\b(hack|bypass|jump|short|bridge|hot ?wire)\b.{0,20}\b(electric(al)?|power|meter|breaker|fuse|circuit|panel|wire|outlet|plug)\b", re.IGNORECASE),
             ("electrical", "high", "Tampering with electrical systems without qualification risks electrocution/fire")),
            
            # Child safety / predatory content
            (re.compile(r"\b(kids?|children|child|minor|teen|underage)\b.{0,30}\b(challenge|dare|prank|trick)\b.{0,30}\b(dangerous|deadly|extreme|painful|hurt|fire|bleach|tide)", re.IGNORECASE),
             ("childcare", "high", "Dangerous 'challenge' targeting minors — potential harm to children")),

            # Dangerous driving (handles both word orders: "racing on highway" AND "street racing")
            (re.compile(r"\b(speed(ing)?|race|racing|drift(ing)?|stunt(s|ing)?)\b.{0,20}\b(public|highway|road|street|traffic|residential|school zone)\b", re.IGNORECASE),
             ("driving_dmv", "medium", "Dangerous driving on public roads — risk to self and others")),
            (re.compile(r"\b(street|highway|public|road|residential|school zone)\b.{0,20}\b(race|racing|drift(ing)?|stunt(ing)?|speed(ing)?)\b", re.IGNORECASE),
             ("driving_dmv", "medium", "Dangerous driving on public roads — risk to self and others")),
            (re.compile(r"\b(drunk|intoxicated|buzzed|high)\b.{0,15}\b(driv(e|ing)|behind the wheel)\b", re.IGNORECASE),
             ("driving_dmv", "high", "Impaired driving — illegal and extremely dangerous")),
            
            # Cooking dangers
            (re.compile(r"\b(raw|uncooked)\b.{0,15}\b(chicken|pork|meat|egg|fish|shellfish|shrimp)\b.{0,20}\b(safe|fine|ok|healthy|delicious|eat|sashimi)\b", re.IGNORECASE),
             ("cooking", "medium", "Raw/undercooked meat can contain harmful bacteria — verify food safety")),
            (re.compile(r"\b(deep fry|frying)\b.{0,20}\b(frozen|ice|water|wet)\b", re.IGNORECASE),
             ("cooking", "high", "Adding water/ice to hot oil causes explosive splattering and severe burns")),
            
            # Financial scams
            (re.compile(r"\b(guaranteed|100%|proven|risk.?free)\b.{0,20}\b(profit|returns?|income|money|rich|wealth|millionaire)\b", re.IGNORECASE),
             ("financial", "medium", "Promises guaranteed financial returns — likely a scam or misleading")),
            (re.compile(r"\b(send|give|transfer|deposit)\b.{0,20}\b(bitcoin|crypto|btc|eth|money)\b.{0,30}\b(double|triple|multiply|10x|100x|guaranteed)\b", re.IGNORECASE),
             ("financial", "high", "Crypto multiplication scheme — this is a scam")),
        ]
        
    def _detect_impossible_content(self, title: str, description: str = "", channel: str = "", tags: list[str] | None = None) -> str | None:
        """
        Detect likely AI content based on impossible scenarios in video title,
        description, hashtags, channel name, and tags.
        Returns description of why it's flagged, or None if not detected.
        """
        tags = tags or []

        # Truncate inputs to prevent ReDoS (bound regex backtracking)
        title = (title or "")[:MAX_TITLE_LENGTH]
        description = (description or "")[:MAX_DESCRIPTION_LENGTH]
        channel = (channel or "")[:MAX_CHANNEL_LENGTH]

        # Combine all text for analysis
        full_text = f"{title} {description}".lower()
        channel_lower = channel.lower() if channel else ""
        
        # Check title patterns
        for pattern, reason in self._impossible_patterns:
            if pattern.search(full_text):
                return reason
        
        # Check for suspicious hashtags (high confidence for AI content)
        hashtag_count = 0
        matched_hashtags = []
        for hashtag_pattern in self._ai_hashtag_patterns:
            if hashtag_pattern.search(full_text):
                hashtag_count += 1
                matched_hashtags.append(hashtag_pattern.pattern.replace("#", "").replace("\\", ""))
        
        # 2+ AI-related hashtags = very likely AI
        if hashtag_count >= AI_HASHTAG_THRESHOLD:
            return f"Multiple AI-associated hashtags detected: {', '.join(matched_hashtags[:3])}"

        # Check channel name patterns
        for pattern in self._suspicious_channel_patterns:
            if pattern.search(channel_lower):
                # Channel name alone isn't enough, but combined with 1 hashtag = flag
                if hashtag_count >= AI_HASHTAG_WITH_CHANNEL:
                    return f"Suspicious channel pattern + AI hashtags (channel: {channel})"
        
        # Check tags from video metadata
        suspicious_tags = ["talking parrot", "talking bird", "talking cat", "talking dog", 
                          "ai generated", "ai video", "funny animals talking"]
        for tag in tags:
            tag_lower = tag.lower()
            for sus_tag in suspicious_tags:
                if sus_tag in tag_lower:
                    return f"Suspicious video tag: '{tag}'"
        
        return None
    
    def _detect_dangerous_animal_child(self, title: str, description: str = "", tags: list[str] | None = None) -> str | None:
        """
        Detect dangerous situations with animals and children/babies.
        Returns safety warning description or None.
        """
        tags = tags or []

        # Truncate inputs to prevent ReDoS (bound regex backtracking)
        title = (title or "")[:MAX_TITLE_LENGTH]
        description = (description or "")[:MAX_DESCRIPTION_LENGTH]

        full_text = f"{title} {description} {' '.join(tags)}"[:MAX_FULL_TEXT_LENGTH].lower()
        
        for pattern, warning in self._dangerous_animal_child_patterns:
            if pattern.search(full_text):
                return warning
        
        return None
    
    def _detect_title_red_flags(self, title: str, description: str = "", tags: list[str] | None = None) -> list[dict]:
        """
        Detect dangerous/misleading content from title and description patterns.
        Returns a list of warning dicts, or empty list if nothing found.
        
        This catches content that the narrow signature triggers miss,
        especially when no transcript is available.
        """
        tags = tags or []
        title = (title or "")[:MAX_TITLE_LENGTH]
        description = (description or "")[:MAX_DESCRIPTION_LENGTH]
        
        full_text = f"{title} {description} {' '.join(tags)}"[:MAX_FULL_TEXT_LENGTH].lower()
        
        warnings = []
        seen_categories = set()  # Avoid duplicate category warnings
        
        for pattern, (category, severity, message) in self._title_red_flag_patterns:
            if pattern.search(full_text):
                # Only add one warning per category to avoid spam
                cat_key = f"{category}:{severity}"
                if cat_key not in seen_categories:
                    seen_categories.add(cat_key)
                    warnings.append({
                        "category": self.safety_db.get_category_name(category),
                        "severity": severity,
                        "message": f"⚠️ {message}",
                        "timestamp": None
                    })
                    logger.info(f"🚩 Title red flag: [{category}/{severity}] {message}")
        
        return warnings
        
    async def analyze(self, video_id: str, scraped_title: str = None, scraped_description: str = None, scraped_channel: str = None) -> dict:
        """
        Perform full safety analysis on a video.
        
        Args:
            video_id: YouTube video ID
            scraped_title: Optional title scraped by extension (fallback if no API key)
            scraped_description: Optional description from extension
            scraped_channel: Optional channel name from extension
            
        Returns:
            Analysis results including safety score, warnings, and categories
        """
        # Step 0: Get video metadata (channel name) to check if trusted
        channel_name = scraped_channel or ""
        video_title = scraped_title or ""
        video_description = scraped_description or ""
        video_tags = []
        is_trusted_channel = False
        
        # Try to fetch from YouTube API (more complete data)
        try:
            async with YouTubeDataFetcher(api_key=self.youtube_api_key) as fetcher:
                metadata = await fetcher.get_video_metadata(video_id)
                if metadata:
                    channel_name = metadata.channel or channel_name
                    video_title = metadata.title or video_title
                    video_description = metadata.description or video_description
                    video_tags = metadata.tags or []
        except Exception as e:
            logger.warning(f"Metadata fetch failed (using scraped data): {e}")
        
        # Check if trusted channel
        is_trusted_channel = channel_name.lower() in self.TRUSTED_CHANNELS if channel_name else False
        
        logger.info(f"📺 Analyzing: '{video_title}' by '{channel_name}'")
        logger.info(f"   Trusted: {is_trusted_channel}, Has API key: {bool(self.youtube_api_key)}")
        
        # Step 1: Get transcript
        transcript_text, transcript_available = await self._get_transcript(video_id)
        
        # Step 2: Get and analyze comments (community warnings)
        comment_analysis = await self._analyze_comments(video_id)
        
        # If trusted channel, filter out AI warnings (they're likely false positives)
        if is_trusted_channel:
            logger.info(f"✅ Trusted channel: {channel_name} - skipping AI warnings")
            comment_analysis["warnings"] = [
                w for w in comment_analysis.get("warnings", [])
                if w.get("category") != "AI Content"
            ]
            comment_analysis["has_ai_content"] = False
        
        # Step 2.5: Heuristic AI detection for impossible animal behaviors
        # This catches AI content even when comments don't flag it
        if not is_trusted_channel and video_title:
            heuristic_ai = self._detect_impossible_content(
                title=video_title,
                description=video_description,
                channel=channel_name,
                tags=video_tags
            )
            if heuristic_ai:
                comment_analysis["has_ai_content"] = True
                comment_analysis["warnings"].insert(0, {
                    "category": "AI Content",
                    "severity": "high",
                    "message": f"🤖 {heuristic_ai}",
                    "timestamp": None
                })
                # Penalize score for AI content
                comment_analysis["warning_score"] = min(comment_analysis.get("warning_score", BASE_SCORE), AI_CONTENT_MAX_SCORE)
                logger.info(f"🤖 Heuristic AI detection triggered: {heuristic_ai}")
        
        # Step 2.6: Detect dangerous animal + child/baby situations
        if video_title:
            dangerous_animal_child = self._detect_dangerous_animal_child(
                title=video_title,
                description=video_description,
                tags=video_tags
            )
            if dangerous_animal_child:
                comment_analysis["warnings"].insert(0, {
                    "category": "Child Safety",
                    "severity": "critical",
                    "message": dangerous_animal_child,
                    "timestamp": None
                })
                # Penalize score for dangerous content
                comment_analysis["warning_score"] = min(comment_analysis.get("warning_score", BASE_SCORE), DANGEROUS_ANIMAL_MAX_SCORE)
                logger.warning(f"⚠️ Dangerous animal/child situation detected: {dangerous_animal_child}")
        
        # Step 2.7: Title/description red flag detection
        # Catches dangerous content (medical misinfo, chemical mixing, DIY weapons, etc.)
        # from metadata alone — critical when transcript is unavailable
        title_red_flags = []
        if not is_trusted_channel and video_title:
            title_red_flags = self._detect_title_red_flags(
                title=video_title,
                description=video_description,
                tags=video_tags
            )
            if title_red_flags:
                # Add red flag warnings
                for flag in title_red_flags:
                    comment_analysis["warnings"].insert(0, flag)
                
                # Penalize score based on severity of flags
                max_severity = max(
                    (f.get("severity", "low") for f in title_red_flags),
                    key=lambda s: {"critical": 3, "high": 2, "medium": 1, "low": 0}.get(s, 0)
                )
                if max_severity in ("high", "critical"):
                    comment_analysis["warning_score"] = min(
                        comment_analysis.get("warning_score", BASE_SCORE), 30
                    )
                elif max_severity == "medium":
                    comment_analysis["warning_score"] = min(
                        comment_analysis.get("warning_score", BASE_SCORE), 55
                    )
                logger.info(f"🚩 {len(title_red_flags)} title red flag(s) detected, max severity: {max_severity}")
        
        # Step 3: Match against danger signatures (transcript + comment text + METADATA)
        # CRITICAL FIX: Include title/description in signature matching text.
        # Previously only transcript was checked, so videos whose transcript
        # couldn't be extracted (very common) would ALWAYS get a safe score
        # even if the title screamed "bleach cure" or "mix ammonia and bleach".
        metadata_text = f"{video_title} {video_description}".lower()
        all_text = transcript_text
        if comment_analysis.get("top_concerns"):
            # Add comment concerns to analysis text
            concern_text = " ".join([c["concern"] for c in comment_analysis["top_concerns"]])
            all_text += " " + concern_text
        
        # Run signature matching on BOTH transcript+comments AND metadata
        signature_matches = self._match_signatures(all_text)
        
        # Also match signatures against title/description (catches issues even without transcript)
        if metadata_text.strip():
            metadata_sig_matches = self._match_signatures(metadata_text)
            # Avoid duplicates — only add matches not already found
            existing_ids = {m['signature'].get('id') for m in signature_matches}
            for m in metadata_sig_matches:
                if m['signature'].get('id') not in existing_ids:
                    m['match_type'] = 'metadata_trigger'  # Mark as metadata-sourced
                    signature_matches.append(m)
                    existing_ids.add(m['signature'].get('id'))
                    logger.info(f"🔍 Signature matched from title/description: {m['signature'].get('id')} - {m['matched_trigger']}")
        
        # Step 3.5: Match metadata-format signatures (title/description/channel patterns)
        # These catch occult manipulation, spiritual extremism, pseudohistory, pop-culture subversion
        metadata_matches = self._match_metadata_signatures(
            title=video_title,
            description=video_description,
            channel=channel_name,
            transcript=transcript_text
        )
        
        # Step 3.6: AI Context Review — verify metadata matches aren't false positives
        # When metadata signatures fire, the AI reviewer checks if the video is
        # PROMOTING the flagged content or DEBUNKING/educating about it.
        # This eliminates false positives like "Tartaria Debunked" being flagged as extremism.
        ai_review_results = {}
        is_debunking = False
        if metadata_matches and self.ai_reviewer:
            verified_matches = []
            for match in metadata_matches:
                cat = match['signature'].get('category', '')
                cat_desc = match['signature'].get('description', '')
                
                review = await self.ai_reviewer.review_flagged_content(
                    title=video_title,
                    description=video_description,
                    channel=channel_name,
                    transcript=transcript_text,
                    category=cat,
                    category_description=cat_desc,
                )
                ai_review_results[cat] = review
                
                if review.get("should_suppress"):
                    # This match is debunking/educational — suppress it
                    is_debunking = True
                    logger.info(f"🧠 AI suppressed {cat}: verdict={review.get('verdict')}, "
                               f"confidence={review.get('confidence')}, "
                               f"method={review.get('method')}")
                else:
                    # Confirmed as promoting — keep the match
                    verified_matches.append(match)
                    logger.info(f"🧠 AI confirmed {cat}: promoting (confidence={review.get('confidence')})")
            
            metadata_matches = verified_matches
        elif metadata_matches and not self.ai_reviewer:
            # No AI reviewer — use basic heuristic inline
            from ai_reviewer import AIContextReviewer
            _fallback = AIContextReviewer()  # Heuristic-only instance
            verified_matches = []
            for match in metadata_matches:
                cat = match['signature'].get('category', '')
                heuristic = _fallback.heuristic_is_debunking(
                    title=video_title,
                    description=video_description,
                    transcript=transcript_text,
                )
                if heuristic["is_debunking"] and heuristic["confidence"] >= 0.3:
                    is_debunking = True
                    logger.info(f"🔍 Heuristic suppressed {cat}: {'; '.join(heuristic['signals'][:2])}")
                else:
                    verified_matches.append(match)
            metadata_matches = verified_matches
        
        if metadata_matches:
            signature_matches.extend(metadata_matches)
            logger.info(f"🔍 Metadata signature matches (post-review): {len(metadata_matches)}")
        
        # Step 3.7: Deep AI transcript analysis (catches contextual dangers patterns miss)
        # Only runs when AI is available and transcript exists
        ai_transcript_concerns = []
        if self.ai_reviewer and self.ai_reviewer.is_ai_enabled and transcript_text and not is_trusted_channel:
            deep_analysis = await self.ai_reviewer.analyze_transcript_safety(
                title=video_title,
                description=video_description,
                channel=channel_name,
                transcript=transcript_text,
            )
            if deep_analysis.get("concerns"):
                ai_transcript_concerns = deep_analysis["concerns"]
                logger.info(f"🧠 Deep analysis found {len(ai_transcript_concerns)} concerns")
                
                # Convert AI concerns into warnings
                for concern in ai_transcript_concerns:
                    severity = concern.get("severity", "medium")
                    category = concern.get("category", "safety_concern").replace("_", " ").title()
                    description_text = concern.get("description", "AI-detected safety concern")
                    
                    comment_analysis["warnings"].append({
                        "category": f"AI Analysis: {category}",
                        "severity": severity,
                        "message": f"🧠 {description_text}",
                        "timestamp": concern.get("timestamp_hint"),
                    })
                
                # Adjust score based on AI risk assessment
                ai_risk = deep_analysis.get("overall_risk", "low")
                if ai_risk == "high":
                    comment_analysis["warning_score"] = min(
                        comment_analysis.get("warning_score", BASE_SCORE), 25
                    )
                elif ai_risk == "medium":
                    comment_analysis["warning_score"] = min(
                        comment_analysis.get("warning_score", BASE_SCORE), 55
                    )
        
        # Step 4: Analyze each category
        category_results = self._analyze_categories(all_text, signature_matches)
        
        # Step 5: Generate warnings from matches + comment warnings + title red flags
        warnings = self._generate_warnings(signature_matches)
        
        # Add title red flag warnings (highest priority, goes first)
        # Deduplicate: don't add a title red flag if a signature already covers the same category+severity
        if title_red_flags:
            existing_keys = {(w.get("category",""), w.get("severity","")) for w in warnings}
            deduped_flags = [f for f in title_red_flags if (f.get("category",""), f.get("severity","")) not in existing_keys]
            # Put title red flags first, then signature warnings
            warnings = deduped_flags + warnings
        
        # Add top comment warnings
        for cw in comment_analysis.get("warnings", [])[:5]:
            warnings.append(cw)
        
        # Step 6: Calculate overall safety score (combining transcript + comments)
        transcript_score = self._calculate_safety_score(signature_matches, category_results)
        comment_score = comment_analysis.get("warning_score", BASE_SCORE)

        # Weight: transcript analysis vs community feedback
        if transcript_available:
            safety_score = int(transcript_score * TRANSCRIPT_WEIGHT + comment_score * COMMENT_WEIGHT)
        else:
            # If no transcript, rely more on comments
            safety_score = int(transcript_score * NO_TRANSCRIPT_WEIGHT + comment_score * NO_TRANSCRIPT_COMMENT_WEIGHT)
        
        # Step 6.1: Uncertainty penalty — when we have NEITHER transcript NOR comments,
        # the score should reflect uncertainty rather than defaulting to "safe".
        # Previously this would produce score ~98 for ANY video that lacks transcript/comments,
        # even if the title contains blatant misinformation.
        has_comments = comment_analysis.get("total_comments", 0) > 0
        if not transcript_available and not has_comments:
            # Cap at 72 — "unable to fully verify, watch with caution"
            UNCERTAINTY_CAP = 72
            if safety_score > UNCERTAINTY_CAP and not is_trusted_channel:
                logger.info(f"📉 No transcript + no comments = uncertain. Capping score from {safety_score} to {UNCERTAINTY_CAP}")
                safety_score = UNCERTAINTY_CAP
        
        # Step 6.5: If metadata signatures fired, enforce score ceiling
        # Metadata matches are high-confidence (title/channel/pattern-based) and should
        # override the weighted score which can be diluted by missing transcript/comments
        if metadata_matches:
            max_metadata_weight = max(m.get('match_weight', 0) for m in metadata_matches)
            max_severity = max(
                (m['signature'].get('severity', 'low') for m in metadata_matches),
                key=lambda s: {'high': 2, 'medium': 1, 'low': 0}.get(s, 0)
            )
            # High severity metadata matches cap the score aggressively
            if max_severity == 'high':
                metadata_cap = max(10, 45 - (max_metadata_weight * 3))
            elif max_severity == 'medium':
                metadata_cap = 65
            else:
                metadata_cap = 80
            
            if safety_score > metadata_cap:
                logger.info(f"📉 Metadata matches capping score from {safety_score} to {metadata_cap}")
                safety_score = metadata_cap
        
        # Step 7: Generate summary
        summary = self._generate_summary(
            signature_matches, 
            category_results, 
            transcript_available,
            comment_analysis,
            title_red_flags=title_red_flags
        )
        
        # Step 8: Extract AI detection info
        ai_generated = comment_analysis.get("has_ai_content", False)
        ai_warnings = [w for w in warnings if w.get("category") == "AI Content"]
        ai_reasons = [w.get("message", "") for w in ai_warnings]
        # Confidence heuristic: 1 AI signal = 60%, 2+ = 85%
        ai_confidence = 0.0
        if ai_generated:
            ai_confidence = 0.85 if len(ai_warnings) >= 2 else 0.60

        # Step 8.5: Collect debunk search queries from matched metadata signatures
        debunk_searches = []
        matched_metadata_category_ids = []
        if metadata_matches:
            for m in metadata_matches:
                cat_id = m['signature'].get('category', '')
                if cat_id:
                    matched_metadata_category_ids.append(cat_id)
            # Pull debunk_searches from the original signature data
            for signature in self.signatures:
                if signature.get('category') in matched_metadata_category_ids:
                    debunk_searches.extend(signature.get('debunk_searches', []))

        return {
            "video_id": video_id,
            "safety_score": safety_score,
            "warnings": warnings,
            "categories": category_results,
            "summary": summary,
            "transcript_available": transcript_available,
            "ai_generated": ai_generated,
            "ai_confidence": ai_confidence,
            "ai_reasons": ai_reasons,
            "comments_analyzed": comment_analysis.get("total_comments", 0),
            "comment_warnings": comment_analysis.get("warning_comments", 0),
            "channel": channel_name,
            "is_trusted_channel": is_trusted_channel,
            "video_title": video_title,
            "debunk_searches": debunk_searches,
            "matched_metadata_categories": matched_metadata_category_ids,
            "is_debunking": is_debunking,
            "ai_review": ai_review_results,
            "ai_transcript_concerns": ai_transcript_concerns,
        }
    
    async def _analyze_comments(self, video_id: str) -> dict:
        """Fetch and analyze YouTube comments for community warnings"""
        try:
            async with YouTubeDataFetcher(api_key=self.youtube_api_key) as fetcher:
                comments = await fetcher.get_comments(video_id, max_results=MAX_COMMENTS_TO_FETCH)

            if comments:
                return analyze_comments(comments)
            else:
                return {"total_comments": 0, "warning_comments": 0, "warnings": [], "warning_score": 100}
        except Exception as e:
            logger.error(f"Comment analysis failed: {e}")
            return {"total_comments": 0, "warning_comments": 0, "warnings": [], "warning_score": 100}

    async def _get_transcript(self, video_id: str) -> tuple[str, bool]:
        """Extract transcript from YouTube video"""
        try:
            # Run in thread pool since youtube_transcript_api is blocking
            loop = asyncio.get_event_loop()
            
            def fetch_transcript():
                ytt_api = YouTubeTranscriptApi()
                transcript = ytt_api.fetch(video_id)
                return transcript
            
            transcript_list = await loop.run_in_executor(None, fetch_transcript)
            
            # Combine all transcript segments
            full_text = " ".join([segment.text for segment in transcript_list])
            return full_text.lower(), True
            
        except Exception as e:
            logger.warning(f"Transcript extraction failed: {e}")
            # Return empty string but continue analysis with metadata
            return "", False
    
    def _match_signatures(self, text: str) -> list[dict]:
        """
        Match text against danger signatures.
        Similar to antivirus signature matching.
        """
        matches = []

        # Truncate text to prevent ReDoS (bound regex backtracking)
        text = text[:MAX_SIGNATURE_TEXT_LENGTH]
        
        for signature in self.signatures:
            # Skip metadata-format signatures (handled by _match_metadata_signatures)
            if 'title_patterns' in signature or 'description_patterns' in signature:
                continue
            
            # Handle new format: signature files with 'danger_signatures' array
            if 'danger_signatures' in signature:
                category = signature.get('category', 'Unknown')
                for danger_sig in signature.get('danger_signatures', []):
                    pattern = danger_sig.get('pattern', '')
                    if pattern and re.search(pattern, text, re.IGNORECASE):
                        matches.append({
                            'signature': {
                                'id': danger_sig.get('id', 'unknown'),
                                'category': category,
                                'severity': danger_sig.get('severity', 'medium'),
                                'warning_message': danger_sig.get('message', ''),
                                'source': danger_sig.get('osha_standard') or danger_sig.get('law') or danger_sig.get('source', '')
                            },
                            'matched_trigger': pattern,
                            'match_type': 'regex'
                        })
            else:
                # Handle old format with 'triggers' array
                for trigger in signature.get('triggers', []):
                    # Support regex patterns
                    if signature.get('is_regex', False):
                        if re.search(trigger, text, re.IGNORECASE):
                            matches.append({
                                'signature': signature,
                                'matched_trigger': trigger,
                                'match_type': 'regex'
                            })
                            break
                    else:
                        if trigger.lower() in text:
                            matches.append({
                                'signature': signature,
                                'matched_trigger': trigger,
                                'match_type': 'phrase'
                            })
                            break
                
                # Check exclusion phrases (reduces false positives)
                # If a trigger matched this signature (it would be the last item), check exclusions
                matched_this_sig = (
                    matches
                    and matches[-1]['signature'] is signature
                )
                if matched_this_sig:
                    for exclusion in signature.get('exclusions', []):
                        if exclusion.lower() in text:
                            matches.pop()
                            break
        
        return matches
    
    def _match_metadata_signatures(self, title: str, description: str, channel: str, transcript: str = "") -> list[dict]:
        """
        Match video metadata (title, description, channel) against the new-format
        signatures that use title_patterns, description_patterns, co_occurrence_signals,
        and channel_signals.
        
        These signatures detect content like occult manipulation, spiritual extremism,
        pseudohistorical extremism, and pop-culture subversion pipelines.
        """
        matches = []
        
        # Truncate inputs to prevent ReDoS
        title = (title or "")[:MAX_TITLE_LENGTH].lower()
        description = (description or "")[:MAX_DESCRIPTION_LENGTH].lower()
        channel = (channel or "")[:MAX_CHANNEL_LENGTH]
        transcript = (transcript or "")[:MAX_SIGNATURE_TEXT_LENGTH].lower()
        
        # Combined text for co-occurrence checking
        all_text = f"{title} {description} {transcript}".lower()
        
        for signature in self.signatures:
            # Only process metadata-format signatures
            if 'title_patterns' not in signature and 'description_patterns' not in signature:
                continue
            
            category = signature.get('category', 'unknown')
            severity = signature.get('severity', 'high')
            display_name = signature.get('display_name', category.replace('_', ' ').title())
            sig_description = signature.get('description', '')
            
            matched_reasons = []
            match_weight = 0  # Track how strong the match is
            
            # 1. Check title patterns (regex)
            for pattern in signature.get('title_patterns', []):
                try:
                    if re.search(pattern, title, re.IGNORECASE):
                        matched_reasons.append(f"Title matches pattern: {pattern}")
                        match_weight += 3  # Title match = strong signal
                        break  # One title match is enough
                except re.error:
                    logger.warning(f"Invalid regex in title_patterns: {pattern}")
            
            # 2. Check description patterns (substring/regex)
            for pattern in signature.get('description_patterns', []):
                try:
                    if re.search(re.escape(pattern) if not any(c in pattern for c in r'.*+?[](){}|\\^$') else pattern, 
                                 description, re.IGNORECASE):
                        matched_reasons.append(f"Description matches: {pattern}")
                        match_weight += 2
                        break  # One description match is enough
                except re.error:
                    # Fall back to substring match
                    if pattern.lower() in description:
                        matched_reasons.append(f"Description contains: {pattern}")
                        match_weight += 2
                        break
            
            # 3. Check co-occurrence signals
            co_occurrence = signature.get('co_occurrence_signals', {})
            if co_occurrence:
                # Find all term groups (genre_terms+harm_terms, wrapper_terms+payload_terms, etc.)
                term_groups = {}
                for key, value in co_occurrence.items():
                    if isinstance(value, list) and key != 'evasion_tactics':
                        term_groups[key] = value
                
                # Check if terms from at least 2 different groups co-occur
                groups_with_hits = {}
                for group_name, terms in term_groups.items():
                    hits = [t for t in terms if t.lower() in all_text]
                    if hits:
                        groups_with_hits[group_name] = hits
                
                if len(groups_with_hits) >= 2:
                    # Co-occurrence detected across multiple signal groups
                    group_summary = "; ".join(
                        f"{name}: {', '.join(hits[:2])}" 
                        for name, hits in list(groups_with_hits.items())[:3]
                    )
                    matched_reasons.append(f"Co-occurrence signals: {group_summary}")
                    match_weight += 4  # Co-occurrence = very strong signal
            
            # 4. Check channel signals (known bad channels)
            channel_signals = signature.get('channel_signals', {})
            known_bad = channel_signals.get('known_bad_channels', [])
            if channel and known_bad:
                channel_lower = channel.lower().strip()
                for bad_channel in known_bad:
                    if bad_channel.lower().strip() == channel_lower:
                        matched_reasons.append(f"Known problematic channel: {bad_channel}")
                        match_weight += 5  # Known bad channel = strongest signal
                        break
            
            # 5. Check known bad hashtags
            known_bad_hashtags = channel_signals.get('known_bad_hashtags', [])
            if known_bad_hashtags:
                for hashtag in known_bad_hashtags:
                    if hashtag.lower() in all_text:
                        matched_reasons.append(f"Known problematic hashtag: {hashtag}")
                        match_weight += 3
                        break
            
            # 6. Non-Latin script detection
            # If a signature has non_latin_script_flag enabled, check if the title/description
            # contain substantial non-Latin text. This catches non-English content from
            # unknown channels that would otherwise evade all English-only patterns.
            non_latin_flag = signature.get('non_latin_script_flag', {}) or signature.get('language_evasion_flag', {})
            if non_latin_flag.get('enabled', False) and match_weight < 2:
                # Count non-Latin characters (Cyrillic, Arabic, CJK, etc.)
                combined = f"{title} {description}"
                non_latin_chars = sum(1 for c in combined if c.isalpha() and not c.isascii())
                total_alpha = sum(1 for c in combined if c.isalpha())
                if total_alpha > 0 and non_latin_chars / total_alpha > 0.5:
                    # More than half the letters are non-Latin.
                    # Check for zodiac emoji (♈-♓) — strong signal for occult content
                    zodiac_emojis = ['♈', '♉', '♊', '♋', '♌', '♍', '♎', '♏', '♐', '♑', '♒', '♓']
                    has_zodiac_emoji = any(e in combined for e in zodiac_emojis)
                    
                    # Build transliterated hints from the signature's own co_occurrence terms
                    # plus a static set of known cross-script survivors
                    static_hints = [
                        # Occult/astrology
                        'tarot', 'taro', 'zodiac', 'horoscope', 'astro',
                        'тар', 'зодиак', 'гороскоп', 'астро', 'таро',
                        # Pseudohistory
                        'tartaria', 'тартар', 'hyperborea', 'гиперборе',
                        'mud flood', 'antiquitech',
                        # Spiritual/wellness extremism
                        'pineal', 'пинеал', 'third eye', 'fluoride', 'chemtrail',
                        # Pop-culture subversion / RAC
                        'rac ', 'conan', 'fashwave', 'codreanu',
                        # General extremism
                        'nwo', 'cabal', 'каббал', 'zionist', 'сионист',
                    ]
                    # Also dynamically extract short co-occurrence terms from the signature
                    dynamic_hints = []
                    for key, value in co_occurrence.items():
                        if isinstance(value, list):
                            for term in value:
                                t = term.lower().strip()
                                # Only use distinctive terms (≥ 5 chars to avoid noise)
                                if len(t) >= 5 and t not in ('note',):
                                    dynamic_hints.append(t)
                    
                    all_hints = static_hints + dynamic_hints
                    has_transliterated = any(hint in combined for hint in all_hints)
                    
                    if has_zodiac_emoji or has_transliterated:
                        matched_reasons.append(f"Non-Latin content with category-relevant signals detected")
                        match_weight += 3  # Strong signal
                        logger.info(f"🌐 Non-Latin script detected for {category} "
                                    f"(emoji={has_zodiac_emoji}, transliterated={has_transliterated})")

            # Generate match if we have enough signal strength
            # Require at least weight 2 (one description match) to avoid false positives
            if match_weight >= 2:
                # Use the full signature description as the warning message
                # This gives users a clear explanation of WHY the content is flagged
                warning_msg = sig_description or f"Content flagged for {display_name}"
                
                # Build evidence items showing EXACTLY what was found
                evidence_items = []
                for reason in matched_reasons:
                    if reason.startswith("Title matches pattern:"):
                        evidence_items.append({
                            'type': 'title',
                            'label': 'Title keyword detected',
                            'value': title[:80]
                        })
                    elif reason.startswith("Description matches:"):
                        matched_term = reason.split("Description matches: ", 1)[-1]
                        evidence_items.append({
                            'type': 'description',
                            'label': 'Description contains',
                            'value': matched_term
                        })
                    elif reason.startswith("Description contains:"):
                        matched_term = reason.split("Description contains: ", 1)[-1]
                        evidence_items.append({
                            'type': 'description',
                            'label': 'Description contains',
                            'value': matched_term
                        })
                    elif reason.startswith("Co-occurrence signals:"):
                        raw = reason.split("Co-occurrence signals: ", 1)[-1]
                        evidence_items.append({
                            'type': 'co_occurrence',
                            'label': 'Multiple harm signals co-occur',
                            'value': raw
                        })
                    elif reason.startswith("Known problematic channel:"):
                        ch_name = reason.split("Known problematic channel: ", 1)[-1]
                        evidence_items.append({
                            'type': 'channel',
                            'label': 'Flagged channel',
                            'value': ch_name
                        })
                    elif reason.startswith("Known problematic hashtag:"):
                        ht = reason.split("Known problematic hashtag: ", 1)[-1]
                        evidence_items.append({
                            'type': 'hashtag',
                            'label': 'Flagged hashtag',
                            'value': ht
                        })
                    else:
                        evidence_items.append({
                            'type': 'other',
                            'label': 'Signal',
                            'value': reason
                        })
                
                matches.append({
                    'signature': {
                        'id': f"metadata_{category}",
                        'category': category,
                        'severity': severity,
                        'warning_message': warning_msg,
                        'description': sig_description,
                        'evidence': evidence_items,
                        'source': ', '.join(signature.get('references', []))
                    },
                    'matched_trigger': '; '.join(matched_reasons[:3]),
                    'match_type': 'metadata',
                    'match_weight': match_weight,
                    'all_reasons': matched_reasons
                })
                
                logger.warning(f"🚨 Metadata signature match: {category} (weight={match_weight}) - {'; '.join(matched_reasons[:2])}")
        
        return matches
    
    def _analyze_categories(self, text: str, matches: list[dict]) -> dict:
        """Analyze text for each safety category"""
        categories = self.safety_db.get_categories()
        results = {}
        
        for cat_id, category in categories.items():
            # Count matches in this category
            cat_matches = [m for m in matches if m['signature'].get('category') == cat_id]
            
            # Calculate category score (100 = safe, 0 = dangerous)
            if cat_matches:
                # More matches = lower score
                total_penalty = sum(
                    CATEGORY_SEVERITY_WEIGHTS.get(m['signature'].get('severity', 'low'), 5)
                    for m in cat_matches
                )
                score = max(0, BASE_SCORE - total_penalty)
            else:
                score = 100
            
            results[category['name']] = {
                'emoji': category['emoji'],
                'flagged': len(cat_matches) > 0,
                'score': score
            }
        
        return results
    
    def _generate_warnings(self, matches: list[dict]) -> list[dict]:
        """Convert signature matches to user-friendly warnings"""
        warnings = []
        
        # Sort by severity
        severity_order = {'high': 0, 'medium': 1, 'low': 2}
        sorted_matches = sorted(
            matches,
            key=lambda m: severity_order.get(m['signature'].get('severity', 'low'), 2)
        )
        
        for match in sorted_matches:
            sig = match['signature']
            warning_entry = {
                'category': self.safety_db.get_category_name(sig.get('category', 'general')),
                'severity': sig.get('severity', 'low'),
                'message': sig.get('warning_message', sig.get('description', 'Potential safety concern detected')),
                'safe_alternative': sig.get('safe_alternative'),
                'source': sig.get('source')
            }
            # Include structured evidence from metadata matches for richer UI
            if sig.get('evidence'):
                warning_entry['evidence'] = sig['evidence']
            warnings.append(warning_entry)
        
        return warnings
    
    def _calculate_safety_score(self, matches: list[dict], categories: dict) -> int:
        """
        Calculate overall safety score (0-100).
        
        Factors:
        - Number and severity of matched signatures
        - Category scores
        """
        if not matches:
            return DEFAULT_SAFE_SCORE

        # Base score
        base_score = BASE_SCORE

        # Penalty for each match based on severity
        for match in matches:
            severity = match['signature'].get('severity', 'low')
            base_score -= OVERALL_SEVERITY_PENALTIES.get(severity, 5)

        # Average with category scores
        if categories:
            category_avg = sum(c['score'] for c in categories.values()) / len(categories)
            final_score = (base_score * BASE_SCORE_WEIGHT) + (category_avg * CATEGORY_SCORE_WEIGHT)
        else:
            final_score = base_score

        return max(0, min(BASE_SCORE, int(final_score)))
    
    def _generate_summary(self, matches: list[dict], categories: dict, has_transcript: bool, comment_analysis: dict | None = None, title_red_flags: list[dict] | None = None) -> str:
        """Generate a human-readable summary of the analysis"""
        
        parts = []
        
        # Title red flag status (most important — comes first)
        if title_red_flags:
            parts.append(f"🚩 {len(title_red_flags)} concern(s) detected from video title/description!")
        
        # Transcript status
        if not has_transcript:
            parts.append("⚠️ Could not extract video transcript.")
        
        # Comment analysis status
        if comment_analysis:
            total_comments = comment_analysis.get("total_comments", 0)
            warning_comments = comment_analysis.get("warning_comments", 0)
            
            if total_comments > 0:
                if warning_comments > 0:
                    ratio = warning_comments / total_comments * 100
                    parts.append(f"👥 Community feedback: {warning_comments}/{total_comments} comments ({ratio:.0f}%) contain safety warnings!")
                    
                    # Add top concerns from comments
                    top_concerns = comment_analysis.get("top_concerns", [])
                    if top_concerns:
                        concern_list = ", ".join([c["concern"] for c in top_concerns[:3]])
                        parts.append(f"Top concerns: {concern_list}")
                else:
                    parts.append(f"👥 Analyzed {total_comments} comments - no safety warnings found.")
            else:
                parts.append("👥 No comments available for community feedback analysis.")
        
        # Signature matches
        if matches:
            high_count = len([m for m in matches if m['signature'].get('severity') == 'high'])
            medium_count = len([m for m in matches if m['signature'].get('severity') == 'medium'])
            low_count = len([m for m in matches if m['signature'].get('severity') == 'low'])
            
            if high_count > 0:
                parts.append(f"🚨 {high_count} HIGH severity concern(s) detected")
            if medium_count > 0:
                parts.append(f"⚠️ {medium_count} MEDIUM severity concern(s) detected")
            if low_count > 0:
                parts.append(f"ℹ️ {low_count} LOW severity concern(s) detected")
            
            flagged_cats = [name for name, data in categories.items() if data['flagged']]
            if flagged_cats:
                parts.append(f"Categories with issues: {', '.join(flagged_cats)}")
        
        # Final recommendation
        if not matches and (not comment_analysis or comment_analysis.get("warning_comments", 0) == 0):
            if has_transcript:
                parts.append("✅ No safety concerns detected based on available data.")
            else:
                parts.append("Consider watching with caution as analysis is limited.")
        else:
            parts.append("Please review the warnings and verify information with trusted sources before following any advice.")
        
        return " ".join(parts)


# Legacy AIAnalyzer removed — replaced by ai_reviewer.AIContextReviewer
# See ai_reviewer.py for the full AI-powered context review system.
