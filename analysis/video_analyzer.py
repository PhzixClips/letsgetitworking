"""
Video analysis and scoring functionality
"""

import random
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import isodate
from langdetect import detect, DetectorFactory
from config import VIRAL_SCORE_WEIGHTS, REPOST_KEYWORDS, GENERIC_HASHTAGS
from utils.logging import log_upgrade
from core.strings import safe_strip

# Ensure consistent language detection
DetectorFactory.seed = 0

# Optional imports
try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TextBlob = None
    TEXTBLOB_AVAILABLE = False

class VideoAnalyzer:
    """Handles video analysis, scoring, and content generation"""

    @staticmethod
    def is_english_content(title: str) -> bool:
        """Check if content is in English"""
        try:
            return detect(title) == 'en'
        except Exception:
            return True  # Default to True if detection fails

    @staticmethod
    def detect_cross_platform_virality(title: str, description: str = '') -> Tuple[bool, str]:
        """Detect signs of reposts from other platforms"""
        content = f"{title} {description}".lower()

        for keyword in REPOST_KEYWORDS:
            if keyword in content:
                return True, f"Detected keyword '{keyword}'"

        return False, ''

    @staticmethod
    def calculate_viral_score(video_data: Dict) -> Tuple[float, Dict]:
        """Calculate viral score (0-1) based on multiple factors"""
        try:
            vph = float(video_data.get('vph', 0))
            views = float(video_data.get('views', 0))
            likes = float(video_data.get('likes', 0))
            comments = float(video_data.get('comments', 0))

            # Parse duration
            duration_str = video_data.get('duration', '00:00')
            try:
                minutes, seconds = [int(x) for x in duration_str.split(':')]
                duration_seconds = minutes * 60 + seconds
            except Exception:
                duration_seconds = 0

            # Calculate recency multiplier
            age_str = video_data.get('age', '0h')
            recency = VideoAnalyzer._calculate_recency_multiplier(age_str)

            # Calculate components
            momentum = vph * recency
            engagement = (likes + comments) / max(1.0, views)
            short_bonus = 1.0 if duration_seconds < 60 else 0.0

            # Sentiment analysis
            title = str(video_data.get('title', ''))
            polarity = VideoAnalyzer._analyze_sentiment(title)

            # Random trend factor
            trend_flag = random.random()

            # Normalize components
            def scale(x: float) -> float:
                try:
                    return 1 - 1/(1 + x)
                except Exception:
                    return 0.0

            normalized = {
                'momentum': scale(momentum),
                'engagement': scale(engagement),
                'short_bonus': short_bonus,
                'polarity': polarity,
                'trend_flag': trend_flag
            }

            # Calculate weighted score
            final_score = sum(
                normalized[component] * VIRAL_SCORE_WEIGHTS[component]
                for component in VIRAL_SCORE_WEIGHTS
            )

            final_score = max(0.0, min(1.0, final_score))

            # Build context
            context = {
                'components': {
                    'momentum': momentum,
                    'engagement': engagement,
                    'short_bonus': short_bonus,
                    'polarity': polarity,
                    'trend_flag': trend_flag
                },
                'normalized': normalized,
                'weights': VIRAL_SCORE_WEIGHTS,
                'recency_multiplier': recency,
                'confidence_interval': (
                    max(0.0, final_score - 0.05),
                    min(1.0, final_score + 0.05)
                )
            }

            return final_score, context

        except Exception as e:
            log_upgrade(f"Error computing viral score: {e}")
            return 0.0, {'error': str(e)}

    @staticmethod
    def _calculate_recency_multiplier(age_str: str) -> float:
        """Calculate recency multiplier based on video age"""
        try:
            if 'h' in age_str:
                hours = float(safe_strip(age_str.replace('h', '').replace(' ago', '')))
                return max(0.2, 1 / (1 + hours / 24))
            elif 'd' in age_str:
                days = float(safe_strip(age_str.replace('d', '').replace(' ago', '')))
                return max(0.1, 1 / (1 + days))
        except Exception:
            pass
        return 0.5

    @staticmethod
    def _analyze_sentiment(title: str) -> float:
        """Analyze sentiment of title text"""
        if TEXTBLOB_AVAILABLE and title:
            try:
                polarity = (TextBlob(title).sentiment.polarity + 1) / 2
                return polarity
            except Exception:
                pass
        return 0.5

    @staticmethod
    def process_facebook_video_data(data: Dict) -> Optional[Dict]:
        """Processes the JSON output from yt-dlp for a Facebook video."""
        try:
            title = data.get('title', '')
            if not VideoAnalyzer.is_english_content(title):
                return None

            # --- Basic Info ---
            video_id = data.get('id')
            if not video_id: return None

            # --- Metrics ---
            views = int(data.get('view_count', 0))
            likes = int(data.get('like_count', 0))
            comments = int(data.get('comment_count', 0))
            like_view_ratio = round(likes / views, 4) if views > 0 else 0

            # --- Age and VPH ---
            upload_date_str = data.get('upload_date') # YYYYMMDD
            age_hours = 0
            age_str = "unknown"
            if upload_date_str:
                published_at = datetime.strptime(upload_date_str, '%Y%m%d')
                age_delta = datetime.utcnow() - published_at
                age_hours = age_delta.total_seconds() / 3600
                age_days = age_delta.days
                age_str = f"{age_days}d ago" if age_days > 0 else f"{int(age_hours)}h ago"

            vph = round(views / age_hours, 2) if age_hours > 0 else 0

            # --- Duration ---
            duration_seconds = data.get('duration', 0)
            minutes, seconds = divmod(int(duration_seconds), 60)
            duration_str = f"{minutes:02d}:{seconds:02d}"

            # --- Create Base Entry ---
            video_entry = {
                'platform': 'Facebook',
                'title': title,
                'video_id': video_id,
                'uploader': data.get('uploader', 'Unknown'),
                'views': views,
                'likes': likes,
                'comments': comments,
                'ratio': like_view_ratio,
                'vph': vph,
                'duration': duration_str,
                'age': age_str,
                'description': data.get('description', ''),
                'thumbnail': data.get('thumbnail'),
                'webpage_url': data.get('webpage_url')
            }

            # --- Add Repost and Viral Score ---
            is_repost, reason = VideoAnalyzer.detect_cross_platform_virality(
                video_entry['title'], video_entry['description']
            )
            video_entry['repost_flag'] = is_repost
            video_entry['repost_reason'] = reason

            score, context = VideoAnalyzer.calculate_viral_score(video_entry)
            video_entry['viral_score'] = round(score, 3)
            video_entry['viral_context'] = context

            return video_entry

        except Exception as e:
            log_upgrade(f"Error processing Facebook video data: {e}")
            return None

    @staticmethod
    def process_video_data(video_details: Dict, video_id: str) -> Optional[Dict]:
        """Process raw video data into structured format"""
        try:
            snippet = video_details['snippet']
            stats = video_details.get('statistics', {})
            content_details = video_details.get('contentDetails', {})

            title = snippet.get('title', '')

            # Skip non-English content
            if not VideoAnalyzer.is_english_content(title):
                return None

            # Extract metrics
            views = int(stats.get('viewCount', 0))
            likes = int(stats.get('likeCount', 0))
            comments = int(stats.get('commentCount', 0))

            # Calculate ratios
            like_view_ratio = round(likes / views, 4) if views > 0 else 0

            # Parse publication time and calculate age
            published_at = datetime.strptime(
                snippet['publishedAt'], '%Y-%m-%dT%H:%M:%SZ'
            )
            age_hours = (datetime.utcnow() - published_at).total_seconds() / 3600
            vph = round(views / age_hours, 2) if age_hours > 0 else 0

            # Parse duration
            duration_iso = content_details.get('duration', 'PT0S')
            duration_seconds = isodate.parse_duration(duration_iso).total_seconds()
            minutes, seconds = divmod(int(duration_seconds), 60)
            duration_str = f"{minutes:02d}:{seconds:02d}"

            # Format age
            age_str = f"{int(age_hours)}h ago"

            # Create video entry
            video_entry = {
                'title': title,
                'video_id': video_id,
                'views': views,
                'likes': likes,
                'comments': comments,
                'ratio': like_view_ratio,
                'vph': vph,
                'duration': duration_str,
                'age': age_str,
                'description': snippet.get('description', '')
            }

            # Add repost detection
            is_repost, reason = VideoAnalyzer.detect_cross_platform_virality(
                video_entry['title'], video_entry['description']
            )
            video_entry['repost_flag'] = is_repost
            video_entry['repost_reason'] = reason

            # Add viral score
            score, context = VideoAnalyzer.calculate_viral_score(video_entry)
            video_entry['viral_score'] = round(score, 3)
            video_entry['viral_context'] = context

            return video_entry

        except Exception as e:
            log_upgrade(f"Error processing video data: {e}")
            return None

    @staticmethod
    def generate_caption_and_hashtags(title: str, transcript: Optional[str] = None) -> Tuple[str, List[str]]:
        """Generate caption and hashtags for content"""
        # Generate caption (≤120 chars)
        caption_base = safe_strip(title)
        if transcript:
            snippet = safe_strip(transcript).split('\n')[0][:80]
            if snippet and snippet.lower() not in caption_base.lower():
                caption_base = f"{caption_base} - {snippet}"
        caption = caption_base[:120]

        # Generate hashtags
        tags = []
        if TEXTBLOB_AVAILABLE:
            try:
                text_to_analyze = transcript or title
                blob = TextBlob(text_to_analyze)
                tags.extend([phrase.lower() for phrase in blob.noun_phrases])
            except Exception:
                tags.extend(title.lower().split())
        else:
            tags.extend(title.lower().split())

        # Clean and filter tags
        cleaned_tags = []
        for word in tags:
            cleaned = ''.join(ch for ch in word if ch.isalnum())
            if len(cleaned) >= 3 and cleaned not in cleaned_tags:
                cleaned_tags.append(cleaned)

        # Create hashtags
        hashtags = [f"#{word}" for word in cleaned_tags[:15]]

        # Add generic hashtags if needed
        generic_copy = GENERIC_HASHTAGS.copy()
        while len(hashtags) < 10 and generic_copy:
            tag = generic_copy.pop(0)
            if tag not in hashtags:
                hashtags.append(tag)

        return caption, hashtags
