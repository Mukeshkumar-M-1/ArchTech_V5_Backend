"""
main.py  —  ArchTech Agent v5.0
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging

log = logging.getLogger(__name__)

import logging

class CustomColorFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    fmt = "\n\n %(asctime)s [%(name)s.%(funcName)s] \n [%(levelname)s] %(message)s"
    FORMATS = {
        logging.DEBUG: grey + fmt + reset,
        logging.INFO: fmt + reset,
        logging.WARNING: grey + fmt + reset,
        logging.ERROR: bold_red + fmt + reset,
        logging.CRITICAL: bold_red + fmt + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(CustomColorFormatter())
file_handler = logging.FileHandler(
    r"D:\ArchTech_AI\_V5_3\Frontend\_Logs\log_1.log", 
    encoding="utf-8", 
    mode="a"
)
file_handler.setFormatter(logging.Formatter("\n\n %(asctime)s [%(name)s.%(funcName)s] \n [%(levelname)s] %(message)s"))
logging.basicConfig(
    level=logging.INFO,
    handlers=[stream_handler, file_handler]
)
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    log.info("[main] Initiating graceful shutdown...")
    try:
        from AgentCore.execution.abort_controller import get_hierarchy
        get_hierarchy().abort_all(reason="Server shutting down")
        log.info("[main] Graceful shutdown completed successfully.")
    except Exception as e:
        log.error("[main] Error during graceful shutdown: %s", e)

app = FastAPI(
    title="ArchTech Agent",
    version="5.0",
    description="A local-first Agent system for aerospace/defense embedded systems documentation generation.",
    lifespan=lifespan
)

origins = [
    "http://localhost:8014",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://10.5.17.83:8014",
    "http://10.5.17.83:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===================================================================
# Route Registration
# ===================================================================
from Routes.requirement_extraction_routes import router as Requirement_Extraction_router
from Routes.memory_management_routes import router as knowledge_router
from Routes.template_analysis_routes import router as template_analysis_router
from Routes.chat_routes import router as chat_router
from Routes.project_routes import router as project_router
from AgentCore.agents.routes import router as document_generate_router
from Routes.version_manage_routes import router as version_manage_router
from Routes.settings_routes import router as settings_router


# --- Requirement Extraction Routes (prefix "/") ---
#   GET  /extraction-progress/{project_id}              -> get_extraction_progress
#   POST /upload-requirements                           -> upload_requirements_files
#   POST /update-requirement                            -> update_requirement_endpoint
#   GET  /requirements/{project_id}                     -> list_requirements
#   POST /rephrase                                      -> rephrase_section
#   POST /ai-insight                                    -> get_ai_insight_endpoint
#   GET  /files/{filename}                              -> serve_file
#   POST /submit-selected/{project_id}                  -> submit_selected_requirements
#   GET  /selected-ids/{project_id}                     -> get_selected_ids
app.include_router(Requirement_Extraction_router, prefix="")

# --- memory_management_routes (prefix "") ---
app.include_router(knowledge_router, prefix="")

# --- template_parsing_routes (prefix "") ---
#   GET  /template-sections/{project_id}                    -> get_template_sections
#   GET  /template-section/{project_id}/{filename:path}     -> get_template_file
#   PUT  /template-section/{project_id}/{filename:path}     -> update_template_file
#   POST /template-section/{project_id}/{filename:path}     -> update_template_file
#   DELETE /template-section/{project_id}/{filename:path}   -> delete_template_file
#   POST /template-section/{project_id}/generate            -> generate_template_section
#   POST /template-section/{project_id}/create              -> create_template_file
#   GET  /template-progress/{project_id}                    -> get_template_progress
#   GET  /template-architecture/{project_id}                -> get_template_architecture
#   GET  /template-gaps/{project_id}                        -> get_template_gaps
#   POST /template-section/{project_id}/validate            -> validate_template_document
#   POST /template-section/{project_id}/execute-plan        -> execute_template_plan
app.include_router(template_analysis_router, prefix="")

# --- project_routes (prefix "") ---
#   POST /init-project    -> initialize project directory structure
app.include_router(project_router, prefix="")

# --- chat_routes (prefix "") ---
#   POST /chat/send       -> agentic chat streaming endpoint (SSE)
#   GET  /chat/messages/{session_id} -> fetch conversation history
#   GET  /chat/sessions    -> list active sessions
app.include_router(chat_router, prefix="")

# --- document_generate_routes (prefix "") ---
#   POST /generate-document-stream     -> document generation SSE stream
#   GET  /document-generation-progress/{project_id} -> poll progress
#   POST /document-generation-cancel/{project_id}   -> cancel generation
app.include_router(document_generate_router, prefix="")

# --- version_manage_routes (prefix "") ---
#   GET  /document-versions/{project_id}          -> list all section versions
#   GET  /document-version/{project_id}/{filename}/{version} -> get specific version content
app.include_router(version_manage_router, prefix="")

# --- settings_routes (prefix "") ---
#   GET  /settings/{project_id}    -> read LLM settings (saved values merged over defaults)
#   POST /settings/{project_id}    -> save LLM settings to .ArchTech/{project_id}/settings.json
app.include_router(settings_router, prefix="")

from Routes.document_routes import router as document_router
app.include_router(document_router, prefix="")



# -------------------------
# @function: main
# @description: Main entry point for the ArchTech Agent application.
# @purpose:  Runs the FastAPI application server.
# @return:    N/A
# -------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8015,
        reload=True,
        # 1. Restrict watcher to source code subfolder
        reload_dirs=["backend"], 
        # 2. Ignore runtime state, databases, logs, and cache
        reload_excludes=[
            "*.log",
            "*.db",
            "*.db-wal",
            "*.db-shm",
            "*.sqlite*",
            "*.tmp",
            "*.pyc",
            "__pycache__/*",
            ".git/*",
            "logs/*",
            "storage/*",
            "vector_store/*",
            "artifacts/*",
        ],
    )