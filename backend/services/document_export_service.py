from pathlib import Path
from services.document_persistence_service import DocumentPersistenceService

class DocumentExportService:
    def __init__(self):
        self.persistence = DocumentPersistenceService()

    def export_to_markdown(self, project_id: str, document_id: str, content_json: dict) -> bool:
        """
        Generates a Markdown representation of the JSON document and saves it securely.
        """
        # A full implementation would parse Tiptap JSON and convert it into Markdown string.
        # Here we mock the parsing for demonstration or use a basic string representation 
        # since Tiptap JSON can be complex to parse perfectly without a library in Python.
        # Alternatively, the frontend could pass the markdown along with JSON if needed,
        # but the standard is to parse JSON on the backend.
        
        md_content = self._json_to_markdown(content_json)
        
        doc_dir = self.persistence.get_document_directory(project_id, document_id)
        md_path = doc_dir / "document.md"
        
        try:
            self.persistence._atomic_write_text(md_path, md_content)
            return True
        except Exception as e:
            import logging
            logging.error(f"Failed to generate Markdown export: {e}")
            return False

    def _json_to_markdown(self, node: dict) -> str:
        # Simplistic basic recursive JSON to Markdown converter for Tiptap structure
        if not node:
            return ""
        
        type_ = node.get("type")
        if type_ == "text":
            text = node.get("text", "")
            marks = node.get("marks", [])
            for mark in marks:
                if mark["type"] == "bold": text = f"**{text}**"
                if mark["type"] == "italic": text = f"*{text}*"
                if mark["type"] == "code": text = f"`{text}`"
            return text
        
        content = node.get("content", [])
        inner = "".join(self._json_to_markdown(child) for child in content)

        if type_ == "paragraph":
            return inner + "\n\n"
        if type_ == "heading":
            level = node.get("attrs", {}).get("level", 1)
            return ("#" * level) + " " + inner + "\n\n"
        if type_ == "bulletList":
            return inner + "\n"
        if type_ == "orderedList":
            return inner + "\n"
        if type_ == "listItem":
            return "- " + inner + "\n"
        if type_ == "blockquote":
            return "> " + inner.replace("\n", "\n> ") + "\n\n"
        if type_ == "doc":
            return inner
        
        return inner
