# ⚡ FastAPI CRUD App

A lightweight CRUD app — FastAPI + SQLite with a built-in UI.

## One-Click Deploy

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/9puB-q?referralCode=-Xd4K_&utm_medium=integration&utm_source=template&utm_campaign=generic)



## Run Locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://localhost:8000

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web UI |
| GET | `/api/items` | List items (`?q=` search, `?skip=` `?limit=`) |
| POST | `/api/items` | Create item |
| GET | `/api/items/{id}` | Get item |
| PUT | `/api/items/{id}` | Update item |
| DELETE | `/api/items/{id}` | Delete item |
| GET | `/api/stats` | Item counts |
| GET | `/docs` | Swagger UI |
