"""
Safety Analyzer - Core analysis engine
Combines transcript extraction, signature matching, comment analysis, and AI analysis
"""

import re
import asyncio
import os
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi
from safety_db import SafetyDatabase
from youtube_data import YouTubeDataFetcher, analyze_comments

# Optional: For AI-powered analysis (uncomment if using OpenAI)
# import openai


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
    
    def __init__(self, safety_db: SafetyDatabase, youtube_api_key: Optional[str] = None):
        self.safety_db = safety_db
        self.signatures = safety_db.get_all_signatures()
        # Get API key from param, env, or None
        self.youtube_api_key = youtube_api_key or os.environ.get("YOUTUBE_API_KEY")
        
        # Suspicious channel name patterns (channels that typically post AI content)
        self._suspicious_channel_patterns = [
            r"talk\s*(with|to|ing)?\s*(rico|pet|animal|bird|parrot|cat|dog)",
            r"(pet|animal|bird|parrot|cat|dog)\s*talk",
            r"(funny|cute)\s*(pet|animal|bird|parrot|cat|dog)\s*video",
            r"ai\s*(pet|animal|content|video|generated)",
        ]
        
        # Hashtag patterns that suggest AI-generated animal content
        self._ai_hashtag_patterns = [
            r"#talkingbird",
            r"#talkingparrot",
            r"#talkingcat",
            r"#talkingdog",
            r"#talkinganimal",
            r"#funnybirds",
            r"#funnypetvideos",
            r"#parrottalking",
            r"#birdtalking",
            r"#cattalking",
            r"#dogtalking",
            r"#aianimals",
            r"#aigenerated",
            r"#aiart",
            r"#aivideo",
        ]
        
        # Heuristic patterns for impossible/AI content
        # Animals that appear to talk, have conversations, or do impossible things
        self._impossible_patterns = [
            # TWO animals having a conversation (dead giveaway for AI)
            (r"\b(two|2|both|pair)\b.{0,20}\b(parrot|bird|cat|dog|animal)s?\b.{0,30}\b(talk|convers|chat|argue|discuss|debate)", 
             "Two animals having a conversation (AI content)"),
            (r"\b(parrot|bird|cat|dog)s?\b.{0,20}\b(talk|convers|chat|argue)\b.{0,20}\b(each other|together|to one another)",
             "Animals conversing with each other (AI content)"),
            # Parrot/bird specific conversations
            (r"\b(parrot|parakeet|cockatoo|budgie|macaw)s?\b.{0,30}\b(conversation|talking to|chatting with|argues with|debates)",
             "Parrots having human-like conversation (likely AI)"),
            (r"\b(parrot|bird)s?\b.{0,15}\b(having a|in a|long|full|real|actual)\b.{0,10}\b(conversation|discussion|debate|argument)",
             "Animals having extended conversation (AI content)"),
            # Generic talking animals - conversation keywords
            (r"\b(parrot|bird|cat|dog|monkey|ape|gorilla|chimp|elephant|lion|tiger|bear|fox|raccoon|squirrel|rabbit|hamster|horse|cow|pig|chicken|duck|goose|owl|crow|raven|fish|shark|whale|dolphin|seal|penguin|frog|turtle|snake|lizard|gecko|iguana|crocodile|alligator)\b.{0,40}\b(talk|talking|speaks|speaking|says|said|conversation|chat|chatting|argue|arguing|debate|interview|podcast|call|phone|answer|respond|tells|told|ask|asking|wants|demanded|yells|screaming|complain|rant|confess|admit|explain|announce|declare|insist|refuse|agree|disagree)\b", 
             "Animal appearing to communicate like a human"),
            (r"\b(talk|talking|speaks|speaking|says|said|conversation|chat|chatting|argue|arguing|debate|interview|podcast|call|phone|answer|respond|tells|told|ask|asking|wants|demanded|yells|screaming|complain|rant|confess|admit|explain|announce|declare|insist|refuse|agree|disagree)\b.{0,40}\b(parrot|bird|cat|dog|monkey|ape|gorilla|chimp|elephant|lion|tiger|bear|fox|raccoon|squirrel|rabbit|hamster|horse|cow|pig|chicken|duck|goose|owl|crow|raven|fish|shark|whale|dolphin|seal|penguin|frog|turtle|snake|lizard|gecko|iguana|crocodile|alligator)\b",
             "Animal appearing to communicate like a human"),
            # Animals wanting/demanding things (AI trope)
            (r"\b(parrot|bird|cat|dog|monkey|gorilla|raccoon|fox|bear|elephant|lion|tiger)\b.{0,20}\b(wants|needs|demands|orders|requests|insists|refuses|complains)\b.{0,20}\b(fbi|police|911|lawyer|manager|refund|divorce|custody|money|revenge)\b",
             "Animal demanding human services (common AI trope)"),
            # Animals doing impossible human activities
            (r"\b(cat|dog|bird|parrot|monkey|bear|lion|tiger|elephant|gorilla|raccoon|fox|squirrel|rabbit|fish|penguin|owl)\b.{0,30}\b(drive|driving|drove|cook|cooking|cooked|play piano|playing piano|type|typing|typed|text|texting|texted|email|emailing|read|reading|write|writing|wrote|paint|painting|painted|sing|singing|sang|dance|dancing|danced|ballet|opera|graduate|graduating|married|wedding|divorce|court|sue|lawsuit)\b",
             "Animal performing impossible human activity"),
            # Animals with jobs/professions
            (r"\b(cat|dog|bird|parrot|raccoon|monkey|bear)\b.{0,20}\b(lawyer|doctor|chef|pilot|driver|ceo|manager|employee|boss|judge|cop|officer|agent|detective)\b",
             "Animal with human profession (likely AI)"),
            # Impossible animal interactions
            (r"\b(cat|dog|bird|mouse|rabbit|hamster|fish|parrot)\b.{0,30}\b(save|saves|saved|rescue|rescues|rescued|hero|call 911|calls 911|called 911|call police|calls police|ambulance|fire department)\b",
             "Animal performing heroic human actions"),
            # Viral AI tropes
            (r"\b(animal|cat|dog|bird|parrot).{0,20}(facetime|video call|zoom|teams call|skype)\b",
             "Animal on video call (common AI trope)"),
            (r"\b(cat|dog|parrot|bird).{0,20}(order|ordering|ordered|uber|doordash|pizza|food delivery|amazon|online shopping)\b",
             "Animal ordering services (common AI trope)"),
            # Animals in legal/dramatic situations
            (r"\b(cat|dog|parrot|bird|raccoon|monkey).{0,30}(court|trial|testif|lawyer|sue|custody|arrested|jail|prison|fbi|cia|police|detective|investigate)\b",
             "Animal in legal/dramatic situation (likely AI)"),
            # Animals with human emotions/drama
            (r"\b(cat|dog|parrot|bird|raccoon).{0,20}(breakup|broke up|cheating|cheated|divorce|married|wedding|pregnant|baby daddy|custody battle)\b",
             "Animal in human relationship drama (likely AI)"),
        ]
        
        # SAFETY patterns - dangerous animals near children/babies
        self._dangerous_animal_child_patterns = [
            # Large birds with babies/children (parrots, cockatoos have powerful beaks)
            # Pattern: bird near baby OR baby near bird (either order)
            (r"\b(parrot|cockatoo|macaw|cockatiel|conure|african grey|amazon parrot|eclectus|bird)\b.{0,50}\b(baby|infant|newborn|toddler|child|kid|sleeping|nap|crib|bed)\b",
             "⚠️ SAFETY: Large parrot/bird near baby/child - parrots have powerful beaks (300+ PSI) that can cause serious injury"),
            (r"\b(baby|infant|newborn|toddler|child|kid|sleeping)\b.{0,50}\b(parrot|cockatoo|macaw|cockatiel|conure|african grey|bird)\b",
             "⚠️ SAFETY: Baby/child near large bird - birds can bite unpredictably and cause serious injury"),
            # Flexible pattern: any mention of baby AND parrot/cockatoo in same title
            (r"(?=.*\b(baby|infant|newborn|toddler)\b)(?=.*\b(parrot|cockatoo|macaw|bird)\b)",
             "⚠️ SAFETY: Video shows baby with parrot/bird - large birds have dangerous beaks and can injure infants"),
            # Dogs with babies unsupervised
            (r"\b(pit ?bull|rottweiler|german shepherd|doberman|husky|malamute|akita|chow|mastiff|great dane|wolf ?dog)\b.{0,50}\b(baby|infant|newborn|toddler|sleep|alone|unsupervised)\b",
             "⚠️ SAFETY: Large/powerful dog near unsupervised baby - never leave children unattended with dogs"),
            (r"\b(baby|infant|newborn|toddler)\b.{0,50}\b(pit ?bull|rottweiler|husky|german shepherd|dog)\b.{0,30}\b(sleep|alone|unsupervised)\b",
             "⚠️ SAFETY: Baby sleeping near dog - dogs should never be left unsupervised with infants"),
            # Flexible: baby AND large dog breed in same text
            (r"(?=.*\b(baby|infant|newborn|toddler)\b)(?=.*\b(pit ?bull|rottweiler|husky|wolf|malamute)\b)",
             "⚠️ SAFETY: Video shows baby with large/powerful dog - dogs should never be left unsupervised with infants"),
            # Cats with babies sleeping
            (r"\b(cat|kitten)\b.{0,40}\b(baby|infant|newborn)\b.{0,30}\b(sleep|sleeping|crib|face|breathing)\b",
             "⚠️ SAFETY: Cat near sleeping baby - cats can accidentally suffocate infants"),
            # Exotic/wild animals with children
            (r"\b(snake|python|boa|constrictor|reptile|monitor lizard|alligator|crocodile|wolf|coyote|fox|raccoon|monkey|chimp|chimpanzee|primate)\b.{0,50}\b(baby|infant|toddler|child|kid|play|hug|cuddle|sleep)\b",
             "⚠️ SAFETY: Wild/exotic animal near child - extremely dangerous, wild animals are unpredictable"),
            (r"\b(baby|infant|toddler|child|kid)\b.{0,50}\b(snake|python|boa|monitor|alligator|crocodile|wolf|coyote|monkey|chimp|primate)\b",
             "⚠️ SAFETY: Child near wild/exotic animal - these animals can cause severe injury or death"),
            # General dangerous combinations
            (r"\b(baby|infant|newborn|toddler)\b.{0,40}\b(sleep|sleeping|nap)\b.{0,40}\b(with|next to|beside|near)\b.{0,30}\b(pet|animal|dog|cat|bird|parrot)\b",
             "⚠️ SAFETY: Baby sleeping with pet - animals should never be left unsupervised with sleeping infants"),
        ]
        
    def _detect_impossible_content(self, title: str, description: str = "", channel: str = "", tags: list = None) -> str | None:
        """
        Detect likely AI content based on impossible scenarios in video title,
        description, hashtags, channel name, and tags.
        Returns description of why it's flagged, or None if not detected.
        """
        tags = tags or []
        
        # Combine all text for analysis
        full_text = f"{title} {description}".lower()
        channel_lower = channel.lower() if channel else ""
        
        # Check title patterns
        for pattern, reason in self._impossible_patterns:
            if re.search(pattern, full_text, re.IGNORECASE):
                return reason
        
        # Check for suspicious hashtags (high confidence for AI content)
        hashtag_count = 0
        matched_hashtags = []
        for hashtag_pattern in self._ai_hashtag_patterns:
            if re.search(hashtag_pattern, full_text, re.IGNORECASE):
                hashtag_count += 1
                matched_hashtags.append(hashtag_pattern.replace("#", "").replace("\\", ""))
        
        # 2+ AI-related hashtags = very likely AI
        if hashtag_count >= 2:
            return f"Multiple AI-associated hashtags detected: {', '.join(matched_hashtags[:3])}"
        
        # Check channel name patterns
        for pattern in self._suspicious_channel_patterns:
            if re.search(pattern, channel_lower, re.IGNORECASE):
                # Channel name alone isn't enough, but combined with 1 hashtag = flag
                if hashtag_count >= 1:
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
    
    def _detect_dangerous_animal_child(self, title: str, description: str = "", tags: list = None) -> str | None:
        """
        Detect dangerous situations with animals and children/babies.
        Returns safety warning description or None.
        """
        tags = tags or []
        full_text = f"{title} {description} {' '.join(tags)}".lower()
        
        for pattern, warning in self._dangerous_animal_child_patterns:
            if re.search(pattern, full_text, re.IGNORECASE):
                return warning
        
        return None
        
    async def analyze(self, video_id: str) -> dict:
        """
        Perform full safety analysis on a video.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Analysis results including safety score, warnings, and categories
        """
        # Step 0: Get video metadata (channel name) to check if trusted
        channel_name = ""
        video_title = ""
        video_description = ""
        video_tags = []
        is_trusted_channel = False
        
        try:
            fetcher = YouTubeDataFetcher(api_key=self.youtube_api_key)
            metadata = await fetcher.get_video_metadata(video_id)
            if metadata:
                channel_name = metadata.channel
                video_title = metadata.title
                video_description = metadata.description
                video_tags = metadata.tags or []
                is_trusted_channel = channel_name.lower() in self.TRUSTED_CHANNELS
            await fetcher.close()
        except Exception as e:
            print(f"Metadata fetch failed: {e}")
        
        # Step 1: Get transcript
        transcript_text, transcript_available = await self._get_transcript(video_id)
        
        # Step 2: Get and analyze comments (community warnings)
        comment_analysis = await self._analyze_comments(video_id)
        
        # If trusted channel, filter out AI warnings (they're likely false positives)
        if is_trusted_channel:
            print(f"✅ Trusted channel: {channel_name} - skipping AI warnings")
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
                print(f"🤖 Heuristic AI detection triggered: {heuristic_ai}")
        
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
                print(f"⚠️ Dangerous animal/child situation detected: {dangerous_animal_child}")
        
        # Step 3: Match against danger signatures (transcript + comment text)
        all_text = transcript_text
        if comment_analysis.get("top_concerns"):
            # Add comment concerns to analysis text
            concern_text = " ".join([c["concern"] for c in comment_analysis["top_concerns"]])
            all_text += " " + concern_text
        
        signature_matches = self._match_signatures(all_text)
        
        # Step 4: Analyze each category
        category_results = self._analyze_categories(all_text, signature_matches)
        
        # Step 5: Generate warnings from matches + comment warnings
        warnings = self._generate_warnings(signature_matches)
        
        # Add top comment warnings
        for cw in comment_analysis.get("warnings", [])[:5]:
            warnings.append(cw)
        
        # Step 6: Calculate overall safety score (combining transcript + comments)
        transcript_score = self._calculate_safety_score(signature_matches, category_results)
        comment_score = comment_analysis.get("warning_score", 100)
        
        # Weight: 60% transcript analysis, 40% community feedback
        if transcript_available:
            safety_score = int(transcript_score * 0.6 + comment_score * 0.4)
        else:
            # If no transcript, rely more on comments
            safety_score = int(transcript_score * 0.3 + comment_score * 0.7)
        
        # Step 7: Generate summary
        summary = self._generate_summary(
            signature_matches, 
            category_results, 
            transcript_available,
            comment_analysis
        )
        
        return {
            "video_id": video_id,
            "safety_score": safety_score,
            "warnings": warnings,
            "categories": category_results,
            "summary": summary,
            "transcript_available": transcript_available,
            "comments_analyzed": comment_analysis.get("total_comments", 0),
            "comment_warnings": comment_analysis.get("warning_comments", 0),
            "channel": channel_name,
            "is_trusted_channel": is_trusted_channel,
            "video_title": video_title
        }
    
    async def _analyze_comments(self, video_id: str) -> dict:
        """Fetch and analyze YouTube comments for community warnings"""
        try:
            fetcher = YouTubeDataFetcher(api_key=self.youtube_api_key)
            comments = await fetcher.get_comments(video_id, max_results=100)
            await fetcher.close()
            
            if comments:
                return analyze_comments(comments)
            else:
                return {"total_comments": 0, "warning_comments": 0, "warnings": [], "warning_score": 100}
        except Exception as e:
            print(f"Comment analysis failed: {e}")
            return {"total_comments": 0, "warning_comments": 0, "warnings": [], "warning_score": 100}
        
        # Step 5: Calculate overall safety score
        safety_score = self._calculate_safety_score(signature_matches, category_results)
        
        # Step 6: Generate summary
        summary = self._generate_summary(signature_matches, category_results, transcript_available)
        
        return {
            "video_id": video_id,
            "safety_score": safety_score,
            "warnings": warnings,
            "categories": category_results,
            "summary": summary,
            "transcript_available": transcript_available
        }
    
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
            print(f"Transcript extraction failed: {e}")
            # Return empty string but continue analysis with metadata
            return "", False
    
    def _match_signatures(self, text: str) -> list[dict]:
        """
        Match text against danger signatures.
        Similar to antivirus signature matching.
        """
        matches = []
        
        for signature in self.signatures:
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
                # If exclusion phrase found, remove the match
                if matches and matches[-1]['signature'].get('id') == signature.get('id'):
                    for exclusion in signature.get('exclusions', []):
                        if exclusion.lower() in text:
                            matches.pop()
                            break
        
        return matches
    
    def _analyze_categories(self, text: str, matches: list) -> dict:
        """Analyze text for each safety category"""
        categories = self.safety_db.get_categories()
        results = {}
        
        for cat_id, category in categories.items():
            # Count matches in this category
            cat_matches = [m for m in matches if m['signature'].get('category') == cat_id]
            
            # Calculate category score (100 = safe, 0 = dangerous)
            if cat_matches:
                # More matches = lower score
                severity_weights = {'high': 30, 'medium': 15, 'low': 5}
                total_penalty = sum(
                    severity_weights.get(m['signature'].get('severity', 'low'), 5)
                    for m in cat_matches
                )
                score = max(0, 100 - total_penalty)
            else:
                score = 100
            
            results[category['name']] = {
                'emoji': category['emoji'],
                'flagged': len(cat_matches) > 0,
                'score': score
            }
        
        return results
    
    def _generate_warnings(self, matches: list) -> list[dict]:
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
            warnings.append({
                'category': self.safety_db.get_category_name(sig.get('category', 'general')),
                'severity': sig.get('severity', 'low'),
                'message': sig.get('warning_message', sig.get('description', 'Potential safety concern detected')),
                'safe_alternative': sig.get('safe_alternative'),
                'source': sig.get('source')
            })
        
        return warnings
    
    def _calculate_safety_score(self, matches: list, categories: dict) -> int:
        """
        Calculate overall safety score (0-100).
        
        Factors:
        - Number and severity of matched signatures
        - Category scores
        """
        if not matches:
            return 95  # High score if no issues found
        
        # Base score
        base_score = 100
        
        # Penalty for each match based on severity
        severity_penalties = {'high': 25, 'medium': 12, 'low': 5}
        
        for match in matches:
            severity = match['signature'].get('severity', 'low')
            base_score -= severity_penalties.get(severity, 5)
        
        # Average with category scores
        if categories:
            category_avg = sum(c['score'] for c in categories.values()) / len(categories)
            final_score = (base_score * 0.6) + (category_avg * 0.4)
        else:
            final_score = base_score
        
        return max(0, min(100, int(final_score)))
    
    def _generate_summary(self, matches: list, categories: dict, has_transcript: bool, comment_analysis: dict = None) -> str:
        """Generate a human-readable summary of the analysis"""
        
        parts = []
        
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


