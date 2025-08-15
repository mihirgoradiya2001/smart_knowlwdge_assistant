import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.auth import router as auth_router
from routers.documents import router as documents_router
from routers.rag import router as rag_router
from routers.history import router as history_router
from utils.logging_config import init_logging, install_request_logging
from utils.exception_handlers import install_exception_handlers

app = FastAPI(
    title="Smart Knowledge Assistant API",
    description="Backend API for document upload, knowledge base creation, and contextual Q&A using RAG.",
    version="1.0.0"
)

# Initialize logging and request middleware
init_logging()
install_request_logging(app)
install_exception_handlers(app)

app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(rag_router)
app.include_router(history_router)

# CORS settings (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include your routers here (to be created)
# from routers import auth, documents, rag, history
# app.include_router(auth.router)
# app.include_router(documents.router)
# app.include_router(rag.router)
# app.include_router(history.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Smart Knowledge Assistant API"}
