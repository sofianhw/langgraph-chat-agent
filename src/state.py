from typing import TypedDict, List, Optional, Dict, Any

class State(TypedDict):
    """Represents the state of the conversational agent."""
    
    conversation_history: List[Dict[str, str]]
    transaction_fields: Dict[str, Any]
    inquiry_fields: Dict[str, Any]
    pending_task: Optional[Dict[str, Any]]
    task_stage: Optional[str]
    current_intent: Optional[str]
    is_safe: bool
    guardrail_violation: Optional[str]
    clarification_needed: bool
    message: Optional[str]
    answer: Optional[str]
    source_urls: Optional[List[str]]
    transaction_id: Optional[str]
    status: Optional[str]
    
    # Audit-related fields
    timestamp: Optional[str]
    node_path: Optional[List[str]]
