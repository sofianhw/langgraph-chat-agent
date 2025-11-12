import datetime
from .state import State

def audit_log(state: State) -> State:
    """
    Logs the state for audit purposes.
    
    Args:
        state: The current state of the conversation.
        
    Returns:
        The unmodified state.
    """
    print("--- Auditing ---")
    
    log_entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "state": state
    }
    
    # In a real application, this would write to a secure, immutable log store.
    # For now, we'll just print it to the console.
    print(log_entry)
    
    return state
