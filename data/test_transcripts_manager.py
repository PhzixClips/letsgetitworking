import unittest
import os
import shutil
from pathlib import Path
import json

from data.transcripts_manager import TranscriptsManager
from data.settings_manager import settings_manager

class TestTranscriptsManager(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory for testing."""
        self.test_dir = Path("test_transcripts")
        self.test_dir.mkdir(exist_ok=True)
        settings_manager.set("transcripts_path", str(self.test_dir))
        self.tm = TranscriptsManager()

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.test_dir)

    def test_save_and_exists(self):
        """Test saving a transcript and checking for its existence."""
        record = {
            "video_id": "test001",
            "title": "Test Video",
            "text": "This is a test transcript."
        }
        self.tm.save(record)
        self.assertTrue(self.tm.exists("test001"))
        self.assertTrue((self.test_dir / "test001.json").exists())
        self.assertTrue((self.test_dir / "test001.txt").exists())

    def test_load(self):
        """Test loading a transcript."""
        record = {
            "video_id": "test002",
            "title": "Test Video 2",
            "text": "Another test transcript."
        }
        self.tm.save(record)
        loaded_record = self.tm.load("test002")
        self.assertIsNotNone(loaded_record)
        self.assertEqual(loaded_record["title"], "Test Video 2")

    def test_delete(self):
        """Test deleting a transcript."""
        record = {
            "video_id": "test003",
            "title": "Test Video 3",
            "text": "This will be deleted."
        }
        self.tm.save(record)
        self.assertTrue(self.tm.exists("test003"))
        self.tm.delete("test003")
        self.assertFalse(self.tm.exists("test003"))
        self.assertFalse((self.test_dir / "test003.json").exists())
        self.assertFalse((self.test_dir / "test003.txt").exists())

    def test_combine_text(self):
        """Test combining multiple transcripts."""
        record1 = {"video_id": "vid1", "title": "First Video", "text": "Hello world."}
        record2 = {"video_id": "vid2", "title": "Second Video", "text": "Goodbye world."}
        self.tm.save(record1)
        self.tm.save(record2)

        combined = self.tm.combine_text(["vid1", "vid2"])
        expected = (
            "==== First Video (vid1) ====\nHello world.\n\n"
            "==== Second Video (vid2) ====\nGoodbye world.\n\n"
        )
        self.assertEqual(combined, expected)

    def test_search(self):
        """Test searching transcripts."""
        record1 = {"video_id": "search1", "title": "Apple Video", "folder": "Fruit", "tags": ["#red"], "text": "A video about apples."}
        record2 = {"video_id": "search2", "title": "Banana Video", "folder": "Fruit", "tags": ["#yellow"], "text": "A video about bananas."}
        record3 = {"video_id": "search3", "title": "Carrot Video", "folder": "Veggies", "tags": ["#orange"], "text": "A video about carrots."}
        self.tm.save(record1)
        self.tm.save(record2)
        self.tm.save(record3)

        # Search by query
        results = self.tm.search(query="apple")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["video_id"], "search1")

        # Search by folder
        results = self.tm.search(folder="Fruit")
        self.assertEqual(len(results), 2)

        # Search by query and folder
        results = self.tm.search(query="banana", folder="Fruit")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["video_id"], "search2")

        # Search by tag
        results = self.tm.search(query="#orange")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["video_id"], "search3")


if __name__ == '__main__':
    unittest.main()
