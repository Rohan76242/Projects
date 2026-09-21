"""Z3RO — Authorized Tools Package.

Provides:
- credentials (Scoped Credential Broker, Section 9.3)
- browser (Web research with robots.txt compliance)
- files (Sandboxed code and artifact generation)
- communication (Restricted messaging with Human Approval Queue)
- system (OS application control, keyboard, mouse)
"""

from z3ro.tools.credentials import credential_broker, CredentialBroker, ScopedCredential
from z3ro.tools.browser import browser_tool, BrowserTool
from z3ro.tools.files import files_tool, FilesTool
from z3ro.tools.communication import (
    communication_tool,
    CommunicationTool,
    approval_queue,
    ApprovalQueue,
    ApprovalStatus,
    PendingApprovalAction,
)

__all__ = [
    "credential_broker",
    "CredentialBroker",
    "ScopedCredential",
    "browser_tool",
    "BrowserTool",
    "files_tool",
    "FilesTool",
    "communication_tool",
    "CommunicationTool",
    "approval_queue",
    "ApprovalQueue",
    "ApprovalStatus",
    "PendingApprovalAction",
]
