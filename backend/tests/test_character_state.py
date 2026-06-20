import unittest
from unittest.mock import patch
import sqlite3

# Import the module to test
from backend.services.character_state import CharacterStateManager

class TestCharacterStateManager(unittest.TestCase):
    def setUp(self):
        # Create an in-memory SQLite database for testing using shared cache
        # Use a unique ID for each test to prevent test pollution and locking across tests
        import uuid
        self.db_uri = f"file:memdb_{uuid.uuid4().hex}?mode=memory&cache=shared"
        self.conn = sqlite3.connect(self.db_uri, uri=True, timeout=10.0)
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()

        # Initialize the affection table schema
        cursor.execute("""
        CREATE TABLE affection (
            id INTEGER PRIMARY KEY,
            value INTEGER DEFAULT 50,
            social_status INTEGER DEFAULT 50,
            social_skills INTEGER DEFAULT 50,
            refractory_period INTEGER DEFAULT 0,
            last_updated DATETIME
        );
        """)
        self.conn.commit()

        # Patch get_db_connection to return a new connection to the shared DB
        def mock_get_db():
            conn = sqlite3.connect(self.db_uri, uri=True, timeout=10.0)
            conn.row_factory = sqlite3.Row
            return conn

        self.db_patcher = patch('backend.services.character_state.get_db_connection', side_effect=mock_get_db)
        self.mock_get_db = self.db_patcher.start()

    def tearDown(self):
        self.db_patcher.stop()
        self.conn.close()

    def test_get_state_empty_db(self):
        """Test getting state when DB is empty returns defaults."""
        state = CharacterStateManager.get_state()
        self.assertEqual(state.affection, 50)
        self.assertEqual(state.social_status, 50)
        self.assertEqual(state.social_skills, 50)
        self.assertEqual(state.refractory_period, 0)

    def test_update_state_empty_db_initializes(self):
        """Test updating state when DB is empty initializes it first."""
        # Update affection by +10
        state = CharacterStateManager.modify_state(affection_delta=10)

        # It should start at 50, so +10 makes it 60
        self.assertEqual(state.affection, 60)
        self.assertEqual(state.social_status, 50)
        self.assertEqual(state.social_skills, 50)
        self.assertEqual(state.refractory_period, 0)

        # Verify it was written to DB
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM affection WHERE id = 1")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["value"], 60)

    def test_update_state_bounds(self):
        """Test that values are constrained to their bounds (0-100 for most, >=0 for refractory)."""
        # Initialize with known values
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO affection (id, value, social_status, social_skills, refractory_period) VALUES (1, 95, 10, 90, 2)")
        self.conn.commit()

        # Try to exceed upper bounds
        state = CharacterStateManager.modify_state(
            affection_delta=10,       # 95 + 10 = 105 -> 100
            social_status_delta=100,  # 10 + 100 = 110 -> 100
            social_skills_delta=20    # 90 + 20 = 110 -> 100
        )
        self.assertEqual(state.affection, 100)
        self.assertEqual(state.social_status, 100)
        self.assertEqual(state.social_skills, 100)

        # Try to exceed lower bounds
        state = CharacterStateManager.modify_state(
            affection_delta=-150,     # 100 - 150 = -50 -> 0
            social_status_delta=-200, # 100 - 200 = -100 -> 0
            social_skills_delta=-50,  # 100 - 50 = 50
            refractory_delta=-5       # 2 - 5 = -3 -> 0
        )
        self.assertEqual(state.affection, 0)
        self.assertEqual(state.social_status, 0)
        self.assertEqual(state.social_skills, 50)
        self.assertEqual(state.refractory_period, 0)

    def test_trigger_climax(self):
        """Test that trigger_climax sets the refractory period."""
        # Should initialize DB and set refractory to 10
        state = CharacterStateManager.trigger_climax(intensity=10)
        self.assertEqual(state.refractory_period, 10)

        # Check DB
        cursor = self.conn.cursor()
        cursor.execute("SELECT refractory_period FROM affection WHERE id = 1")
        self.assertEqual(cursor.fetchone()[0], 10)

    def test_advance_round(self):
        """Test that advance_round decreases the refractory period."""
        # Setup initial state
        CharacterStateManager.trigger_climax(intensity=5)

        # Advance 2 rounds
        state = CharacterStateManager.advance_round(rounds=2)
        self.assertEqual(state.refractory_period, 3)

        # Advance 10 rounds (should floor at 0)
        state = CharacterStateManager.advance_round(rounds=10)
        self.assertEqual(state.refractory_period, 0)

    @patch('backend.services.character_state.get_db_connection')
    def test_db_error_raises_exception(self, mock_db):
        """Test that DB errors raise CharacterStateError."""
        mock_db.side_effect = sqlite3.Error("Mock DB Error")

        from backend.services.character_state import CharacterStateError
        with self.assertRaises(CharacterStateError):
            CharacterStateManager.get_state()

        with self.assertRaises(CharacterStateError):
            CharacterStateManager.modify_state(affection_delta=10)

    def test_concurrent_updates(self):
        """Test that concurrent updates do not cause race conditions (data loss)."""
        # Ensure initial state is 0 for affection
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO affection (id, value, social_status, social_skills, refractory_period, last_updated) VALUES (1, 0, 50, 50, 0, datetime('now'))")
        self.conn.commit()

        import threading

        def worker():
            CharacterStateManager.modify_state(affection_delta=10)

        threads = []
        # Spawn 10 threads, each adding 10. Total should be 100.
        for _ in range(10):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        final_state = CharacterStateManager.get_state()
        self.assertEqual(final_state.affection, 100)

if __name__ == '__main__':
    unittest.main()
