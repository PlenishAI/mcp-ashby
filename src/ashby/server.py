# /// script
# dependencies = [
#   "mcp",
#   "requests",
#   "python-dotenv"
# ]
# ///
import asyncio
import base64
import json
from typing import Any, Optional
import os
from dotenv import load_dotenv
import requests

import mcp.types as types
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio


class AshbyClient:
    """Handles Ashby API operations using Basic Auth."""

    def __init__(self):
        self.api_key: Optional[str] = None
        self.base_url = "https://api.ashbyhq.com"
        self.headers = {}

    def connect(self) -> bool:
        try:
            self.api_key = os.getenv("ASHBY_API_KEY")
            if not self.api_key:
                raise ValueError("ASHBY_API_KEY environment variable not set")
            # Ashby uses Basic Auth: API key as username, empty password
            encoded = base64.b64encode(f"{self.api_key}:".encode()).decode()
            self.headers = {
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/json",
            }
            return True
        except Exception as e:
            print(f"Ashby connection failed: {str(e)}", flush=True)
            return False

    def post(self, endpoint: str, data: Optional[dict] = None) -> dict:
        """All Ashby API endpoints are POST with JSON bodies."""
        if not self.api_key:
            raise ValueError("Ashby connection not established")
        url = f"{self.base_url}{endpoint}"
        response = requests.post(url, headers=self.headers, json=data or {})
        response.raise_for_status()
        return response.json()


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------
server = Server("ashby-mcp")
load_dotenv()

ashby = AshbyClient()
if not ashby.connect():
    print("Failed to initialize Ashby connection", flush=True)


