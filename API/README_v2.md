# Argos API v2 - Neo4j Based Research API

## Overview

Argos API v2 is a complete rewrite that uses Neo4j as the backend instead of ChromaDB/file systems. It provides user-based access control to research topics with integrated chat functionality.

## Key Features

- **User Authentication**: Simple username/password authentication
- **Topic-Based Access**: Users can only access their assigned topics
- **Neo4j Integration**: All data comes from Neo4j graph database
- **Intelligent Chat**: Topic-aware chat with full context (articles + reports)
- **Real-time Reports**: Uses `aggregate_reports()` for live report generation

## Quick Start

### 1. Start the API Server

```bash
cd API
python api_main_v2.py
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs

### 2. Run Tests

```bash
python test_api_v2.py
```

## API Endpoints

### Authentication

#### POST /login
Authenticate user and get accessible topics.

**Request:**
```json
{
  "username": "Victor",
  "password": "v123"
}
```

**Response:**
```json
{
  "username": "Victor",
  "accessible_topics": ["oil-price-decline", "boeing", "us-crude-inventories", ...]
}
```

### Topics (Interests)

#### GET /interests?username=Victor
Get list of topics accessible to a user.

**Response:**
```json
{
  "interests": [
    {"id": "oil-price-decline", "name": "Oil Price Decline"},
    {"id": "boeing", "name": "Boeing"},
    ...
  ]
}
```

### Articles

#### GET /articles?topic_id=oil-price-decline&limit=10
Get articles for a specific topic.

**Response:**
```json
{
  "articles": [
    {
      "id": "ABC123",
      "title": "Oil Prices Drop Amid Supply Concerns",
      "summary": "Oil prices fell 3% today...",
      "url": "https://example.com/article",
      "published_date": "2025-01-15"
    }
  ]
}
```

#### GET /articles/{article_id}
Get full article content by ID.

### Reports

#### GET /reports/{topic_id}?format=markdown|json
Get complete analysis report for a topic using `aggregate_reports()`.

**Parameters:**
- `format` (optional): `markdown` (default) or `json`

**Default Markdown Response:**
```json
{
  "topic_id": "brent",
  "topic_name": "Brent Crude Oil",
  "markdown": "# Brent Crude Oil\n\n## Executive Summary\n\nOil prices have declined...\n\n## Fundamental Analysis\n\nSupply factors include..."
}
```

**JSON Response (with ?format=json):**
```json
{
  "topic_id": "brent",
  "topic_name": "Brent Crude Oil",
  "sections": {
    "executive_summary": "Oil prices have declined...",
    "fundamental_analysis": "Supply factors include...",
    "current_analysis": "Recent developments...",
    ...
  }
}
```

The markdown format is ready for Svelte's `simpleMarkdown` function:
- `# Header` → `<h1>`
- `## Header` → `<h2>`
- `### Header` → `<h3>`

### Chat

#### POST /chat
Chat about a specific topic with full context.

**Request:**
```json
{
  "message": "What's driving oil prices down?",
  "topic_id": "oil-price-decline",
  "history": [
    {"role": "user", "content": "Previous message"},
    {"role": "assistant", "content": "Previous response"}
  ]
}
```

**Response:**
```json
{
  "response": "Based on the latest analysis, oil prices are declining due to...",
  "topic_id": "oil-price-decline"
}
```

### Health

#### GET /health
Check API and Neo4j connection status.

## User Management

Users are defined in `users.json`:

```json
{
  "users": [
    {
      "username": "Victor",
      "password": "v123",
      "accessible_topics": ["oil-price-decline", "boeing", ...]
    },
    {
      "username": "William",
      "password": "w456", 
      "accessible_topics": ["boeing", "us-services-pmi", ...]
    }
  ]
}
```

## Architecture Changes from v1

| Feature | v1 (Old) | v2 (New) |
|---------|----------|----------|
| **Data Source** | ChromaDB + Files | Neo4j Graph Database |
| **Authentication** | None | Username/Password |
| **Access Control** | None | Topic-based per user |
| **Articles** | ChromaDB collections | Neo4j + `load_article()` |
| **Reports** | File-based markdown | `aggregate_reports()` |
| **Chat Context** | Single report file | Full topic context (articles + reports) |
| **Insights** | Separate endpoint | Removed (consolidated into reports) |

## Frontend Integration

The API is designed for a simple frontend flow:

1. **Login**: User enters credentials → get accessible topics
2. **Topic List**: Show user's interests as clickable cards
3. **Topic View**: Click interest → show articles + report
4. **Article Reading**: Click article → show full content
5. **Chat**: Chat about the topic with full context

## Development Notes

- **No Write Operations**: API is read-only for users
- **Demo Authentication**: Simple username/password (not production-ready)
- **Error Handling**: Comprehensive error responses
- **CORS Enabled**: Ready for frontend integration
- **Type Safety**: Full Pydantic models for requests/responses

## Next Steps

1. **Enhanced Authentication**: JWT tokens, session management
2. **User Management UI**: Admin interface for user/topic management  
3. **Real-time Updates**: WebSocket support for live data
4. **Caching**: Redis caching for frequently accessed data
5. **Rate Limiting**: API usage limits per user
