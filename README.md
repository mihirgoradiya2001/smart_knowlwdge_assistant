# Smart Knowledge Assistant API

A secure, modular, and scalable backend system that allows users to upload knowledge documents, generate a custom knowledge base using vector embeddings, and retrieve contextual answers using RAG (Retrieval Augmented Generation).

## Features Implemented

- **Document Upload & Processing**: Support for PDF, TXT, and Markdown files with validation
- **JWT Authentication**: Secure user registration and login with JWT tokens
- **RAG (Retrieval Augmented Generation)**: Ask questions and get context-rich answers from uploaded documents
- **Question History**: Track and retrieve user's question history with pagination
- **Daily Usage Limits**: Enforce daily question limits per user (configurable)
- **Asynchronous Processing**: Background document processing with Celery + Redis
- **Structured Logging**: JSON logs with rotation, correlation IDs, and user context
- **Input Validation**: File format, size, and content validation
- **Error Handling**: Centralized exception handling with standardized responses
- **Unit Tests**: Comprehensive test suite with pytest

## Tech Stack

- **Backend**: FastAPI
- **Authentication**: JWT (JSON Web Tokens)
- **Vector Database**: FAISS
- **Embeddings**: HuggingFace Sentence Transformers
- **Async Processing**: Celery + Redis
- **Document Parsing**: PyPDF, LangChain
- **Testing**: pytest
- **Logging**: Structured JSON logs with rotation

## Prerequisites

- Python 3.8+
- Redis server
- Virtual environment (recommended)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd smart_knowledge_assistant
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Environment Variables

Create a `.env` file with the following variables:

```env
# JWT Configuration
JWT_SECRET=your_jwt_secret_here

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# File Storage
FAISS_INDEX_PATH=faiss_indexes/
STATE_DIR=state/
LOG_DIR=logs/

# Upload Limits
MAX_UPLOAD_MB=25

# Usage Limits
FREE_DAILY_QUESTION_LIMIT=20

# Logging
LOG_LEVEL=INFO
LOG_BACKUP_COUNT=7

# Optional: Use fake embeddings for testing
USE_FAKE_EMBEDDINGS=0
```

## Running the Application

1. **Start Redis server**
   ```bash
   # Using Docker
   docker run -d --name redis -p 6379:6379 redis:7
   
   # Or using system Redis
   redis-server --port 6379
   ```

2. **Start Celery worker** (in a new terminal)
   ```bash
   cd smart_knowledge_assistant
   source venv/bin/activate
   celery -A tasks.celery_app.celery_app worker --loglevel=info
   ```

3. **Start the API server** (in another terminal)
   ```bash
   cd smart_knowledge_assistant
   source venv/bin/activate
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Access the API documentation**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## API Endpoints

### Authentication

#### Register User
```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure_password"
}
```

#### Login
```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure_password"
}
```

Response includes JWT token:
```json
{
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer"
  },
  "message": "Login successful",
  "status_code": 200
}
```

### Document Management

#### Upload Document
```http
POST /documents/upload
Authorization: Bearer <your_jwt_token>
Content-Type: multipart/form-data

