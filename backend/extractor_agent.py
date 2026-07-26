"""
extraction_agent.py
"""

import json
import logging
from pathlib import Path

try:
    from Requirement_extraction.extraction_event_loop import extract_requirements_async
except ImportError:
    from Requirement_extraction.extraction_event_loop import extract_requirements_async

log = logging.getLogger(__name__)

#-------------------------
# @function: scan_file
# @description: scan a file for requirements
# @purpose:  scan a file for requirements
# @return:    list of requirements
#-------------------------
async def scan_file(file_path: str, doc_type: str = None,
              counters: dict = None, progress_callback: callable = None) -> list[dict]:
    if counters is None:
        counters = {}
    current_file_path = Path(file_path)
    ext   = current_file_path.suffix.lower()
    
    if ext == '.pdf':
        log.info(f"[Scan_File] Requrement Extraction Start")
        return await extract_requirements_async(str(current_file_path), doc_type=doc_type, use_llm_norm=True, progress_callback=progress_callback)
    return []


#-------------------------
# @function: scan_folder
# @description: scan a folder for requirements
# @purpose:  scan a folder for requirements
# @return:    list of requirements
#-------------------------
async def scan_folder(folder_path: str, progress_callback: callable = None) -> list[dict]:
    folder    = Path(folder_path)
    all_reqs  = []
    counters  = {}
    supported = {'.pdf'}
    
    log.info(f" [Scan_Foler] Extracting Requirement Path : {folder_path}")
    files = ([folder] if folder.is_file()
             else sorted(file for file in folder.rglob("*") if file.suffix.lower() in supported))
    if not files:
        log.info(f" [Scan_Foler] No supported files in {folder_path}")
        return []
    for file in files:
        log.info(f" [Scan_Foler] Processing File: {file.name}")
        extracted = await scan_file(str(file), counters=counters, progress_callback=progress_callback)
        log.info(f" [Scan_Foler] Extracted : {len(extracted)} requirements")
        all_reqs.extend(extracted)
    return all_reqs


#-------------------------
# @function: save_to_json
# @description: save requirements to json
# @purpose:  save requirements to json
# @return:    list of requirement ids
#-------------------------
async def save_to_json(requirements: list, output_dir: Path) -> list[str]:
    fpath = output_dir / "requirements.json"
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(requirements, f, indent=2)
    log.info(f"[Save_JSON] Requirements Saved: {Path(fpath)}")
    return [r['id'] for r in requirements]
