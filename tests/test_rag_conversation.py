import pytest
from src.main import create_graph
from src.state import State
from tests.test_e2e_conversation import evaluate_response_with_llm

@pytest.mark.rag
def test_rag_faq_question():
    """Tests the RAG agent's ability to answer a question from the knowledge base."""
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

    user_input = "How can I order a new checkbook?"
    expected_bot_response = "You can order a new checkbook through our mobile app or by visiting any of our branches."

    current_state["conversation_history"].append({"role": "user", "content": user_input})
    
    final_state = app.invoke(current_state)
    
    bot_response = ""
    if final_state.get("answer"):
        bot_response += final_state["answer"]
    if final_state.get("message"):
        if bot_response:
            bot_response += "\n"
        bot_response += final_state["message"]
    
    bot_response = bot_response.strip()

    # Use the AI judge for a more robust assertion
    is_correct = evaluate_response_with_llm(expected_bot_response, bot_response)
    assert is_correct, f"AI judge failed for RAG test: Expected '{expected_bot_response}', but got '{bot_response}'"
