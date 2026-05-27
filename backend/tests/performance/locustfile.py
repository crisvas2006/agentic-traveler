import os
import random
from locust import HttpUser, task, between
from dotenv import load_dotenv

# Load .env file with override=True to align with uvicorn's loading behavior
load_dotenv(override=True)

class BaseTelegramUser(HttpUser):
    abstract = True  # Instruct Locust not to spawn this class directly
    
    def on_start(self):
        """Configure test context and headers."""
        self.secret_token = os.getenv("TELEGRAM_SECRET_TOKEN", "perf_test_secret")
        self.headers = {
            "Content-Type": "application/json",
            "X-Telegram-Bot-Api-Secret-Token": self.secret_token
        }
        self.chat_id = random.randint(10000000, 99999999)

    @task(1)
    def test_health_check(self):
        """Verify baseline HTTP server capability."""
        self.client.get("/health")

    @task(10)
    def test_casual_chat(self):
        """Simulate sending normal conversational queries."""
        payload = {
            "update_id": random.randint(10000, 99999),
            "message": {
                "message_id": random.randint(100, 999),
                "from": {
                    "id": self.user_id,
                    "is_bot": False,
                    "first_name": "VU",
                    "username": f"vu_{self.user_id}"
                },
                "chat": {
                    "id": self.chat_id,
                    "type": "private"
                },
                "text": random.choice([
                    "Hello bot!",
                    "How are you doing today?",
                    "Tell me a travel joke!",
                    "Who created you?"
                ])
            }
        }
        self.client.post(f"/webhook/{self.secret_token}", json=payload, headers=self.headers)

    @task(5)
    def test_travel_query(self):
        """Simulate heavy travel advisory query."""
        payload = {
            "update_id": random.randint(10000, 99999),
            "message": {
                "message_id": random.randint(100, 999),
                "from": {
                    "id": self.user_id,
                    "is_bot": False,
                    "first_name": "VU",
                },
                "chat": {
                    "id": self.chat_id,
                    "type": "private"
                },
                "text": "Recommend 3 nice beaches in Bali, under $1000 budget."
            }
        }
        self.client.post(f"/webhook/{self.secret_token}", json=payload, headers=self.headers)


class NormalTelegramUser(BaseTelegramUser):
    weight = 95
    wait_time = between(8, 15)  # Realistic conversational delays

    def on_start(self):
        super().on_start()
        # Generate a distinct user ID
        self.user_id = f"normal_{random.randint(100000, 999999)}"


class SpammerTelegramUser(BaseTelegramUser):
    weight = 5
    wait_time = between(0.5, 1.5)  # Aggressive rapid-fire spamming

    def on_start(self):
        super().on_start()
        # Generate a distinct user ID
        self.user_id = f"spammer_{random.randint(100000, 999999)}"

