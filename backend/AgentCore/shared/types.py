"""
Pydantic input models for built-in tools.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class FileReadInput(BaseModel):
    file_path: str = Field(..., description="Absolute or relative path to the file to read")


class FileWriteInput(BaseModel):
    file_path: str = Field(..., description="Absolute or relative path to the file to write")
    content: str = Field(..., description="The complete content to write to the file")


class FileEditInput(BaseModel):
    file_path: str = Field(..., description="Absolute or relative path to the file to edit")
    target_file: str = Field(..., description="The target file path (alias for file_path)")
    range: dict = Field(..., description="Range to replace: {start_line: int, end_line: int}")
    insert_content: str = Field(..., description="The text to insert at the specified range")


class BashInput(BaseModel):
    command: str = Field(..., description="The bash command to execute")
    timeout: int = Field(default=30, description="Maximum execution time in seconds")


class AgentInput(BaseModel):
    agent_type: str = Field(default="general-purpose", description="Type: general-purpose, explore, plan")
    prompt: str = Field(..., description="Detailed task description for the subagent")
    description: str = Field(default="", description="Short 3-5 word description of the task")
    run_in_background: bool = Field(default=False, description="Run asynchronously and notify when done")


class GlobInput(BaseModel):
    pattern: str = Field(..., description="Glob pattern like **/*.ts or src/**/*.py")
    path: Optional[str] = Field(None, description="Directory to search in (defaults to CWD)")


class GrepInput(BaseModel):
    pattern: str = Field(..., description="Regex pattern to search for")
    path: Optional[str] = Field(None, description="File or directory to search in")
    glob: Optional[str] = Field(None, description="Glob filter like *.js")
    output_mode: Optional[str] = Field("files_with_matches", description="content | files_with_matches | count")

class SendMessageInput(BaseModel):
    to: str = Field(..., description="Recipient agent ID, name, or '*' for broadcast")
    message: str = Field(..., description="Message text to send")
    message_type: str = Field(default="text", description="text | shutdown_request | plan_approval")


class RequestUserInputInput(BaseModel):
    prompt: str = Field(..., description="The question or instruction for the user (supports markdown: lists, line breaks, bold)")
    ui_type: str = Field(..., description="One of: select, radio, checkbox, text")
    options: Optional[list[str]] = Field(None, description="The available options (2-8 recommended). Required for select/radio/checkbox. Omit for text type.")
    title: str = Field(default="", description="Short plain-text label for what the question is about")


class ProposeContentEditInput(BaseModel):
    section_filename: str = Field(description="The filename of the section being edited (e.g., '01_project_table.md')")
    version: int = Field(description="The version of the section block being edited")
    block_number: int = Field(description="The numeric block number that is being edited")
    original_text: str = Field(description="The exact original text content of the block")
    proposed_text: str = Field(description="The new proposed text for this block")
    rationale: str = Field(description="A brief explanation of why this edit is being proposed", default="")
