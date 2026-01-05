"""
Vision Analyzer - AI-powered screenshot analysis for YouTube videos
Uses OpenAI GPT-4 Vision to analyze video frames for safety concerns
"""

import os
import base64
import asyncio
import httpx
from typing import Optional
from yt_dlp import YoutubeDL
import tempfile
import subprocess
import shutil

class VisionAnalyzer:
    """Analyzes video screenshots using AI vision models"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.enabled = bool(self.api_key)
        
        if self.enabled:
            print("✅ OpenAI API key found - Vision analysis enabled")
        else:
            print("⚠️ No OPENAI_API_KEY - Vision analysis disabled")
    
    async def analyze_video_frames(self, video_id: str, num_frames: int = 5) -> dict:
        """
        Extract and analyze frames from a YouTube video
        
        Args:
            video_id: YouTube video ID
            num_frames: Number of frames to analyze (default 5)
            
        Returns:
            dict with analysis results and any safety concerns
        """
        if not self.enabled:
            return {
                "enabled": False,
                "message": "Vision analysis disabled - no API key",
                "concerns": [],
                "frames_analyzed": 0
            }
        
        try:
            # Extract frames from video
            frames = await self._extract_frames(video_id, num_frames)
            
            if not frames:
                return {
                    "enabled": True,
                    "message": "Could not extract video frames",
                    "concerns": [],
                    "frames_analyzed": 0
                }
            
            # Analyze each frame with AI vision
            all_concerns = []
            frame_results = []
            
            for i, frame_data in enumerate(frames):
                result = await self._analyze_frame(frame_data, i + 1)
                frame_results.append(result)
                
                if result.get("concerns"):
                    all_concerns.extend(result["concerns"])
            
            return {
                "enabled": True,
                "message": f"Analyzed {len(frames)} frames",
                "concerns": all_concerns,
                "frames_analyzed": len(frames),
                "frame_details": frame_results,
                "is_ai_generated": any(r.get("is_ai_generated") for r in frame_results),
                "safety_issues": any(r.get("safety_issues") for r in frame_results)
            }
            
        except Exception as e:
            print(f"Vision analysis error: {e}")
            return {
                "enabled": True,
                "message": f"Analysis error: {str(e)}",
                "concerns": [],
                "frames_analyzed": 0
            }
    
    async def _extract_frames(self, video_id: str, num_frames: int) -> list:
        """Extract frames from YouTube video using yt-dlp and ffmpeg"""
        
        frames = []
        temp_dir = tempfile.mkdtemp()
        
        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            # Download video to temp file
            ydl_opts = {
                'format': 'worst[ext=mp4]',  # Smallest video for speed
                'outtmpl': os.path.join(temp_dir, 'video.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
            }
            
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                duration = info.get('duration', 60)
            
            video_path = os.path.join(temp_dir, 'video.mp4')
            
            if not os.path.exists(video_path):
                # Try finding any video file
                for f in os.listdir(temp_dir):
                    if f.startswith('video'):
                        video_path = os.path.join(temp_dir, f)
                        break
            
            if not os.path.exists(video_path):
                print("Could not find downloaded video")
                return []
            
            # Calculate frame timestamps (evenly distributed)
            timestamps = []
            if duration > 0:
                interval = duration / (num_frames + 1)
                for i in range(1, num_frames + 1):
                    timestamps.append(int(interval * i))
            else:
                timestamps = [5, 15, 30, 45, 55][:num_frames]
            
            # Extract frames using ffmpeg
            for i, ts in enumerate(timestamps):
                frame_path = os.path.join(temp_dir, f'frame_{i}.jpg')
                
                cmd = [
                    'ffmpeg', '-ss', str(ts), '-i', video_path,
                    '-vframes', '1', '-q:v', '2',
                    '-y', frame_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, timeout=30)
                
                if os.path.exists(frame_path):
                    with open(frame_path, 'rb') as f:
                        frame_data = base64.b64encode(f.read()).decode('utf-8')
                        frames.append({
                            "timestamp": ts,
                            "data": frame_data,
                            "index": i + 1
                        })
            
            return frames
            
        except Exception as e:
            print(f"Frame extraction error: {e}")
            return []
        finally:
            # Cleanup temp directory
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    
    async def _analyze_frame(self, frame_data: dict, frame_num: int) -> dict:
        """Analyze a single frame using GPT-4 Vision"""
        
        prompt = """Analyze this video frame for safety concerns. Look for:

1. **AI/Fake Content Detection**: 
   - Is this image AI-generated? Look for: unnatural lighting, distorted hands/faces, weird textures, impossible physics, artifacts
   - Signs of deepfake or manipulated content
   
2. **Physical Safety Hazards**:
   - Dangerous activities without proper safety equipment
   - Risky stunts, unsafe practices
   - Electrical hazards, fire risks, chemical dangers
   
3. **Misleading Content**:
   - Medical misinformation being demonstrated
   - Dangerous DIY techniques
   - Stunts presented as safe when they're not

Respond in this JSON format:
{
    "is_ai_generated": true/false,
    "ai_confidence": 0-100,
    "ai_indicators": ["list of AI tells if any"],
    "safety_issues": true/false,
    "concerns": ["list of specific safety concerns"],
    "description": "brief description of what's in the frame"
}

Be conservative - only flag clear issues. If unsure, don't flag."""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "gpt-4o",  # Vision-capable model
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": prompt},
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{frame_data['data']}",
                                            "detail": "low"  # Use low detail for speed/cost
                                        }
                                    }
                                ]
                            }
                        ],
                        "max_tokens": 500
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result['choices'][0]['message']['content']
                    
                    # Parse JSON from response
                    import json
                    try:
                        # Extract JSON from response (might be wrapped in markdown)
                        if '```json' in content:
                            content = content.split('```json')[1].split('```')[0]
                        elif '```' in content:
                            content = content.split('```')[1].split('```')[0]
                        
                        analysis = json.loads(content.strip())
                        analysis['frame_num'] = frame_num
                        analysis['timestamp'] = frame_data['timestamp']
                        return analysis
                    except json.JSONDecodeError:
                        return {
                            "frame_num": frame_num,
                            "timestamp": frame_data['timestamp'],
                            "is_ai_generated": False,
                            "safety_issues": False,
                            "concerns": [],
                            "raw_response": content
                        }
                else:
                    print(f"Vision API error: {response.status_code}")
                    return {
                        "frame_num": frame_num,
                        "timestamp": frame_data['timestamp'],
                        "error": f"API error: {response.status_code}",
                        "is_ai_generated": False,
                        "safety_issues": False,
                        "concerns": []
                    }
                    
        except Exception as e:
            print(f"Frame analysis error: {e}")
            return {
                "frame_num": frame_num,
                "timestamp": frame_data['timestamp'],
                "error": str(e),
                "is_ai_generated": False,
                "safety_issues": False,
                "concerns": []
            }


# Singleton instance
_vision_analyzer = None

def get_vision_analyzer() -> VisionAnalyzer:
    """Get or create vision analyzer instance"""
    global _vision_analyzer
    if _vision_analyzer is None:
        _vision_analyzer = VisionAnalyzer()
    return _vision_analyzer
