"""YouTube Safety Inspector - AI Context Reviewer
Copyright (c) 2026 beautifulplanet
Licensed under MIT License

AI-powered contextual analysis that verifies whether flagged content
is actually promoting dangerous ideas or is debunking/educational.

Two-phase architecture:
  Phase 1: Fast pattern matching catches candidates (free, instant)
  Phase 2: LLM reviews candidates for context (promoting vs debunking)
  Fallback: Heuristic debunking detection when no API key is configured
"""

import json
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# --- Heuristic debunking keywords ---
# These strongly indicate the video is DEBUNKING or critically examining
# the flagged content rather than promoting it.
DEBUNKING_TITLE_KEYWORDS = [
    "debunk", "debunked", "debunking",
    "fact check", "fact-check", "factcheck",
    "myth", "myths", "mythbusting",
    "busted", "busting",
    "exposed", "exposing",
    "fraud", "fraudulent", "scam",
    "hoax", "hoaxes",
    "fake", "faked",
    "not real", "isn't real", "isnt real",
    "critical look", "critical analysis", "critical thinking",
    "skeptic", "skeptical",
    "disproved", "disproven", "disproving",
    "refuted", "refuting", "refutation",
    "nonsense", "pseudoscience", "pseudo-science",
    "conspiracy debunk", "conspiracy theory debunk",
    "the truth about",  # Often used by debunkers
    "why .* is wrong", "why .* is fake", "why .* doesn't work",
    "explained", "explanation",
    "history of the myth",
    "no, .* is not", "no, .* doesn't",
    "stop believing", "stop falling for",
    "don't fall for", "don't believe",
    "is it real", "is this real",
    "vs reality", "vs. reality",
    "in 2 minutes", "in two minutes",  # Short-form debunking
]

# These appear in descriptions of debunking content
DEBUNKING_DESCRIPTION_KEYWORDS = [
    "in this video i debunk",
    "in this video we debunk",
    "let's debunk",
    "let me debunk",
    "here's why .* is wrong",
    "is complete nonsense",
    "is pseudoscience",
    "is a hoax",
    "is a scam",
    "is fraudulent",
    "fact-checking",
    "critical examination",
    "has been debunked",
    "has been disproven",
    "has been refuted",
    "thoroughly debunked",
    "no scientific evidence",
    "no credible evidence",
    "lack of evidence",
    "conspiracy theory",
    "conspiracy theories",
    "misinformation",
    "disinformation",
    "internet phenomenon",
    "internet conspiracy",
]

# Educational / trusted context signals
EDUCATIONAL_SIGNALS = [
    "professor", "phd", "ph.d", "doctorate",
    "university", "academic", "researcher",
    "peer-reviewed", "peer reviewed",
    "scientific consensus",
    "evidence-based", "evidence based",
    "source:", "sources:", "references:",
    "citation", "citations",
    "study shows", "studies show", "research shows",
]

# Regex patterns for debunking (compiled once)
DEBUNKING_TITLE_PATTERNS = [
    re.compile(r"\bdebunk(?:ed|ing|s)?\b", re.IGNORECASE),
    re.compile(r"\bfact[\s-]?check(?:ed|ing|s)?\b", re.IGNORECASE),
    re.compile(r"\bmyth(?:s|busting|buster)?\b", re.IGNORECASE),
    re.compile(r"\bbusted\b", re.IGNORECASE),
    re.compile(r"\bexposed?\b", re.IGNORECASE),
    re.compile(r"\bhoax(?:es)?\b", re.IGNORECASE),
    re.compile(r"\bfraud(?:ulent)?\b", re.IGNORECASE),
    re.compile(r"\bpseudo[\s-]?science\b", re.IGNORECASE),
    re.compile(r"\bscam\b", re.IGNORECASE),
    re.compile(r"\bdisprov(?:ed|en|ing)\b", re.IGNORECASE),
    re.compile(r"\brefut(?:ed|ing|ation)\b", re.IGNORECASE),
    re.compile(r"\bskeptic(?:al)?\b", re.IGNORECASE),
    re.compile(r"\bnonsense\b", re.IGNORECASE),
    re.compile(r"\bwhy\b.+\bis\s+(?:wrong|fake|bs|nonsense)\b", re.IGNORECASE),
    re.compile(r"\bstop\s+(?:believing|falling\s+for)\b", re.IGNORECASE),
    re.compile(r"\bdon'?t\s+(?:fall\s+for|believe)\b", re.IGNORECASE),
    re.compile(r"\bvs\.?\s*reality\b", re.IGNORECASE),
    re.compile(r"\bis\s+(?:it|this)\s+real\b", re.IGNORECASE),
    re.compile(r"\bno[,.]?\s+\w+.{0,20}\b(?:does|do|is|are|will|can)\s*(?:not|n'?t)\b", re.IGNORECASE),
    re.compile(r"\bspoiler[:\s]+no\b", re.IGNORECASE),
]

