

import asyncio
import json
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from agent import run_agent_streaming
from mock_data import get_all_scenarios, get_scenario


app = FastAPI(title="LayaAIAgent Dashboard", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the main dashboard HTML."""
    html_path = Path(__file__).parent / "index.html"
    return HTMLResponse(content=html_path.read_text(), status_code=200)



@app.get("/api/scenarios")
async def list_scenarios():
    return {"scenarios": get_all_scenarios()}


@app.get("/api/run/{scenario_id}")
async def run_scenario_stream(scenario_id: str, request: Request):
    scenario = get_scenario(scenario_id)
    if not scenario:
        return {"error": f"Scenario {scenario_id} not found"}

    async def event_generator():
        import queue
        import threading

        q = queue.Queue()

        def run_in_thread():
            try:
                for event in run_agent_streaming(scenario):
                    q.put(event)
            except Exception as e:
                q.put({"type": "error", "data": {"message": str(e)}})
            finally:
                q.put(None)  

        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()

        while True:
            if await request.is_disconnected():
                break

            try:
                event = q.get_nowait()
            except queue.Empty:
                yield ": keepalive\n\n"
                await asyncio.sleep(0.1)
                continue

            if event is None:
                break

            payload = json.dumps(event)
            padding = " " * max(0, 1024 - len(payload))
            yield f"data: {payload}{padding}\n\n"
            await asyncio.sleep(0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Transfer-Encoding": "chunked",
        }
    )



@app.get("/api/run-all")
async def run_all_scenarios():

    async def event_generator():
        import queue
        import threading

        scenarios = get_all_scenarios()
        q = queue.Queue()

        def run_in_thread():
            try:
                for i, scenario_summary in enumerate(scenarios):
                    full_scenario = get_scenario(scenario_summary["id"])
                    q.put({
                        "type": "scenario_start",
                        "data": {
                            "scenario_id": scenario_summary["id"],
                            "name": scenario_summary["name"],
                            "index": i + 1,
                            "total": len(scenarios)
                        }
                    })
                    for event in run_agent_streaming(full_scenario):
                        event["data"]["scenario_id"] = scenario_summary["id"]
                        q.put(event)
            except Exception as e:
                q.put({"type": "error", "data": {"message": str(e)}})
            finally:
                q.put(None)

        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()

        while True:
            try:
                event = q.get(timeout=0.5)
            except queue.Empty:
                yield f": keepalive\n\n"
                continue

            if event is None:
                yield f"data: {json.dumps({'type': 'all_done', 'data': {}})}\n\n"
                break

            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/api/health")
async def health():
    """Health check."""
    return {
        "status": "ok",
        "api_key_configured": bool(os.getenv("GITHUB_TOKEN")),
        "model": os.getenv("MODEL", "openai/gpt-4.1-mini"),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
