import os
import yaml
from typing import Dict, Any, List, Optional
from .state import State
from .task_registry import task_registry
from .response_generator import response_generator # Import the response_generator

# Load the flow configuration
FLOW_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "flow.yaml")
with open(FLOW_CONFIG_PATH, "r") as f:
    FLOW_CONFIG = yaml.safe_load(f)

class FlowAgent:
    """A generic agent that interprets and executes steps defined in flow.yaml."""

    def __init__(self):
        self.flows = FLOW_CONFIG.get("flows", {})

    def _get_current_flow_step(self, state: State) -> Optional[Dict[str, Any]]:
        """Retrieves the current step definition from the active flow."""
        pending_task = state.get("pending_task")
        if not pending_task or "flow_name" not in pending_task or "current_step" not in pending_task:
            return None
        
        flow_name = pending_task["flow_name"]
        current_step_name = pending_task["current_step"]
        
        flow_definition = self.flows.get(flow_name)
        if flow_definition and "nodes" in flow_definition:
            return flow_definition["nodes"].get(current_step_name)
        return None

    def _update_flow_state(self, state: State, flow_name: str, current_step: str, task_type: str) -> State:
        """Updates the state to reflect the current position in a flow."""
        return {
            **state,
            "pending_task": {
                "type": task_type,
                "flow_name": flow_name,
                "current_step": current_step,
                "fields": state.get("transaction_fields", {})
            },
            "task_stage": current_step # Use current_step as task_stage for clarity
        }

    def run_flow(self, state: State) -> State:
        """Main entry point for the generic flow agent. Assumes a flow is already active."""
        print("--- Generic Flow Agent processing ---")
        
        while True:
            pending_task = state.get("pending_task")
            if not pending_task or "flow_name" not in pending_task:
                return {**state, "message": response_generator.generate(state, "ERROR", {"details": "Flow agent was called but no flow is active."})}

            flow_name = pending_task["flow_name"]
            task_type = pending_task["type"]
            current_step_name = pending_task.get("current_step")
            current_intent = state["current_intent"]
            
            flow_definition = self.flows.get(flow_name)
            if not flow_definition:
                return {**state, "message": response_generator.generate(state, "ERROR", {"details": f"Flow definition for '{flow_name}' not found."})}

            current_step_def = flow_definition["nodes"].get(current_step_name)
            if not current_step_def:
                return {**state, "message": response_generator.generate(state, "ERROR", {"details": f"Step '{current_step_name}' not found in flow '{flow_name}'."})}

            # --- Interruption Recovery ---
            if current_intent not in [task_type, "CONFIRM", "CANCEL"] and not state.get("reprompt_handled"):
                message = self.get_current_step_question(state)
                return {**state, "message": message}

            # --- Standard Step Execution ---
            step_type = current_step_def["type"]
            if step_type == "form_collection":
                state = self._handle_form_collection(state, flow_name, task_type, current_step_name, current_step_def)
            elif step_type == "prompt":
                state = self._handle_prompt(state, flow_name, task_type, current_step_name, current_step_def)
            elif step_type == "execution":
                state = self._handle_execution(state, flow_name, task_type, current_step_name, current_step_def)
            elif step_type == "end":
                return self._handle_end_flow(state)
            else:
                return {**state, "message": response_generator.generate(state, "ERROR", {"details": f"Unknown step type '{step_type}'."})}

            if state.get("message"):
                return state

    def _handle_form_collection(self, state: State, flow_name: str, task_type: str, current_step_name: str, step_def: Dict[str, Any]) -> State:
        """Handles collecting fields for a form."""
        transaction_fields = state.get("transaction_fields", {})
        fields_to_collect = step_def["fields_to_collect"]
        
        missing_fields = [field for field in fields_to_collect if not transaction_fields.get(field)]

        if missing_fields:
            field_to_ask = missing_fields[0]
            message = response_generator.generate(state, "ASK_FIELD", {"field": field_to_ask, "transaction_fields": transaction_fields})
            return self._update_flow_state(state, flow_name, current_step_name, task_type) | {"message": message}
        else:
            # All fields collected, move to next step
            next_step_name = step_def["on_complete"]["target"]
            return self._update_flow_state(state, flow_name, next_step_name, task_type) | {"message": ""}

    def _handle_prompt(self, state: State, flow_name: str, task_type: str, current_step_name: str, step_def: Dict[str, Any]) -> State:
        """Handles displaying a prompt and waiting for user reply."""
        current_intent = state["current_intent"]
        transaction_fields = state.get("transaction_fields", {})

        # Check if user has replied to the prompt
        if current_intent in [r["intent"] for r in step_def["on_reply"]]:
            reply_rule = next(r for r in step_def["on_reply"] if r["intent"] == current_intent)
            next_step_name = reply_rule["target"]
            return self._update_flow_state(state, flow_name, next_step_name, task_type) | {"message": ""}
        else:
            # Display the prompt message
            message = response_generator.generate(state, "CONFIRM_TRANSFER", {"transaction_fields": transaction_fields})
            return self._update_flow_state(state, flow_name, current_step_name, task_type) | {"message": message}

    def _handle_execution(self, state: State, flow_name: str, task_type: str, current_step_name: str, step_def: Dict[str, Any]) -> State:
        """Handles executing a task (e.g., API call)."""
        # Simulate API call / execution
        transaction_fields = state.get("transaction_fields", {})
        message = response_generator.generate(state, "EXECUTION_SUCCESS", {"transaction_fields": transaction_fields})
        
        next_step_name = step_def["on_complete"]["target"]
        return self._update_flow_state(state, flow_name, next_step_name, task_type) | {"message": message, "status": "COMPLETED"}

    def _handle_end_flow(self, state: State) -> State:
        """Handles the end of a flow, clearing pending task."""
        return {
            **state,
            "pending_task": None,
            "task_stage": None,
            "message": state.get("message", ""), # Preserve any final message
            "status": state.get("status", "COMPLETED") # Default to completed if not set
        }

    def _get_field_question(self, field: str, fields: dict) -> str:
        """Helper to generate questions for missing fields."""
        # This logic is now handled by the response_generator
        return response_generator.generate(state, "ASK_FIELD", {"field": field, "transaction_fields": fields})

    def get_current_step_question(self, state: State) -> Optional[str]:
        """Returns the question for the current step of the active flow."""
        current_step_def = self._get_current_flow_step(state)
        if not current_step_def:
            return None

        step_type = current_step_def["type"]
        transaction_fields = state.get("transaction_fields", {})

        if step_type == "form_collection":
            fields_to_collect = current_step_def["fields_to_collect"]
            missing_fields = [field for field in fields_to_collect if not transaction_fields.get(field)]
            if missing_fields:
                return response_generator.generate(state, "ASK_FIELD", {"field": missing_fields[0], "transaction_fields": transaction_fields})
        elif step_type == "prompt":
            return response_generator.generate(state, "REPROMPT", {"original_prompt": current_step_def["message"].format(**transaction_fields)})
        
        return None

# Create a singleton instance of the FlowAgent
flow_agent = FlowAgent()
