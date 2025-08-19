"""
Search engine for finding and filtering YouTube videos
"""

from typing import Dict, List, Optional, Callable
from datetime import datetime
from api.youtube_client import YouTubeAPIClient
from analysis.video_analyzer import VideoAnalyzer
from config import MIN_RESULTS_PER_CALL
from utils.logging import log_upgrade

class SearchEngine:
    """Handles video searching with advanced filtering"""

    def __init__(self):
        self.api_client = YouTubeAPIClient()
        self.video_analyzer = VideoAnalyzer()
        self.low_efficiency_count = 0

    def reset_search(self):
        """Reset search state"""
        self.api_client.reset_tracking()
        self.low_efficiency_count = 0

    def cancel_search(self):
        """Cancel ongoing search"""
        self.api_client.cancel_search()

    def parse_multi_query(self, query_string: str) -> List[Dict]:
        """Parse query string with negative keywords"""
        if not query_string.strip():
            return [{'query': '', 'negative': []}]

        queries = []
        parts = [part.strip() for part in query_string.split(',') if part.strip()]

        for part in parts:
            words = part.split()
            positive_words = []
            negative_words = []

            for word in words:
                if word.startswith('-') and len(word) > 1:
                    negative_words.append(word[1:].lower())
                else:
                    positive_words.append(word)

            if positive_words:
                queries.append({
                    'query': ' '.join(positive_words),
                    'negative': negative_words
                })

        return queries if queries else [{'query': query_string, 'negative': []}]

    def search_videos(self, query: str, max_results: int = 50,
                     published_after: Optional[datetime] = None,
                     min_vph: float = 0,
                     max_duration: Optional[int] = None,
                     progress_callback: Optional[Callable] = None) -> List[Dict]:
        """Search for videos with filtering"""
        videos = []
        seen_ids = set()
        next_page_token = None

        while len(videos) < max_results:
            if self.api_client.search_cancelled:
                break

            try:
                # Search for video IDs
                video_ids, next_page_token = self.api_client.search_videos(
                    query, max_results - len(videos), published_after, next_page_token
                )

                if not video_ids:
                    self.low_efficiency_count += 1
                    if self.low_efficiency_count >= 3:
                        log_upgrade("Auto-stopping: 3 consecutive searches with no new results")
                        break
                    continue
                else:
                    self.low_efficiency_count = 0

                # Filter out already seen videos
                new_video_ids = [vid for vid in video_ids if vid not in seen_ids]
                if not new_video_ids:
                    continue

                seen_ids.update(new_video_ids)

                # Get video details
                video_details_map = self.api_client.get_video_details(new_video_ids)

                # Process videos
                videos_added = 0
                for video_id in new_video_ids:
                    if self.api_client.search_cancelled or len(videos) >= max_results:
                        break

                    video_details = video_details_map.get(video_id)
                    if not video_details:
                        continue

                    # Process video data
                    video_entry = self.video_analyzer.process_video_data(
                        video_details, video_id
                    )

                    if not video_entry:
                        continue

                    # Apply filters
                    if video_entry['vph'] < min_vph:
                        continue

                    if max_duration is not None:
                        duration_parts = video_entry['duration'].split(':')
                        duration_seconds = int(duration_parts[0]) * 60 + int(duration_parts[1])
                        if duration_seconds > max_duration:
                            continue

                    videos.append(video_entry)
                    videos_added += 1

                    # Progress callback
                    if progress_callback and len(videos) % 5 == 0:
                        progress_callback(len(videos), max_results)

                # Check efficiency
                if videos_added < MIN_RESULTS_PER_CALL:
                    self.low_efficiency_count += 1
                    if self.low_efficiency_count >= 3:
                        log_upgrade(f"Auto-stopping: Low efficiency ({videos_added} results)")
                        break
                else:
                    self.low_efficiency_count = 0

                if not next_page_token:
                    break

            except Exception as e:
                log_upgrade(f"Search error: {e}")
                break

        return videos[:max_results]

    def smart_search_fill(self, base_query: str, desired_count: int,
                         published_after: Optional[datetime] = None,
                         min_vph: float = 0,
                         max_duration: Optional[int] = None,
                         progress_callback: Optional[Callable] = None) -> List[Dict]:
        """Smart search with query expansion and negative keyword filtering"""
        queries = self.parse_multi_query(base_query)
        all_videos = []
        seen_ids = set()

        for query_info in queries:
            if self.api_client.search_cancelled or len(all_videos) >= desired_count:
                break

            query_term = query_info['query']
            negative_words = query_info['negative']

            if progress_callback:
                progress_callback(-1, desired_count, f"Searching: {query_term}")

            # Main search
            results = self.search_videos(
                query_term,
                max_results=min(50, desired_count - len(all_videos)),
                published_after=published_after,
                min_vph=min_vph,
                max_duration=max_duration,
                progress_callback=progress_callback
            )

            # Filter and add results
            for video in results:
                if self.api_client.search_cancelled or len(all_videos) >= desired_count:
                    break

                if video['video_id'] not in seen_ids:
                    title_lower = video['title'].lower()
                    if not any(neg_word in title_lower for neg_word in negative_words):
                        seen_ids.add(video['video_id'])
                        all_videos.append(video)

            # Try suggestions if we need more results
            if len(all_videos) < desired_count and not self.api_client.search_cancelled:
                self._search_with_suggestions(
                    query_term, negative_words, all_videos, seen_ids,
                    desired_count, published_after, min_vph, max_duration,
                    progress_callback
                )

        return all_videos[:desired_count]

    def _search_with_suggestions(self, query_term: str, negative_words: List[str],
                               all_videos: List[Dict], seen_ids: set,
                               desired_count: int, published_after: Optional[datetime],
                               min_vph: float, max_duration: Optional[int],
                               progress_callback: Optional[Callable]):
        """Search using query suggestions to fill remaining results"""
        try:
            suggestions = self.api_client.get_suggestions(query_term)

            for suggestion in suggestions[:3]:
                if self.api_client.search_cancelled or len(all_videos) >= desired_count:
                    break

                if progress_callback:
                    progress_callback(-1, desired_count, f"Trying suggestion: {suggestion}")

                suggestion_results = self.search_videos(
                    suggestion,
                    max_results=min(20, desired_count - len(all_videos)),
                    published_after=published_after,
                    min_vph=min_vph,
                    max_duration=max_duration
                )

                for video in suggestion_results:
                    if self.api_client.search_cancelled or len(all_videos) >= desired_count:
                        break

                    if video['video_id'] not in seen_ids:
                        title_lower = video['title'].lower()
                        if not any(neg_word in title_lower for neg_word in negative_words):
                            seen_ids.add(video['video_id'])
                            all_videos.append(video)

        except Exception as e:
            log_upgrade(f"Error with suggestions for {query_term}: {e}")