# ---------------------------------------------------------------------------
# Tool definitions – aligned to the real Ashby API
# ---------------------------------------------------------------------------
TOOLS = [
    # ── Jobs ──────────────────────────────────────────────────────────────
    types.Tool(
        name="job_list",
        description="List all jobs (open, closed, archived). Supports cursor pagination and status filtering.",
        inputSchema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["Draft", "Open", "Closed", "Archived"]},
                    "description": "Filter by status(es). If omitted, returns all non-Draft jobs.",
                },
                "limit": {"type": "integer", "description": "Max results per page (default/max 100)"},
                "cursor": {"type": "string", "description": "Cursor for next page of results"},
            },
        },
    ),
    types.Tool(
        name="job_info",
        description="Get details of a single job by its ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "The job ID (UUID)"},
            },
            "required": ["id"],
        },
    ),
    types.Tool(
        name="job_search",
        description="Search for jobs by title. Not paginated; returns all matches.",
        inputSchema={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "The job title to search for"},
            },
            "required": ["title"],
        },
    ),

    # ── Candidates ────────────────────────────────────────────────────────
    types.Tool(
        name="candidate_list",
        description="List all candidates with cursor pagination.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results per page (default/max 100)"},
                "cursor": {"type": "string", "description": "Cursor for next page"},
            },
        },
    ),
    types.Tool(
        name="candidate_search",
        description="Search candidates by email and/or name. Not paginated.",
        inputSchema={
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "Email to search for"},
                "name": {"type": "string", "description": "Name to search for"},
            },
        },
    ),
    types.Tool(
        name="candidate_info",
        description="Get full details of a single candidate by ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "The candidate ID (UUID)"},
            },
            "required": ["id"],
        },
    ),
    types.Tool(
        name="candidate_create",
        description="Create a new candidate in Ashby.",
        inputSchema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Full name of the candidate"},
                "email": {"type": "string", "description": "Primary email address"},
                "phoneNumber": {"type": "string", "description": "Phone number"},
                "linkedInUrl": {"type": "string", "description": "LinkedIn profile URL"},
                "githubUrl": {"type": "string", "description": "GitHub profile URL"},
                "sourceId": {"type": "string", "description": "Source ID for attribution"},
            },
            "required": ["name"],
        },
    ),
    types.Tool(
        name="candidate_create_note",
        description="Add a note to a candidate. Supports HTML formatting.",
        inputSchema={
            "type": "object",
            "properties": {
                "candidateId": {"type": "string", "description": "The candidate ID"},
                "note": {"type": "string", "description": "Note content (HTML supported)"},
                "sendNotifications": {
                    "type": "boolean",
                    "description": "Notify subscribed users (default false)",
                },
            },
            "required": ["candidateId", "note"],
        },
    ),
    types.Tool(
        name="candidate_list_notes",
        description="List all notes for a candidate.",
        inputSchema={
            "type": "object",
            "properties": {
                "candidateId": {"type": "string", "description": "The candidate ID"},
                "limit": {"type": "integer", "description": "Max results per page"},
                "cursor": {"type": "string", "description": "Cursor for next page"},
            },
            "required": ["candidateId"],
        },
    ),
    types.Tool(
        name="candidate_add_tag",
        description="Add a tag to a candidate. Use candidate_tag_list to find tag IDs.",
        inputSchema={
            "type": "object",
            "properties": {
                "candidateId": {"type": "string", "description": "The candidate ID"},
                "tagId": {"type": "string", "description": "The tag ID to add"},
            },
            "required": ["candidateId", "tagId"],
        },
    ),
    types.Tool(
        name="candidate_tag_list",
        description="List all available candidate tags.",
        inputSchema={
            "type": "object",
            "properties": {
                "includeArchived": {"type": "boolean", "description": "Include archived tags (default false)"},
            },
        },
    ),

    # ── Applications ──────────────────────────────────────────────────────
    types.Tool(
        name="application_list",
        description="List applications. Can filter by jobId and/or status. Uses cursor pagination.",
        inputSchema={
            "type": "object",
            "properties": {
                "jobId": {"type": "string", "description": "Filter by job ID (UUID)"},
                "status": {
                    "type": "string",
                    "enum": ["Active", "Hired", "Archived", "Lead"],
                    "description": "Filter by application status",
                },
                "createdAfter": {
                    "type": "integer",
                    "description": "Only return applications created after this timestamp (ms since epoch)",
                },
                "limit": {"type": "integer", "description": "Max results per page (default/max 100)"},
                "cursor": {"type": "string", "description": "Cursor for next page"},
            },
        },
    ),
    types.Tool(
        name="application_info",
        description="Get full details for a single application by ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "applicationId": {"type": "string", "description": "The application ID (UUID)"},
            },
            "required": ["applicationId"],
        },
    ),
    types.Tool(
        name="application_create",
        description="Create an application linking a candidate to a job.",
        inputSchema={
            "type": "object",
            "properties": {
                "candidateId": {"type": "string", "description": "The candidate ID"},
                "jobId": {"type": "string", "description": "The job ID"},
                "sourceId": {"type": "string", "description": "Source ID for attribution"},
                "interviewPlanId": {"type": "string", "description": "Interview plan to use (optional)"},
            },
            "required": ["candidateId", "jobId"],
        },
    ),
    types.Tool(
        name="application_change_stage",
        description="Move an application to a different interview stage.",
        inputSchema={
            "type": "object",
            "properties": {
                "applicationId": {"type": "string", "description": "The application ID"},
                "interviewStageId": {"type": "string", "description": "Target interview stage ID"},
                "archiveReasonId": {
                    "type": "string",
                    "description": "Required when moving to an Archived stage",
                },
            },
            "required": ["applicationId", "interviewStageId"],
        },
    ),

    # ── Interview Stages & Plans ──────────────────────────────────────────
    types.Tool(
        name="interview_stage_list",
        description="List all interview stages for a given interview plan.",
        inputSchema={
            "type": "object",
            "properties": {
                "interviewPlanId": {"type": "string", "description": "The interview plan ID"},
            },
            "required": ["interviewPlanId"],
        },
    ),
    types.Tool(
        name="interview_plan_list",
        description="List all interview plans.",
        inputSchema={
            "type": "object",
            "properties": {
                "includeArchived": {"type": "boolean", "description": "Include archived plans"},
            },
        },
    ),

    # ── Interviews ────────────────────────────────────────────────────────
    types.Tool(
        name="interview_list",
        description="List all interviews with cursor pagination.",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max results per page"},
                "cursor": {"type": "string", "description": "Cursor for next page"},
            },
        },
    ),
    types.Tool(
        name="interview_info",
        description="Get details of a single interview by ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "The interview ID"},
            },
            "required": ["id"],
        },
    ),

    # ── Supporting lookups ────────────────────────────────────────────────
    types.Tool(
        name="department_list",
        description="List all departments.",
        inputSchema={
            "type": "object",
            "properties": {
                "includeArchived": {"type": "boolean", "description": "Include archived departments"},
            },
        },
    ),
    types.Tool(
        name="user_list",
        description="List all users (team members) in the organization.",
        inputSchema={
            "type": "object",
            "properties": {
                "includeDeactivated": {"type": "boolean", "description": "Include deactivated users"},
            },
        },
    ),
    types.Tool(
        name="source_list",
        description="List all candidate sources.",
        inputSchema={
            "type": "object",
            "properties": {
                "includeArchived": {"type": "boolean", "description": "Include archived sources"},
            },
        },
    ),
    types.Tool(
        name="archive_reason_list",
        description="List all archive reasons (needed for application_change_stage to Archived).",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    types.Tool(
        name="location_list",
        description="List all locations.",
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
]

# Map tool names -> Ashby API endpoints
TOOL_ENDPOINT_MAP = {
    "job_list": "/job.list",
    "job_info": "/job.info",
    "job_search": "/job.search",
    "candidate_list": "/candidate.list",
    "candidate_search": "/candidate.search",
    "candidate_info": "/candidate.info",
    "candidate_create": "/candidate.create",
    "candidate_create_note": "/candidate.createNote",
    "candidate_list_notes": "/candidate.listNotes",
    "candidate_add_tag": "/candidate.addTag",
    "candidate_tag_list": "/candidateTag.list",
    "application_list": "/application.list",
    "application_info": "/application.info",
    "application_create": "/application.create",
    "application_change_stage": "/application.change_stage",
    "interview_stage_list": "/interviewStage.list",
    "interview_plan_list": "/interviewPlan.list",
    "interview_list": "/interview.list",
    "interview_info": "/interview.info",
    "department_list": "/department.list",
    "user_list": "/user.list",
    "source_list": "/source.list",
    "archive_reason_list": "/archiveReason.list",
    "location_list": "/location.list",
}


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return TOOLS


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    """Route tool calls to the correct Ashby endpoint, passing arguments directly."""
    endpoint = TOOL_ENDPOINT_MAP.get(name)
    if not endpoint:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    try:
        # Pass arguments straight through -- tool schemas already use Ashby's
        # camelCase param names so no translation is needed.
        response = ashby.post(endpoint, data=arguments if arguments else None)
        return [types.TextContent(type="text", text=json.dumps(response, indent=2))]
    except requests.exceptions.HTTPError as e:
        error_body = ""
        if e.response is not None:
            try:
                error_body = e.response.text
            except Exception:
                pass
        return [
            types.TextContent(
                type="text",
                text=f"Ashby API error on {endpoint}: {e}\n{error_body}",
            )
        ]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error calling {endpoint}: {e}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def run():
    """Run the MCP server over stdio."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ashby",
                server_version="0.2.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(run())