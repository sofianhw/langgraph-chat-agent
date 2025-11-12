import asyncio
import sys
from src.main import create_graph
from src.state import State

def main():
    """Main application loop."""
    print("Starting Conversational Banking Agent...")
    app = create_graph()

    current_state: State = {
        "conversation_history": [],
        "transaction_fields": {},
        "inquiry_fields": {},
        "pending_task": None,
        "task_stage": None,
        "current_intent": None,
        "is_safe": True,
        "guardrail_violation": None,
        "clarification_needed": False,
        "message": None,
        "answer": None,
        "source_urls": None,
        "transaction_id": None,
        "status": None,
        "timestamp": None,
        "node_path": None
    }

    try:
        while True:
            print("You: ", end="", flush=True)
            user_input = input()
            if user_input.lower() in ["quit", "exit"]:
                break

            current_state["reprompt_handled"] = False
            current_state["conversation_history"].append({"role": "user", "content": user_input})
            
            final_state = app.invoke(current_state)
            
            current_state = {**current_state, **final_state}

            bot_response = ""
            if final_state.get("answer"):
                bot_response += final_state["answer"]
            if final_state.get("message"):
                if bot_response: # Add a newline if answer is also present
                    bot_response += "\n"
                bot_response += final_state["message"]
            
            if bot_response:
                print(f"Bot: {bot_response.strip()}")
                current_state["conversation_history"].append({"role": "assistant", "content": bot_response.strip()})

            # Reset transient fields for the next turn
            current_state["message"] = None
            current_state["answer"] = None

            # If the task is finished, reset the state for the next conversation
            if final_state.get("status") in ["COMPLETED", "CANCELLED"]:
                print("--- Session State Reset ---")
                current_state["conversation_history"] = []
                current_state["transaction_fields"] = {}
                current_state["inquiry_fields"] = {}
                current_state["pending_task"] = None
                current_state["task_stage"] = None
                current_state["status"] = None

    except KeyboardInterrupt:
        print("\nExiting chat. Goodbye!")
        sys.exit(0)

if __name__ == "__main__":
    main()
