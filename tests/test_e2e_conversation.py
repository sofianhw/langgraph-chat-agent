import pytest
from src.main import create_graph
from src.state import State
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from src.config import APP_CONFIG

# --- AI Judge for Semantic Assertion ---
def evaluate_response_with_llm(expected_response: str, actual_response: str) -> bool:
    """Uses an LLM to judge if the actual response semantically matches the expected one."""
    
    prompt_template = """You are a test evaluator for a conversational banking agent. 
    Your task is to determine if the "Actual Response" from the agent is a correct and satisfactory answer, based on the "Expected Response".
    The actual response does not need to be an exact match, but it must convey the same core information and intent. Pay close attention to amounts, names, and confirmations.

    Expected Response:
    "{expected}"

    Actual Response:
    "{actual}"

    Is the actual response a semantically correct match to the expected response?
    Respond with a JSON object containing a single key: "is_correct" (boolean).
    """
    
    prompt = ChatPromptTemplate.from_template(prompt_template)
    llm = ChatOpenAI(model=APP_CONFIG["llm_model"], temperature=0)
    chain = prompt | llm | JsonOutputParser()
    
    try:
        result = chain.invoke({
            "expected": expected_response,
            "actual": actual_response
        })
        return result.get("is_correct", False)
    except Exception as e:
        print(f"Error during LLM evaluation: {e}")
        return False

# --- Test Data ---
conversation_flow = [
    ("i wanna transfer", "Who do you want to send money to?"),
    ("anna", "How much do you want to send to anna?"),
    ("what is my balance?", "Your current balance is $1,000.00."),
    ("what is transfer limit per day?", "Transfer limit per day is $10,000. How much would you like to transfer to Anna?"),
    ("okey transfer 10", "Please confirm transfer to anna of $10.0. Approve or cancel?"),
    ("how much my money will be after transfer?", "Your current balance is $1,000.00. After transferring $10.00, your new balance will be $990.00. Do you want to confirm the transfer to anna of $10.00?"),
    ("confirm", "What is the name of the recipient's bank?"),
    ("bca", "What is the recipient's account number?"),
    ("12345", "Transfer to anna of $10.0 at bca (account: 12345) confirmed. Your transaction succeeded."),
]

@pytest.mark.e2e
def test_full_conversation_flow():
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

    log_file = "conversation_log.txt"
    with open(log_file, "w") as f:
        f.write("--- Conversation Log ---\n\n")

        for user_input, expected_bot_response in conversation_flow:
            f.write(f"You: {user_input}\n")
            
            current_state["conversation_history"].append({"role": "user", "content": user_input})
            
            final_state = app.invoke(current_state)
            
            current_state = {**current_state, **final_state}

            bot_response = ""
            if final_state.get("answer"):
                bot_response += final_state["answer"]
            if final_state.get("message"):
                if bot_response:
                    bot_response += "\n"
                bot_response += final_state["message"]
            
            bot_response = bot_response.strip()
            f.write(f"Bot: {bot_response}\n\n")
            
            # Use the AI judge for a more robust assertion
            is_correct = evaluate_response_with_llm(expected_bot_response, bot_response)
            assert is_correct, f"AI judge failed: Expected '{expected_bot_response}', but got '{bot_response}'"

            current_state["conversation_history"].append({"role": "assistant", "content": bot_response})
            current_state["message"] = None
            current_state["answer"] = None

            if final_state.get("status") in ["COMPLETED", "CANCELLED"]:
                current_state["transaction_fields"] = {}
                current_state["inquiry_fields"] = {}
                current_state["pending_task"] = None
                current_state["task_stage"] = None
                current_state["status"] = None

    print(f"\nConversation log saved to {log_file}")
