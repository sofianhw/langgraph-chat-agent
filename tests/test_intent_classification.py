import pytest
from src.main import create_graph
from src.state import State
from tests.test_e2e_conversation import evaluate_response_with_llm

intent_test_cases = [
    (
        "How much more can I transfer today?",
        "INQUIRY",
        "Your remaining transfer limit for today is $7500.00 out of a daily limit of $10000.00."
    ),
    (
        "What is the capital of France?",
        "OUT_OF_TOPIC",
        "I can only assist with banking-related questions and tasks."
    ),
    (
        "how are you?",
        "CHITCHAT",
        "I'm just a bot, but I'm here to help you with your banking needs!"
    ),
    (
        "Thank you for your help!",
        "FAREWELL",
        "You're welcome! Have a great day."
    ),
    (
        "Goodbye",
        "FAREWELL",
        "Goodbye! Have a great day."
    )
]

@pytest.mark.parametrize("user_input, expected_intent, expected_response", intent_test_cases)
def test_intent_classification(user_input, expected_intent, expected_response):
    """Tests various simple intent classifications."""
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

    current_state["conversation_history"].append({"role": "user", "content": user_input})
    
    final_state = app.invoke(current_state)
    
    # Assert the intent was classified correctly
    assert final_state["current_intent"] == expected_intent

    bot_response = ""
    if final_state.get("answer"):
        bot_response += final_state["answer"]
    if final_state.get("message"):
        if bot_response:
            bot_response += "\n"
        bot_response += final_state["message"]
    
    bot_response = bot_response.strip()

    # Use the AI judge for a more robust assertion on the response
    is_correct = evaluate_response_with_llm(expected_response, bot_response)
    assert is_correct, f"AI judge failed for intent '{expected_intent}': Expected '{expected_response}', but got '{bot_response}'"