import sys
from langgraph.graph import StateGraph, END
from .state import State
from .config import APP_CONFIG
from .guardrails import check_safety
from .intent_classifier import classify_intent
from .audit import audit_log
from .task_registry import task_registry
from .flow_agent import flow_agent, FLOW_CONFIG # Import flow_agent and FLOW_CONFIG
from .knowledge_agent import KnowledgeAgent # Import the new knowledge_agent
from .response_generator import response_generator # Import the response_generator

# --- Generic Nodes (interpreters for flow.yaml) ---
def generic_flow_node(state: State) -> State:
    """A generic node that delegates to the FlowAgent to run the current flow step."""
    return flow_agent.run_flow(state)

def greeting_node(state: State) -> State:
    """Handles greetings."""
    print("--- Greeting ---")
    message = response_generator.generate(state, "GREETING")
    return {**state, "message": message}

def clarification_node(state: State) -> State:
    print("--- Clarification needed ---")
    message = response_generator.generate(state, "CLARIFICATION")
    return {**state, "message": message}

def out_of_topic_node(state: State) -> State:
    """Handles out-of-topic user queries."""
    print("--- Out of Topic ---")
    message = response_generator.generate(state, "OUT_OF_TOPIC")
    return {**state, "message": message}

def farewell_node(state: State) -> State:
    """Handles farewells."""
    print("--- Farewell ---")
    message = response_generator.generate(state, "FAREWELL")
    return {**state, "message": message}

def chitchat_node(state: State) -> State:
    """Handles chitchat."""
    print("--- Chitchat ---")
    message = response_generator.generate(state, "CHITCHAT")
    return {**state, "message": message}

# --- Generic Router ---
def start_flow(state: State) -> State:
    """Initializes the state for a new conversational flow."""
    print("--- Starting Flow ---")
    current_intent = state["current_intent"]
    
    # Find the rule for the current intent to get the target flow name
    rule = next((r for r in FLOW_CONFIG["routing_rules"] if r["intent"] == current_intent), None)
    if not rule or not rule["target"].endswith("_flow"):
        return {**state, "message": "Error: Could not determine which flow to start."}

    flow_name = rule["target"]
    flow_definition = FLOW_CONFIG["flows"][flow_name]
    start_node_name = flow_definition["start_node"]

    # Set up the initial state for the flow
    return {
        **state,
        "pending_task": {
            "type": current_intent,
            "flow_name": flow_name,
            "current_step": start_node_name,
            "fields": {}
        },
        "transaction_fields": {}, # Ensure fields are clean for the new flow
        "task_stage": start_node_name
    }

def generic_router(state: State) -> str:
    """Routes to the appropriate node based on the current intent and whether a task is pending."""
    current_intent = state["current_intent"]

    # Prioritize simple, non-task intents first
    if current_intent in ["OUT_OF_TOPIC", "FAREWELL", "CHITCHAT", "GREETING"]:
        return {
            "OUT_OF_TOPIC": "out_of_topic_node",
            "FAREWELL": "farewell_node",
            "CHITCHAT": "chitchat_node",
            "GREETING": "greeting_node"
        }[current_intent]

    if not state["is_safe"]:
        return "end_node"
    
    pending_task = state.get("pending_task")

    # --- Interruption Handling ---
    if pending_task and "flow_name" in pending_task:
        # Check if the new intent is an interruption or part of the flow
        flow_task_type = pending_task.get("type")
        is_interruption = current_intent not in [flow_task_type, "CONFIRM", "CANCEL"]
        
        if is_interruption:
            # Route to the interruption handler
            for rule in FLOW_CONFIG.get("routing_rules", []):
                if rule["intent"] == current_intent:
                    return rule["target"]
    
    # --- Standard Flow and Rule-Based Routing ---
    # If not an interruption, or if no task is pending, use the main routing rules
    if pending_task and "flow_name" in pending_task:
        return "generic_flow_node"

    for rule in FLOW_CONFIG.get("routing_rules", []):
        if rule["intent"] == current_intent:
            if "conditions" in rule:
                all_conditions_met = True
                for condition in rule["conditions"]:
                    if condition == "pending_task" and not pending_task:
                        all_conditions_met = False; break
                if not all_conditions_met: continue
            
            target = rule["target"]
            return "start_flow" if target.endswith("_flow") else target

    return "clarification_node"

