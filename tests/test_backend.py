import importlib
import os
import tempfile
import unittest

from fastapi.testclient import TestClient


class HealthChatbotBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        os.environ["DATABASE_URL"] = f"sqlite:///{cls.temp_db.name}"
        cls.backend = importlib.import_module("backend.main")
        cls.backend = importlib.reload(cls.backend)
        cls.client = TestClient(cls.backend.app)

    @classmethod
    def tearDownClass(cls):
        cls.temp_db.close()
        os.unlink(cls.temp_db.name)

    def setUp(self):
        self.backend.Base.metadata.drop_all(bind=self.backend.engine)
        self.backend.Base.metadata.create_all(bind=self.backend.engine)

    def test_intake_stores_extracted_symptoms(self):
        response = self.client.post(
            "/chatbot/intake",
            headers={"X-User-Id": "user-123"},
            json={"message": "I have fever and cough for 2 days", "duration_days": 2},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        symptoms = [entry["symptom"] for entry in payload["stored_entries"]]
        self.assertIn("fever", symptoms)
        self.assertIn("cough", symptoms)

    def test_intake_requires_user_identifier(self):
        response = self.client.post(
            "/chatbot/intake",
            json={"message": "headache"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing user_id", response.text)


if __name__ == "__main__":
    unittest.main()