class AIAnalyzer:
    """
    Optional AI-powered analyzer for deeper contextual analysis.
    Requires OpenAI API key or Anthropic API key.
    """
    
    def __init__(self, api_key: str, provider: str = 'openai'):
        self.api_key = api_key
        self.provider = provider
        
    async def analyze_context(self, transcript: str, video_title: str) -> dict:
        """
        Use AI to analyze the transcript for contextual dangers
        that simple pattern matching might miss.
        """
        # This is a placeholder for AI integration
        # Uncomment and configure based on your API provider
        
        """
        if self.provider == 'openai':
            import openai
            openai.api_key = self.api_key
            
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": '''You are a safety analyst. Analyze the following video transcript 
                        for potentially dangerous advice, misinformation, or unsafe practices.
                        Focus on:
                        - Dangerous physical exercises or techniques
                        - Unsafe DIY practices or materials
                        - Medical misinformation
                        - Food safety issues
                        - Electrical/fire hazards
                        
                        Return a JSON object with:
                        {
                            "concerns": [{"category": str, "severity": str, "description": str}],
                            "overall_risk": "low" | "medium" | "high",
                            "summary": str
                        }'''
                    },
                    {
                        "role": "user",
                        "content": f"Video Title: {video_title}\n\nTranscript:\n{transcript[:4000]}"
                    }
                ]
            )
            
            return response.choices[0].message.content
        """
        
        return {"concerns": [], "overall_risk": "low", "summary": "AI analysis not configured"}