file: <your_document.pdf>
```

Supported formats: PDF, TXT, MD
Max file size: Configurable via `MAX_UPLOAD_MB`

### RAG (Question Answering)

#### Ask Question
```http
POST /rag/ask?doc_id=1&question=What is this document about?
Authorization: Bearer <your_jwt_token>
```

Response:
```json
{
  "data": {
    "answer": "This is a stubbed answer for: 'What is this document about?'...",
    "context": ["Chunk one", "Chunk two", "Chunk three"]
  },
  "message": "Answer generated successfully.",
  "status_code": 200
}
```

### History

#### Get Question History
```http
GET /history?date=2025-08-15&offset=0&limit=20
Authorization: Bearer <your_jwt_token>
```

Response:
```json
{
  "data": {
    "items": [
      {
        "id": "uuid",
        "timestamp": "2025-08-15T10:30:00Z",
        "user_id": 1,
        "doc_id": 1,
        "question": "What is this about?",
        "answer": "Answer text...",
        "context_preview": "Context preview...",
        "top_k": 3,
        "chunk_indices": [0, 1, 2]
      }
    ],
    "total": 1,
    "date": "2025-08-15",
    "offset": 0,
    "limit": 20
  },
  "message": "History fetched successfully.",
  "status_code": 200
}
```

## Usage Examples

### Complete Workflow

1. **Register and login**
   ```bash
   curl -X POST "http://localhost:8000/auth/register" \
     -H "Content-Type: application/json" \
     -d '{"email":"user@example.com","password":"password123"}'
   
   curl -X POST "http://localhost:8000/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email":"user@example.com","password":"password123"}'
   ```

2. **Upload a document**
   ```bash
   TOKEN="your_jwt_token_here"
   curl -X POST "http://localhost:8000/documents/upload" \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@/path/to/your/document.pdf"
   ```

3. **Ask a question** (after document processing completes)
   ```bash
   curl -X POST "http://localhost:8000/rag/ask?doc_id=1&question=What%20is%20this%20document%20about%3F" \
     -H "Authorization: Bearer $TOKEN"
   ```

4. **View history**
   ```bash
   curl -X GET "http://localhost:8000/history" \
     -H "Authorization: Bearer $TOKEN"
   ```

## File Structure

```
smart_knowledge_assistant/
├── main.py                 # FastAPI application entry point
├── routers/               # API route handlers
│   ├── auth.py           # Authentication endpoints
│   ├── documents.py      # Document upload endpoints
│   ├── rag.py           # RAG question answering
│   └── history.py       # History management
├── models/               # Pydantic models
│   ├── user.py          # User models
│   ├── document.py      # Document models
│   └── response.py      # Response models
├── utils/               # Utility functions
│   ├── jwt.py          # JWT token handling
│   ├── response.py     # Response formatting
│   ├── history.py      # History management
│   ├── logging_config.py # Logging configuration
│   └── exception_handlers.py # Error handling
├── tasks/               # Celery background tasks
│   ├── celery_app.py   # Celery configuration
│   └── celery_tasks.py # Document processing tasks
├── tests/               # Unit tests
│   ├── conftest.py     # Test configuration
│   ├── test_auth.py    # Authentication tests
│   ├── test_documents.py # Document tests
│   └── test_rag_and_history.py # RAG and history tests
├── uploads/             # Uploaded files storage
├── faiss_indexes/       # FAISS vector indices
├── state/               # Application state (history, usage)
├── logs/                # Application logs
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables
└── README.md           # This file
```

## Testing

Run the test suite:

```bash
# Install test dependencies
pip install pytest

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_auth.py

# Run with coverage
pytest --cov=.
```

## Logging

The application uses structured JSON logging with the following features:

- **Log files**: `logs/app.log`, `logs/error.log`, `logs/tasks.log`
- **Rotation**: Daily rotation with configurable backup count
- **Correlation IDs**: Each request gets a unique correlation ID
- **User context**: User ID is included in logs when available
- **Structured format**: JSON logs for easy parsing

Example log entry:
```json
{
  "timestamp": "2025-08-15T10:30:00Z",
  "level": "INFO",
  "logger": "api.auth",
  "message": "login_success",
  "correlation_id": "abc123",
  "user_id": 1,
  "email": "u***@example.com"
}
```

## Error Handling

The application includes centralized error handling:

- **HTTP Exceptions**: Standardized JSON responses
- **Validation Errors**: Detailed validation error messages
- **Internal Errors**: Generic error messages (no sensitive data leakage)
- **Logging**: All errors are logged with context

## Security Features

- **JWT Authentication**: Secure token-based authentication
- **Input Validation**: File type, size, and content validation
- **Rate Limiting**: Daily question limits per user
- **Secure Logging**: Sensitive data is masked/hashed in logs
- **CORS**: Configurable CORS settings

## Performance Considerations

- **Asynchronous Processing**: Document processing runs in background
- **Vector Search**: Efficient FAISS-based similarity search
- **File Locking**: Thread-safe file operations for history/usage
- **Caching**: In-process usage caching for performance

## Troubleshooting

### Common Issues

1. **Redis Connection Error**
   - Ensure Redis server is running
   - Check `REDIS_URL` in `.env`

2. **Document Processing Fails**
   - Check Celery worker is running
   - Verify file format is supported
   - Check logs in `logs/tasks.log`

3. **Authentication Errors**
   - Verify JWT token is valid and not expired
   - Check `JWT_SECRET` in `.env`

4. **Daily Limit Exceeded**
   - Wait until UTC midnight for reset
   - Check current usage via `/history` endpoint

### Log Locations

- Application logs: `logs/app.log`
- Error logs: `logs/error.log`
- Task logs: `logs/tasks.log`