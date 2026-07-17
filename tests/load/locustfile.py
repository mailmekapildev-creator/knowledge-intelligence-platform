"""
Load test for the query endpoint using Locust. Run with:
    pip install locust
    locust -f tests/load/locustfile.py --host=http://localhost:8000

See docs/cost-and-scalability.md for what this is intended to reveal (the reranker and
DB connection pool are the expected bottlenecks before the LLM call itself, at moderate
concurrency).
"""
from locust import HttpUser, between, task

QUESTIONS = [
    "How many vacation days do employees get?",
    "What is the remote work policy?",
    "How much can I expense for meals while traveling?",
]


class KnowledgePlatformUser(HttpUser):
    wait_time = between(1, 3)
    token = None

    def on_start(self):
        resp = self.client.post(
            "/api/v1/admin/dev-token",
            params={"user_id": "load-test-user", "tenant_id": "load-test-tenant", "role": "contributor"},
        )
        self.token = resp.json()["access_token"]

    @task
    def ask_question(self):
        import random
        self.client.post(
            "/api/v1/query",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"query": random.choice(QUESTIONS), "tenant_id": "load-test-tenant"},
        )
