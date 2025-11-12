import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from .state import State
from .config import APP_CONFIG

def _load_prompt_template() -> str:
    """Loads the safety check prompt template from the file."""
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "safety_check.txt")
    with open(prompt_path, "r") as f:
        return f.read()

def check_safety(state: State) -> State:
    """
    Checks the user's message for safety and compliance using an LLM.
    """
    print("--- Checking safety ---")
    user_message = state["conversation_history"][-1]["content"]

    prompt_template_str = _load_prompt_template()
    prompt = ChatPromptTemplate.from_template(prompt_template_str)
    
    llm = ChatOpenAI(model=APP_CONFIG["llm_model"], temperature=0.0)
    chain = prompt | llm | JsonOutputParser()
    
    response = chain.invoke({"message": user_message})
    
    classification = response.get("safety_classification", "safe").lower()
    
    if classification == "safe":
        print("Message is safe.")
        return {**state, "is_safe": True, "guardrail_violation": None}
    else:
        print("Message is not safe.")
        return {
            **state, 
            "is_safe": False, 
            "guardrail_violation": "Unsafe content detected.",
            "message": "I'm sorry, I cannot process that request. It violates our safety policies."
        }
