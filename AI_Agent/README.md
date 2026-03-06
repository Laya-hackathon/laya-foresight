# Laya Foresight AI Agent Server (Backend)

This repository contains the backend server for the Laya Foresight project. The server hosts a FastAPI application that runs an AI agent (to simulate support escalation preventions) and streams reasoning events to the frontend dashboard.

## Prerequisites

- **Python 3.8+**
- **pip** package manager

## Setup and Installation

### 1. Clone the Repository
Clone the backend repository to your local machine:
```bash
git clone https://github.com/Laya-hackathon/laya-foresight.git
cd "laya-foresight/AI Agent"
```

### 2. Create a Virtual Environment (Recommended)
It's a best practice to keep your Python dependencies isolated.
```bash
python3 -m venv venv
```

**Activate the virtual environment:**
- **Mac/Linux:**
  ```bash
  source venv/bin/activate
  ```
- **Windows:**
  ```bash
  venv\Scripts\activate
  ```

### 3. Install Dependencies
Install the required packages using pip:
```bash
pip install -r requirements.txt
```
*(Dependencies include FastAPI, Uvicorn, Python-Dotenv, and Anthropic's SDK)*

### 4. Environment Variables
Create a `.env` file in the root of the backend folder (`AI Agent`) and add the necessary configuration. Example:
```env
GITHUB_TOKEN=your_github_token_here
MODEL=gpt-4o-mini
```
*Note: Make sure to replace `your_github_token_here` with a valid token.*

## Running Locally

Start the FastAPI application directly:
```bash
python server.py
```

Alternatively, you can run it directly with Uvicorn:
```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

The standard backend API will run on **`http://localhost:8000`**.



## Key API Endpoints
- `GET /` : Serves a built-in demo dashboard (if using the bundled HTML).
- `GET /api/health` : Checks server status, API token configuration, and selected model.
- `GET /api/scenarios` : Lists all available simulation scenarios.
- `GET /api/run/{scenario_id}` : Starts an agent session for a given scenario, streaming output via Server-Sent Events (SSE).
- `GET /api/run-all` : Runs all test scenarios sequentially.
