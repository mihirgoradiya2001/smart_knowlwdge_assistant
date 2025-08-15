from .celery_app import celery_app
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import CharacterTextSplitter
import faiss
import os
import numpy as np
import logging

FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "faiss_indexes")
logger = logging.getLogger("tasks.documents")


def parse_document(file_path):
	ext = file_path.split('.')[-1].lower()
	text = ""
	if ext == "pdf":
		from pypdf import PdfReader
		reader = PdfReader(file_path)
		for page in reader.pages:
			text += page.extract_text() or ""
	elif ext in ["txt", "md"]:
		with open(file_path, "r", encoding="utf-8") as f:
			text = f.read()
	else:
		raise ValueError("Unsupported file format")
	return text


@celery_app.task
def process_document_task(doc_id, file_path):
	try:
		logger.info("task_started", extra={"doc_id": doc_id})
		# 1. Parse document
		text = parse_document(file_path)
		logger.info("parsed_document", extra={"doc_id": doc_id, "chars": len(text)})

		# 2. Chunk text
		splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
		chunks = splitter.split_text(text)
		logger.info("chunked_document", extra={"doc_id": doc_id, "chunks": len(chunks)})

		# After chunking
		os.makedirs(FAISS_INDEX_PATH, exist_ok=True)
		chunks_path = os.path.join(FAISS_INDEX_PATH, f"{doc_id}_chunks.txt")
		with open(chunks_path, "w", encoding="utf-8") as f:
			f.write("\n---\n".join(chunks))

		if not chunks:
			raise ValueError("No text extracted from document")

		# 3. Generate embeddings
		embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
		vectors = embedder.embed_documents(chunks)
		logger.info("embedded_chunks", extra={"doc_id": doc_id, "vectors": len(vectors), "dim": len(vectors[0]) if vectors else 0})

		# 4. Index in FAISS
		dim = len(vectors[0])
		index = faiss.IndexFlatL2(dim)
		index.add(np.array(vectors).astype("float32"))
		logger.info("faiss_index_built", extra={"doc_id": doc_id, "ntotal": index.ntotal})

		# 5. Save FAISS index
		faiss_path = os.path.join(FAISS_INDEX_PATH, f"{doc_id}.index")
		faiss.write_index(index, faiss_path)
		logger.info("task_completed", extra={"doc_id": doc_id, "faiss_path": f"{doc_id}.index"})
		return True
	except Exception as e:
		logger.error("task_failed", extra={"doc_id": doc_id}, exc_info=True)
		return False