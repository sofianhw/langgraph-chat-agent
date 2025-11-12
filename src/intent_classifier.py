import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from .state import State
from .config import APP_CONFIG
from .task_registry import task_registry

def _load_prompt_template() -> str:
    """Loads the intent classifier prompt template from the file."""
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "intent_classifier.txt")
    with open(prompt_path, "r") as f:
        return f.read()

def classify_intent(state: State) -> State:
    """
    Classifies the user's intent and extracts entities using a dynamically generated prompt.
    """
    print("--- Classifying intent ---")
    
    user_message = state["conversation_history"][-1]["content"]

    # Dynamically generate context for the prompt
    valid_intents = ["GREETING", "CANCEL", "CONFIRM", "CLARIFICATION", "CHITCHAT"] + list(task_registry.tasks.keys())
    
    all_fields = set()
    for task in task_registry.tasks.values():
        for field in task.get("required_fields", []):
            all_fields.add(f"- '{field}'")
    entities_to_extract = "\n".join(sorted(list(all_fields)))

    inquiry_types_context = ""
    inquiry_types = task_registry.get_inquiry_types()
    for itype in inquiry_types:
        inquiry_types_context += f"    - '{itype['name']}': {itype['description']}\n"

    # Get pending task name safely
    pending_task = state.get("pending_task")
    pending_task_name = pending_task.get("type", "None") if pending_task else "None"

    # Load the raw prompt template
    prompt_template_str = _load_prompt_template()

    # Create the prompt template and the chain
    prompt = ChatPromptTemplate.from_messages([
        ("system", prompt_template_str),
        ("human", "{message}"),
    ])
    
    llm = ChatOpenAI(model=APP_CONFIG["llm_model"], temperature=APP_CONFIG["llm_temperature"])
    chain = prompt | llm | JsonOutputParser()
    
    history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in state["conversation_history"]])
    
    # Invoke the chain with all required variables for the template
    response = chain.invoke({
        "message": user_message, 
        "history": history,
        "valid_intents": ", ".join(valid_intents),
        "entities_to_extract": entities_to_extract,
        "inquiry_types_context": inquiry_types_context,
        "pending_task": pending_task_name
    })
    
    intent = response.get("intent", "CLARIFICATION")
    print(f"Intent classified as: {intent}")

    # Post-processing to refine CLARIFICATION intent for common cases
    user_message_lower = user_message.lower()
    if intent == "CLARIFICATION":
        if any(keyword in user_message_lower for keyword in ["thank you", "thanks", "goodbye", "bye"]):
            intent = "FAREWELL"
        elif any(keyword in user_message_lower for keyword in ["how are you", "you are a bot", "who are you"]):
            intent = "CHITCHAT"
        elif any(keyword in user_message_lower for keyword in ["capital of", "joke", "weather"]):
            intent = "OUT_OF_TOPIC"

    if intent not in valid_intents:
        intent = "CLARIFICATION"

    # Update fields based on extracted entities
    transaction_fields = state.get("transaction_fields", {})
    inquiry_fields = state.get("inquiry_fields", {})

    for key, value in response.items():
        if key != "intent" and value is not None:
            # Decide where to put the extracted field
            if key in task_registry.get_task("Transfer funds").get("required_fields", []):
                if key == 'amount':
                    try:
                        transaction_fields[key] = float(value)
                    except (ValueError, TypeError):
                        transaction_fields[key] = value 
                else:
                    transaction_fields[key] = value
            elif key in task_registry.get_task("INQUIRY").get("required_fields", []):
                 inquiry_fields[key] = value

    return {
        **state,
        "current_intent": intent,
        "transaction_fields": transaction_fields,
        "inquiry_fields": inquiry_fields,
    }
