from locust import HttpUser, task, between

class HigalaExpressUser(HttpUser):
    # Specify your local FastAPI server base URL
    host = "http://127.0.0.1:8000"

    # Wait between 1 and 3 seconds between simulated requests
    wait_time = between(1, 3)

    def on_start(self):
        """Setup run when a simulated user starts (e.g., login or token fetch)"""
        self.token = None
        # Example login mock to retrieve a real token for secured endpoints:
        # response = self.client.post("/auth/login", json={"username": "testuser", "password": "password"})
        # if response.status_code == 200:
        #     self.token = response.json().get("access_token")

    @task(3)
    def health_check(self):
        """Test deep system and connection pool health check"""
        self.client.get("/health", name="/health")

    @task(2)
    def root_endpoint(self):
        """Test API Root Status"""
        self.client.get("/", name="/")

    @task(1)
    def browse_merchant_subscriptions(self):
        """Test merchant subscription endpoints"""
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        self.client.get("/merchants/subscriptions/1", headers=headers, name="/merchants/subscriptions/{id}")

    @task(1)
    def check_orders(self):
        """Test order history/retrieval endpoint"""
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        self.client.get("/api/orders/", headers=headers, name="/api/orders")

    @task(1)
    def test_transport(self):
        """Test transport router endpoints"""
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        self.client.get("/transport/", headers=headers, name="/transport")

    @task(1)
    def test_checkout(self):
        """Test checkout router endpoints"""
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        self.client.get("/checkout/", headers=headers, name="/checkout")

    @task(1)
    def test_admin_rbac(self):
        """Test admin dashboard RBAC roles endpoint"""
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        self.client.get("/api/admin/rbac/roles", headers=headers, name="/api/admin/rbac/roles")