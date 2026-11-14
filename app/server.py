"""HTTP API and static file server.

Run with:  python -m uvicorn app.server:app --port 8000
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agent, config, db, engine, explore, insights, mortgage, quiz, replay, tools
from .engine import EngineError


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    yield


app = FastAPI(title="Money Mentor", version="0.1.0", lifespan=lifespan)


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except EngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "today": db.today().isoformat(), **agent.describe()}


@app.get("/api/personas")
def personas() -> list[dict]:
    return insights.personas()


@app.get("/api/customers/{customer_id}/overview")
def overview(customer_id: str) -> dict:
    return _guard(engine.overview, customer_id)


@app.get("/api/customers/{customer_id}/baskets")
def basket_view(customer_id: str, period: str = "last_3_months") -> dict:
    return _guard(engine.basket_summary, customer_id, period)


@app.get("/api/customers/{customer_id}/cashflow")
def cashflow(customer_id: str, months: int = 6) -> dict:
    return _guard(engine.cashflow, customer_id, months)


@app.get("/api/customers/{customer_id}/safe-to-spend")
def safe_to_spend(customer_id: str, savings_goal_pct: float = engine.DEFAULT_SAVINGS_GOAL_PCT) -> dict:
    return _guard(engine.safe_to_spend, customer_id, savings_goal_pct)


@app.get("/api/customers/{customer_id}/profile")
def profile(customer_id: str) -> dict:
    return _guard(insights.spender_profile, customer_id)


@app.get("/api/customers/{customer_id}/replay")
def replay_year(customer_id: str, lever: str | None = None) -> dict:
    return _guard(replay.replay, customer_id, lever)


@app.get("/api/customers/{customer_id}/quiz")
def basket_quiz(customer_id: str) -> dict:
    return _guard(quiz.basket_quiz, customer_id)


@app.get("/api/customers/{customer_id}/notices")
def notices(customer_id: str, limit: int = 4) -> dict:
    return _guard(insights.notices, customer_id, limit)


@app.get("/api/customers/{customer_id}/benchmark")
def benchmark(customer_id: str, target: str | None = None, peer_group: str = "age") -> dict:
    return _guard(insights.benchmark, customer_id, target, peer_group)


@app.get("/api/customers/{customer_id}/mortgage")
def mortgage_view(customer_id: str, property_price: float | None = None, own_money: float | None = None) -> dict:
    return _guard(mortgage.readiness, customer_id, property_price, own_money)


@app.get("/api/customers/{customer_id}/mortgage/application")
def mortgage_application(customer_id: str) -> dict:
    return _guard(mortgage.application_timeline, customer_id)


@app.get("/api/explore/schema")
def explore_schema() -> dict:
    return explore.schema()


@app.get("/api/baskets/rules")
def basket_rules() -> dict:
    return engine.basket_rules()


class ToolCall(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


@app.post("/api/customers/{customer_id}/tools/{name}")
def run_tool(customer_id: str, name: str, body: ToolCall) -> dict:
    """Run any engine tool directly. The app's cards and the explore screen use this."""
    _guard(engine.customer, customer_id)
    if name not in tools.TOOL_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown tool '{name}'.")
    result = tools.call(customer_id, name, body.arguments)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class ChatMessage(BaseModel):
    role: str
    content: str


MAX_IMAGE_CHARS = 4_000_000  # a data URL of roughly 3 MB of image


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list)
    # Optional photo (price tag, receipt, bill) as a data URL: data:image/jpeg;base64,...
    image: str | None = Field(default=None, max_length=MAX_IMAGE_CHARS)


@app.post("/api/customers/{customer_id}/chat")
def chat(customer_id: str, body: ChatRequest) -> StreamingResponse:
    """Chat as a stream of server-sent events: tool_call, tool_result, answer."""
    cid = _guard(engine.customer, customer_id)["customer_id"]
    history = [m.model_dump() for m in body.history]
    image = body.image
    if image and not image.startswith(("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")):
        raise HTTPException(status_code=400, detail="image must be a JPEG, PNG or WebP data URL.")

    def events():
        try:
            for event in agent.run(cid, body.message, history, image=image):
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        except Exception as exc:  # keep the stream well-formed whatever happens
            payload = {"type": "error", "message": f"Something went wrong: {exc.__class__.__name__}"}
            yield f"data: {json.dumps(payload)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class FreshStaticFiles(StaticFiles):
    """Static files that the browser must revalidate before reuse.

    There is no build step and no hashed file names, so without this a browser
    can keep running an old script after the file changed. With ``no-cache`` it
    asks each time and gets a short 304 when nothing changed.
    """

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


if config.WEB_DIR.exists():
    app.mount("/assets", FreshStaticFiles(directory=config.WEB_DIR), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        """The demo page: the story, the tour, and the phone."""
        return FileResponse(config.WEB_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    @app.get("/app")
    def phone() -> FileResponse:
        """The app itself. The demo page shows it inside the phone; a real phone opens it directly."""
        return FileResponse(config.WEB_DIR / "phone.html", headers={"Cache-Control": "no-cache"})
