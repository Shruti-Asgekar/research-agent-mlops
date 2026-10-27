---
title: Research Brief Agent
emoji: 🔎
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8501
pinned: false
---

# Research Brief Agent (Experiment 10 - MLOps deployment)

A two-stage task-automation agent: **web search (DuckDuckGo) -> 3-bullet summary (LLM)**,
served with Streamlit, packaged with Docker, tested and deployed through GitHub Actions.

## Run locally
```bash
pip install -r requirements.txt
export GROQ_API_KEY="your-key"        # Windows PowerShell: $env:GROQ_API_KEY="your-key"
streamlit run app.py
```

## Run in Docker
```bash
docker build -t research-agent .
docker run --rm -p 8501:8501 -e GROQ_API_KEY="your-key" research-agent
```
Open http://localhost:8501

## Tests
```bash
pip install pytest
pytest -v
```

## Secrets
The API key is never stored in the code, image or repository. It is supplied as the
`GROQ_API_KEY` environment variable / platform secret.