def route_after_flow(state: State) -> str:
    """Routes after a generic flow step has been executed."""
    pending_task = state.get("pending_task")
    if not pending_task:
        # Flow is complete
        return "end_node"
    # Flow is still in progress, end the turn to wait for user input
    return "audit_node"

def route_after_interruption(state: State) -> str:
    """After an interruption, decide whether to resume a pending task or end."""
    # If the interruption (e.g., inquiry) generated an answer, end the turn to display it.
    if state.get("answer"):
        return "audit_node"
    # Otherwise, if a task is still pending, resume it.
    if state.get("pending_task"):
        return "generic_flow_node"
    # If no task to resume, end the turn.
    return "audit_node"

def create_graph():
    """Creates the LangGraph workflow with declarative routing and interruption handling."""
    
    knowledge_agent = KnowledgeAgent(task_registry)
    
    def faq_handler_node(state: State) -> State:
        """Handles FAQ intents using the generic KnowledgeAgent."""
        return knowledge_agent.handle_faq(state)

    def inquiry_handler_node(state: State) -> State:
        """Handles inquiry intents using the generic KnowledgeAgent."""
        return knowledge_agent.handle_inquiry(state)

    workflow = StateGraph(State)

    # Add nodes...
    workflow.add_node("guardrails", check_safety)
    workflow.add_node("intent_classifier", classify_intent)
    workflow.add_node("start_flow", start_flow)
    workflow.add_node("generic_flow_node", generic_flow_node)
    workflow.add_node("greeting_node", greeting_node)
    workflow.add_node("clarification_node", clarification_node)
    workflow.add_node("out_of_topic_node", out_of_topic_node)
    workflow.add_node("farewell_node", farewell_node)
    workflow.add_node("chitchat_node", chitchat_node)
    workflow.add_node("faq_handler_node", faq_handler_node)
    workflow.add_node("inquiry_handler_node", inquiry_handler_node)
    workflow.add_node("audit_node", audit_log)
    workflow.add_node("end_node", lambda state: {**state, "status": "COMPLETED"})

    workflow.set_entry_point("guardrails")
    workflow.add_edge("guardrails", "intent_classifier")
    
    workflow.add_conditional_edges(
        "intent_classifier",
        generic_router,
        {
            "start_flow": "start_flow",
            "generic_flow_node": "generic_flow_node",
            "greeting_node": "greeting_node",
            "clarification_node": "clarification_node",
            "out_of_topic_node": "out_of_topic_node",
            "farewell_node": "farewell_node",
            "chitchat_node": "chitchat_node",
            "faq_handler_node": "faq_handler_node",
            "inquiry_handler_node": "inquiry_handler_node",
            "end_node": "end_node",
        }
    )

    workflow.add_edge("start_flow", "generic_flow_node")

    # After a flow step, end the turn to wait for user input
    workflow.add_conditional_edges(
        "generic_flow_node",
        route_after_flow,
        {"audit_node": "audit_node", "end_node": "end_node"}
    )
    
    # After interruptions, route back to the pending task or end
    workflow.add_conditional_edges("faq_handler_node", route_after_interruption, {"generic_flow_node": "generic_flow_node", "audit_node": "audit_node"})
    workflow.add_conditional_edges("inquiry_handler_node", route_after_interruption, {"generic_flow_node": "generic_flow_node", "audit_node": "audit_node"})

    # Simple nodes go to audit and then end
    workflow.add_edge("greeting_node", "audit_node")
    workflow.add_edge("clarification_node", "audit_node")
    workflow.add_edge("out_of_topic_node", "audit_node")
    workflow.add_edge("farewell_node", "audit_node")
    workflow.add_edge("chitchat_node", "audit_node")
    
    workflow.add_edge("audit_node", END)
    workflow.add_edge("end_node", END)

    return workflow.compile()


