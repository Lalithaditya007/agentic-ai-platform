# Universal Agentic AI Platform

A Universal Agentic AI Platform that dynamically creates, orchestrates, and deploys intelligent AI agents for any B2B customer discovery domain.

## What This Is

The platform is not hardcoded for a single business. It:
1. Understands any business from a natural language description
2. Generates an Ideal Customer Profile (ICP) and business rules automatically
3. Dynamically composes a unique AI agent workflow per business
4. Discovers, validates, and enriches target companies and contacts
5. Recommends the Next Best Action with full reasoning
6. Learns from human feedback to improve over time

**Demo use case:** B2B Customer Discovery for a cybersecurity company (CipherGuard Security)

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, Zustand |
| Backend | FastAPI, Python 3.11+ |
| Agentic Framework | LangGraph, LangChain |
| LLM | Google Gemini 2.0 Flash (free tier) |
| Database | PostgreSQL (local) |
| Cache | Redis (Upstash) |
| Vector DB | ChromaDB (embedded) |
| Search | Tavily API |
| Observability | LangSmith |

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL (local install)

### Setup

1. Clone the repo
2. Copy `.env.example` to `.env` and fill in your API keys
3. Create the database: `CREATE DATABASE platform_db;` in PostgreSQL
4. Start backend:
   ```bash
   cd backend
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   alembic upgrade head
   uvicorn main:app --reload
   ```
5. Start frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Project Structure

```
Project/
├── frontend/          # Next.js application
├── backend/           # FastAPI + LangGraph backend
├── docs/              # Implementation plan & API reference
├── tests/             # Backend unit tests + E2E tests
├── .env.example       # Environment variable template
└── README.md
```

## Architecture

```
Business Description → Business Understanding AI → ICP & Rules
→ User Review → Trigger Monitoring → Planner Agent
→ Agent Architect → Runtime Agents (Discovery, Validation, Enrichment, Contact, NBA, Brief)
→ Human-in-the-Loop Review → Feedback & Learning → Analytics Dashboard
```
