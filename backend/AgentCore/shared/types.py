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


class TodoWriteInput(BaseModel):
    todos: list[dict] = Field(..., description="Tasks with content, status, activeForm")


class SkillInput(BaseModel):
    skill: str = Field(..., description="Skill name (e.g., 'review', 'simplify')")
    args: Optional[str] = Field(None, description="Optional arguments")


class TaskCreateInput(BaseModel):
    subject: str = Field(..., description="Brief actionable title in imperative form")
    description: str = Field(..., description="What needs to be done")
    activeForm: Optional[str] = Field(None, description="Present continuous form for spinner")
    metadata: Optional[dict] = Field(None, description="Arbitrary metadata")


class TaskUpdateInput(BaseModel):
    taskId: str = Field(..., description="Task ID to update")
    subject: Optional[str] = None
    description: Optional[str] = None
    activeForm: Optional[str] = None
    status: Optional[str] = Field(None, description="pending | in_progress | completed | deleted")
    addBlocks: Optional[list] = None
    addBlockedBy: Optional[list] = None
    owner: Optional[str] = None
    metadata: Optional[dict] = None


class TaskListInput(BaseModel):
    pass


class TaskGetInput(BaseModel):
    taskId: str = Field(..., description="The ID of the task to retrieve")


class TaskOutputInput(BaseModel):
    task_id: str = Field(..., description="The task ID to get output from")
    block: bool = Field(True, description="Whether to wait for completion")
    timeout: int = Field(30000, description="Max wait time in ms (0-600000)")


class TaskStopInput(BaseModel):
    task_id: Optional[str] = Field(None, description="The task ID to stop")


class SendMessageInput(BaseModel):
    to: str = Field(..., description="Recipient agent ID, name, or '*' for broadcast")
    message: str = Field(..., description="Message text to send")
    message_type: str = Field(default="text", description="text | shutdown_request | plan_approval")


class RequestUserInputInput(BaseModel):
    prompt: str = Field(..., description="The question or instruction for the user")
    ui_type: str = Field(..., description="One of: select, radio, checkbox")
    options: list[str] = Field(..., description="The available options (2-8 recommended)")
    title: str = Field(default="", description="Optional card title")