# LLM system prompt for context verification
CONTEXT_REVIEW_SYSTEM_PROMPT = """You are an expert content context analyzer for a YouTube safety tool. Your job is to determine whether a video is PROMOTING dangerous/misleading content or is DEBUNKING/EDUCATING about it.

You will be given:
- Video title
- Video description (if available)
- Transcript excerpt (if available)
- The safety category that was flagged

Your task: Determine the video's INTENT regarding the flagged category.

CRITICAL RULES:
1. A video that MENTIONS a conspiracy theory to debunk it is NOT promoting it
2. A video titled "X Debunked" or "X is Fake" is clearly debunking, NOT promoting
3. Educational content that explains WHY something is wrong is NOT promoting it
4. Satire and comedy about a topic is NOT promoting it
5. News coverage REPORTING on a conspiracy is NOT promoting it
6. A critic reviewing problematic content is NOT promoting it

Respond with ONLY valid JSON (no markdown, no code fences):
{
    "verdict": "promoting" | "debunking" | "educational" | "neutral" | "satire",
    "confidence": 0.0 to 1.0,
    "reasoning": "Brief explanation of your determination",
    "is_dangerous": true | false
}

Where:
- "promoting": The video actively promotes the flagged dangerous content
- "debunking": The video debunks, refutes, or fact-checks the flagged content
- "educational": The video educates about the topic in a balanced/academic way
- "neutral": The video mentions the topic but doesn't clearly promote or debunk
- "satire": The video treats the topic as comedy/satire
- "is_dangerous": true ONLY if verdict is "promoting", false for all others"""

CONTEXT_REVIEW_USER_TEMPLATE = """Flagged Category: {category}
Category Description: {category_description}

Video Title: {title}
Channel: {channel}
Video Description: {description}

{transcript_section}

Based on this information, is this video PROMOTING the flagged dangerous content, or is it DEBUNKING/EDUCATING about it? Respond with JSON only."""


