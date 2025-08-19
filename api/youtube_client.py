"""
YouTube API client for handling all API interactions
"""

import requests
import itertools
from datetime import datetime, timezone
import isodate
from typing import Dict, List, Optional, Tuple
from config import API_KEY_LIST, MAX_API_CALLS
from utils.logging import log_upgrade

class YouTubeAPIClient:
    def __init__(self):
        self.api_keys = itertools.cycle(API_KEY_LIST)
        self.api_call_count = 0
        self.search_cancelled = False

    def reset_tracking(self):
        """Reset API call tracking"""
        self.api_call_count = 0
        self.search_cancelled = False

    def cancel_search(self):
        """Cancel ongoing search operations"""
        self.search_cancelled = True

    def _get_next_key(self) -> str:
        """Get next API key from rotation"""
        return next(self.api_keys)

    def _make_request(self, url: str, params: Dict) -> Dict:
        """Make API request with fallback key rotation"""
        if self.search_cancelled:
            raise Exception('Search cancelled by user')

        if self.api_call_count >= MAX_API_CALLS:
            raise Exception(f'API call limit reached ({MAX_API_CALLS} calls)')

        for _ in range(len(API_KEY_LIST)):
            params['key'] = self._get_next_key()
            try:
                response = requests.get(url, params=params, timeout=10)
                data = response.json()
                self.api_call_count += 1

                if 'error' not in data:
                    return data

            except Exception as e:
                log_upgrade(f"API request error: {e}")
                continue

        raise Exception('All API keys exhausted or network error')

    def search_videos(self, query: str, max_results: int = 50,
                     published_after: Optional[datetime] = None,
                     next_page_token: Optional[str] = None) -> Tuple[List[str], Optional[str]]:
        """Search for videos and return video IDs and next page token"""
        search_url = 'https://www.googleapis.com/youtube/v3/search'

        params = {
            'part': 'snippet',
            'q': query,
            'type': 'video',
            'maxResults': min(50, max_results),
            'videoDuration': 'any',
            'safeSearch': 'moderate'
        }

        if published_after:
            params['publishedAfter'] = published_after.replace(
                tzinfo=timezone.utc
            ).isoformat().replace('+00:00', 'Z')

        if next_page_token:
            params['pageToken'] = next_page_token

        data = self._make_request(search_url, params)

        video_ids = [
            item['id']['videoId']
            for item in data.get('items', [])
            if item.get('id', {}).get('videoId')
        ]

        return video_ids, data.get('nextPageToken')

    def get_video_details(self, video_ids: List[str]) -> Dict[str, Dict]:
        """Get detailed information for videos"""
        if not video_ids:
            return {}

        video_url = 'https://www.googleapis.com/youtube/v3/videos'

        params = {
            'part': 'snippet,statistics,contentDetails',
            'id': ','.join(video_ids)
        }

        data = self._make_request(video_url, params)

        return {
            video['id']: video
            for video in data.get('items', [])
        }

    def get_suggestions(self, query: str) -> List[str]:
        """Get search suggestions from Google"""
        try:
            response = requests.get(
                "https://suggestqueries.google.com/complete/search",
                params={"client": "firefox", "ds": "yt", "q": query},
                timeout=5
            )
            data = response.json()
            suggestions = data[1] if isinstance(data, list) and len(data) > 1 else []
            return list(dict.fromkeys([query] + suggestions))
        except Exception as e:
            log_upgrade(f"Error getting suggestions: {e}")
            return [query]
