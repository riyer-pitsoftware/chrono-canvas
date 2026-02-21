import httpx

DEFAULT_BASE_URL = "http://localhost:8000/api"


class ChronoCanvasClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL):
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=30.0)

    def health(self) -> dict:
        return self.client.get("/health").json()

    # Figures
    def list_figures(self, offset: int = 0, limit: int = 50, search: str | None = None) -> dict:
        params = {"offset": offset, "limit": limit}
        if search:
            params["search"] = search
        return self.client.get("/figures", params=params).json()

    def get_figure(self, figure_id: str) -> dict:
        return self.client.get(f"/figures/{figure_id}").json()

    def create_figure(self, data: dict) -> dict:
        resp = self.client.post("/figures", json=data)
        resp.raise_for_status()
        return resp.json()

    # Generation
    def generate(self, input_text: str, figure_id: str | None = None) -> dict:
        data = {"input_text": input_text}
        if figure_id:
            data["figure_id"] = figure_id
        resp = self.client.post("/generate", json=data)
        resp.raise_for_status()
        return resp.json()

    def batch_generate(self, items: list[dict]) -> dict:
        resp = self.client.post("/generate/batch", json={"items": items})
        resp.raise_for_status()
        return resp.json()

    def get_generation(self, request_id: str) -> dict:
        return self.client.get(f"/generate/{request_id}").json()

    def list_generations(self, offset: int = 0, limit: int = 20) -> dict:
        return self.client.get("/generate", params={"offset": offset, "limit": limit}).json()

    # Validation
    def get_validation(self, request_id: str) -> dict:
        return self.client.get(f"/validation/{request_id}").json()

    # Export
    def download_image(self, request_id: str) -> bytes:
        resp = self.client.get(f"/export/{request_id}/download")
        resp.raise_for_status()
        return resp.content

    # Agents
    def list_agents(self) -> dict:
        return self.client.get("/agents").json()

    def llm_status(self) -> dict:
        return self.client.get("/agents/llm-status").json()

    def cost_summary(self) -> dict:
        return self.client.get("/agents/costs").json()