class AIContextReviewer:
    """
    AI-powered context reviewer that verifies whether pattern-matched content
    is actually promoting dangerous ideas or is debunking/educational.
    
    Supports:
    - OpenAI (GPT-4o, GPT-4o-mini)
    - Anthropic (Claude 3.5 Sonnet, Claude 3 Haiku)
    - Heuristic fallback (no API key needed)
    """
    
    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        provider: str = "auto",
        model: Optional[str] = None,
    ):
        """
        Initialize the AI context reviewer.
        
        Args:
            openai_api_key: OpenAI API key (enables GPT-4o review)
            anthropic_api_key: Anthropic API key (enables Claude review)
            provider: "openai", "anthropic", or "auto" (picks best available)
            model: Override model name (default: auto-selects best)
        """
        self.openai_api_key = openai_api_key
        self.anthropic_api_key = anthropic_api_key
        self._openai_client = None
        self._anthropic_client = None
        
        # Auto-select provider
        if provider == "auto":
            if anthropic_api_key:
                self.provider = "anthropic"
            elif openai_api_key:
                self.provider = "openai"
            else:
                self.provider = "heuristic"
        else:
            self.provider = provider
        
        # Set model
        if model:
            self.model = model
        elif self.provider == "anthropic":
            self.model = "claude-sonnet-4-20250514"
        elif self.provider == "openai":
            self.model = "gpt-4o"
        else:
            self.model = "heuristic"
        
        # Initialize clients lazily
        self._init_clients()
        
        logger.info(f"🧠 AI Context Reviewer initialized: provider={self.provider}, model={self.model}")
    
    def _init_clients(self):
        """Initialize API clients based on available keys."""
        if self.provider == "openai" and self.openai_api_key:
            try:
                from openai import AsyncOpenAI
                self._openai_client = AsyncOpenAI(api_key=self.openai_api_key)
                logger.info("✅ OpenAI client initialized")
            except ImportError:
                logger.warning("openai package not installed. Run: pip install openai")
                self.provider = "heuristic"
                self.model = "heuristic"
        
        elif self.provider == "anthropic" and self.anthropic_api_key:
            try:
                from anthropic import AsyncAnthropic
                self._anthropic_client = AsyncAnthropic(api_key=self.anthropic_api_key)
                logger.info("✅ Anthropic client initialized")
            except ImportError:
                logger.warning("anthropic package not installed. Run: pip install anthropic")
                self.provider = "heuristic"
                self.model = "heuristic"
    
    @property
    def is_ai_enabled(self) -> bool:
        """Check if an AI provider is available."""
        return self.provider in ("openai", "anthropic") and (
            self._openai_client is not None or self._anthropic_client is not None
        )
    
    # ------------------------------------------------------------------ #
    #  Heuristic debunking detection (no API key needed)                 #
    # ------------------------------------------------------------------ #
    
    def heuristic_is_debunking(
        self,
        title: str,
        description: str = "",
        transcript: str = "",
    ) -> dict:
        """
        Fast heuristic check for debunking/educational content.
        No API key required. Catches obvious cases like:
        - "Tartaria Debunked in 2 Minutes"
        - "Flat Earth: The Myth Busted"
        - "Why Crystal Healing is Pseudoscience"
        
        Returns:
            {
                "is_debunking": bool,
                "confidence": float (0-1),
                "signals": list[str],
                "method": "heuristic"
            }
        """
        title_lower = (title or "").lower()
        desc_lower = (description or "").lower()
        transcript_lower = (transcript or "")[:5000].lower()
        
        signals = []
        score = 0.0
        
        # Check title for debunking patterns (strongest signal)
        for pattern in DEBUNKING_TITLE_PATTERNS:
            match = pattern.search(title_lower)
            if match:
                signals.append(f"Title contains debunking keyword: '{match.group()}'")
                score += 0.4
                break  # One strong title signal is enough
        
        # Check title for specific debunking keyword phrases
        for keyword in DEBUNKING_TITLE_KEYWORDS:
            if keyword in title_lower:
                if keyword not in [s for s in signals]:  # Avoid double-counting
                    signals.append(f"Title contains: '{keyword}'")
                    score += 0.3
                    break
        
        # Check description for debunking context
        desc_debunk_count = 0
        for keyword in DEBUNKING_DESCRIPTION_KEYWORDS:
            if keyword in desc_lower:
                desc_debunk_count += 1
                if desc_debunk_count <= 2:  # Cap at 2 description signals
                    signals.append(f"Description contains: '{keyword}'")
        if desc_debunk_count > 0:
            score += min(0.3, desc_debunk_count * 0.15)
        
        # Check for educational signals
        edu_count = 0
        for signal in EDUCATIONAL_SIGNALS:
            if signal in desc_lower or signal in transcript_lower:
                edu_count += 1
                if edu_count <= 2:
                    signals.append(f"Educational signal: '{signal}'")
        if edu_count > 0:
            score += min(0.2, edu_count * 0.1)
        
        # Transcript-based debunking signals (weaker but helpful)
        if transcript_lower:
            transcript_debunk_phrases = [
                "this is false", "this is not true", "this is a myth",
                "this has been debunked", "no evidence", "no scientific basis",
                "this is pseudoscience", "let me explain why this is wrong",
                "this is simply not true", "there is no proof",
                "conspiracy theory", "misinformation",
            ]
            for phrase in transcript_debunk_phrases:
                if phrase in transcript_lower:
                    signals.append(f"Transcript contains: '{phrase}'")
                    score += 0.1
                    break  # One transcript signal is enough
        
        # Cap confidence at 0.95 for heuristic
        confidence = min(0.95, score)
        is_debunking = confidence >= 0.3  # Threshold: at least one strong signal
        
        return {
            "is_debunking": is_debunking,
            "confidence": round(confidence, 2),
            "signals": signals,
            "method": "heuristic",
        }
    
    # ------------------------------------------------------------------ #
    #  AI-powered context review (requires API key)                      #
    # ------------------------------------------------------------------ #
    
    async def ai_review_context(
        self,
        title: str,
        description: str,
        channel: str,
        transcript: str,
        category: str,
        category_description: str = "",
    ) -> dict:
        """
        Use LLM to verify whether flagged content is promoting or debunking.
        
        Returns:
            {
                "verdict": "promoting" | "debunking" | "educational" | "neutral" | "satire",
                "confidence": float (0-1),
                "reasoning": str,
                "is_dangerous": bool,
                "method": "openai" | "anthropic"
            }
        """
        # Build the prompt
        transcript_section = ""
        if transcript:
            # Use first 3000 chars of transcript for context
            truncated = transcript[:3000]
            transcript_section = f"Transcript excerpt:\n{truncated}"
        else:
            transcript_section = "Transcript: Not available"
        
        user_message = CONTEXT_REVIEW_USER_TEMPLATE.format(
            category=category,
            category_description=category_description or category,
            title=title or "Unknown",
            channel=channel or "Unknown",
            description=(description or "No description")[:1000],
            transcript_section=transcript_section,
        )
        
        try:
            if self.provider == "openai" and self._openai_client:
                return await self._review_with_openai(user_message)
            elif self.provider == "anthropic" and self._anthropic_client:
                return await self._review_with_anthropic(user_message)
            else:
                # Fallback to heuristic
                heuristic = self.heuristic_is_debunking(title, description, transcript)
                return {
                    "verdict": "debunking" if heuristic["is_debunking"] else "promoting",
                    "confidence": heuristic["confidence"],
                    "reasoning": f"Heuristic: {'; '.join(heuristic['signals'][:3])}",
                    "is_dangerous": not heuristic["is_debunking"],
                    "method": "heuristic",
                }
        except Exception as e:
            logger.error(f"AI review failed, falling back to heuristic: {e}")
            heuristic = self.heuristic_is_debunking(title, description, transcript)
            return {
                "verdict": "debunking" if heuristic["is_debunking"] else "promoting",
                "confidence": heuristic["confidence"],
                "reasoning": f"AI review failed ({e}). Heuristic fallback: {'; '.join(heuristic['signals'][:3])}",
                "is_dangerous": not heuristic["is_debunking"],
                "method": "heuristic_fallback",
            }
    
    async def _review_with_openai(self, user_message: str) -> dict:
        """Call OpenAI API for context review."""
        response = await self._openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": CONTEXT_REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,  # Low temp for consistent judgments
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        
        result = json.loads(response.choices[0].message.content)
        result["method"] = "openai"
        
        logger.info(f"🧠 OpenAI review: verdict={result.get('verdict')}, "
                    f"confidence={result.get('confidence')}, "
                    f"dangerous={result.get('is_dangerous')}")
        
        return self._validate_result(result)
    
    async def _review_with_anthropic(self, user_message: str) -> dict:
        """Call Anthropic API for context review."""
        response = await self._anthropic_client.messages.create(
            model=self.model,
            max_tokens=300,
            system=CONTEXT_REVIEW_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
        )
        
        # Extract text from Anthropic response
        text = response.content[0].text.strip()
        
        # Parse JSON (handle potential markdown fences)
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        
        result = json.loads(text)
        result["method"] = "anthropic"
        
        logger.info(f"🧠 Anthropic review: verdict={result.get('verdict')}, "
                    f"confidence={result.get('confidence')}, "
                    f"dangerous={result.get('is_dangerous')}")
        
        return self._validate_result(result)
    
    def _validate_result(self, result: dict) -> dict:
        """Validate and normalize AI response."""
        valid_verdicts = {"promoting", "debunking", "educational", "neutral", "satire"}
        
        if result.get("verdict") not in valid_verdicts:
            result["verdict"] = "neutral"
        
        confidence = result.get("confidence", 0.5)
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            confidence = 0.5
        result["confidence"] = round(float(confidence), 2)
        
        # Enforce is_dangerous logic
        result["is_dangerous"] = result["verdict"] == "promoting"
        
        if "reasoning" not in result:
            result["reasoning"] = "No reasoning provided"
        
        return result
    
    # ------------------------------------------------------------------ #
    #  Main entry point: review a flagged match                          #
    # ------------------------------------------------------------------ #
    
    async def review_flagged_content(
        self,
        title: str,
        description: str,
        channel: str,
        transcript: str,
        category: str,
        category_description: str = "",
    ) -> dict:
        """
        Review a piece of content that was flagged by pattern matching.
        Uses AI if available, falls back to heuristic.
        
        This is the main entry point called by the analyzer when
        metadata signatures fire.
        
        Returns:
            {
                "verdict": str,
                "confidence": float,
                "reasoning": str,
                "is_dangerous": bool,
                "method": str,
                "should_suppress": bool,  # True = suppress the warning
            }
        """
        # Always run heuristic first (instant, free)
        heuristic = self.heuristic_is_debunking(title, description, transcript)
        
        logger.info(f"🔍 Reviewing flagged content: '{title}' | category={category} | "
                    f"heuristic_debunking={heuristic['is_debunking']} "
                    f"(confidence={heuristic['confidence']})")
        
        # If AI is available and heuristic isn't very confident, use AI
        if self.is_ai_enabled:
            ai_result = await self.ai_review_context(
                title=title,
                description=description,
                channel=channel,
                transcript=transcript,
                category=category,
                category_description=category_description,
            )
            
            # AI overrides heuristic when confident
            if ai_result["confidence"] >= 0.6:
                ai_result["should_suppress"] = not ai_result["is_dangerous"]
                ai_result["heuristic_agreed"] = (
                    heuristic["is_debunking"] == (not ai_result["is_dangerous"])
                )
                return ai_result
            
            # Low AI confidence: combine with heuristic
            if heuristic["is_debunking"] and heuristic["confidence"] >= 0.5:
                # Both think it's debunking — suppress with combined confidence
                return {
                    "verdict": "debunking",
                    "confidence": max(ai_result["confidence"], heuristic["confidence"]),
                    "reasoning": f"AI + heuristic agree: debunking. AI: {ai_result['reasoning']}",
                    "is_dangerous": False,
                    "method": f"{ai_result['method']}+heuristic",
                    "should_suppress": True,
                    "heuristic_agreed": True,
                }
        
        # Heuristic only (no AI available)
        should_suppress = heuristic["is_debunking"] and heuristic["confidence"] >= 0.3
        
        return {
            "verdict": "debunking" if heuristic["is_debunking"] else "promoting",
            "confidence": heuristic["confidence"],
            "reasoning": f"Heuristic only: {'; '.join(heuristic['signals'][:3])}" if heuristic["signals"] else "No debunking signals found",
            "is_dangerous": not should_suppress,
            "method": "heuristic",
            "should_suppress": should_suppress,
        }
    
    # ------------------------------------------------------------------ #
    #  Deep transcript safety analysis (AI-only)                         #
    # ------------------------------------------------------------------ #
    
    async def analyze_transcript_safety(
        self,
        title: str,
        description: str,
        channel: str,
        transcript: str,
    ) -> dict:
        """
        Deep AI analysis of transcript for contextual dangers that
        pattern matching cannot catch. Examples:
        - Indoor fire without ventilation warnings
        - Using non-food-safe materials for cooking
        - Meditation presented as replacement for medicine
        - Dangerous stunts (subway surfing, rooftop climbing)
        
        Only runs when AI is available. Returns empty result otherwise.
        
        Returns:
            {
                "concerns": [
                    {
                        "category": str,
                        "severity": "high" | "medium" | "low",
                        "description": str,
                        "timestamp_hint": str | None
                    }
                ],
                "overall_risk": "low" | "medium" | "high",
                "summary": str,
                "method": str
            }
        """
        if not self.is_ai_enabled or not transcript:
            return {
                "concerns": [],
                "overall_risk": "low",
                "summary": "Deep analysis not available (no AI key or no transcript)",
                "method": "skipped",
            }
        
        system_prompt = """You are a safety analyst for a YouTube video safety tool. Analyze the video content for dangers that simple keyword matching would miss.

Focus on CONTEXTUAL dangers:
1. Fire/heat without ventilation or safety warnings
2. Non-food-safe materials used in cooking/food prep
3. Alternative medicine presented as replacement for real medicine
4. Dangerous physical stunts (subway surfing, rooftop climbing, train hopping)
5. DIY projects with hidden electrical/chemical/structural hazards
6. Exercise techniques that could cause injury without proper form warnings
7. Unlicensed medical/legal/financial advice presented as authoritative
8. Child safety issues (dangerous activities with children)

DO NOT flag:
- Professional demonstrations with proper safety equipment
- Content that explicitly warns viewers about dangers
- Educational content explaining why something is dangerous
- Clearly fictional/entertainment content
- Standard cooking, DIY, or exercise content done safely

Respond with ONLY valid JSON (no markdown, no code fences):
{
    "concerns": [
        {
            "category": "fire_safety" | "food_safety" | "medical_misinfo" | "dangerous_stunts" | "diy_hazard" | "exercise_risk" | "unauthorized_advice" | "child_safety",
            "severity": "high" | "medium" | "low",
            "description": "Brief description of the specific concern"
        }
    ],
    "overall_risk": "low" | "medium" | "high",
    "summary": "One-sentence safety summary"
}

If no concerns found, return empty concerns array with "low" risk."""

        user_message = f"""Video Title: {title or 'Unknown'}
Channel: {channel or 'Unknown'}
Description: {(description or 'No description')[:500]}

Transcript (first 4000 chars):
{transcript[:4000]}

Analyze this content for safety concerns that keyword matching would miss."""

        try:
            if self.provider == "openai" and self._openai_client:
                response = await self._openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.1,
                    max_tokens=500,
                    response_format={"type": "json_object"},
                )
                result = json.loads(response.choices[0].message.content)
                result["method"] = "openai"
                
            elif self.provider == "anthropic" and self._anthropic_client:
                response = await self._anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=500,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                    temperature=0.1,
                )
                text = response.content[0].text.strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                result = json.loads(text)
                result["method"] = "anthropic"
            else:
                return {
                    "concerns": [],
                    "overall_risk": "low",
                    "summary": "No AI provider available",
                    "method": "skipped",
                }
            
            # Validate
            if "concerns" not in result:
                result["concerns"] = []
            if "overall_risk" not in result:
                result["overall_risk"] = "low"
            if "summary" not in result:
                result["summary"] = "Analysis complete"
            
            logger.info(f"🧠 Deep analysis: {len(result['concerns'])} concerns, "
                       f"risk={result['overall_risk']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Deep transcript analysis failed: {e}")
            return {
                "concerns": [],
                "overall_risk": "low",
                "summary": f"Analysis failed: {e}",
                "method": "error",
            }
