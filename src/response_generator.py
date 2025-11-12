import os
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from .config import APP_CONFIG
from .state import State

class ResponseGenerator:
    """Generates dynamic responses using an LLM based on the conversation state and intent."""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=APP_CONFIG["llm_model"],
            temperature=APP_CONFIG["llm_temperature"]
        )
        self.prompt_template = self._load_prompt_template()
        self.chain = ChatPromptTemplate.from_messages([
            ("system", self.prompt_template),
            ("human", "Generate response.") # The actual message is in the prompt context
        ]) | self.llm | StrOutputParser()

    def _load_prompt_template(self) -> str:
        """Loads the response generator prompt template from the file."""
        prompt_path = os.path.join(os.path.dirname(__file__), "..", "config", "response_generator.txt")
        with open(prompt_path, "r") as f:
            return f.read()

    def generate(self, state: State, intent: str, data: dict = None) -> str:
        """Generates a response based on the current state, intent, and additional data."""
        history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in state["conversation_history"]])
        
        # Ensure data is a JSON string for the prompt
        data_str = json.dumps(data if data is not None else {}, indent=2)

        response = self.chain.invoke({
            "history": history,
            "intent": intent,
            "data": data_str
        })
        return response.strip()

# Create a singleton instance of the ResponseGenerator
response_generator = ResponseGenerator()
