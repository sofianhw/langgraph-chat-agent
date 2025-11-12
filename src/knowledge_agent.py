import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from .state import State
from .config import APP_CONFIG
from .response_generator import response_generator # Import the response_generator

class KnowledgeAgent:
    """A generic agent for handling FAQ (RAG) and general inquiries."""

    def __init__(self, task_registry):
        self.task_registry = task_registry
        self.llm = ChatOpenAI(
            model=APP_CONFIG["llm_model"],
            temperature=APP_CONFIG["llm_temperature"]
        )
        self.rag_chain = self._initialize_rag_chain()

    def _initialize_rag_chain(self):
        """Initializes the RAG chain for FAQ retrieval."""
        faq_path = os.path.join(os.path.dirname(__file__), '..', APP_CONFIG["faq_path"])
        if not os.path.exists(faq_path):
            print(f"Warning: FAQ file not found at {faq_path}. FAQ agent will not function.")
            return None

        with open(faq_path, "r") as f:
            faq_content = f.read()

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        docs = text_splitter.create_documents([faq_content])

        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        vectorstore = FAISS.from_documents(docs, embeddings)
        retriever = vectorstore.as_retriever(search_kwargs={"k": APP_CONFIG["rag_top_k"]})

        rag_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful banking assistant. Use the following context to answer the user's question:

{context}"""),
            ("user", "{question}")
        ])

        return (
            {"context": retriever, "question": StrOutputParser()}
            | rag_prompt
            | self.llm
            | StrOutputParser()
        )

    def handle_faq(self, state: State) -> State:
        """Handles FAQ intents using a RAG approach."""
        print("--- FAQ processing (Generic Knowledge Agent) ---")
        user_message = state["conversation_history"][-1]["content"]
        
        if self.rag_chain:
            answer = self.rag_chain.invoke(user_message)
        else:
            answer = response_generator.generate(state, "ERROR", {"details": "FAQ knowledge base is not available."})
        
        return {**state, "answer": answer, "source_urls": []}

    def handle_inquiry(self, state: State) -> State:
        """Handles general inquiry intents by interpreting the declarative config."""
        print("--- Inquiry processing (Generic Knowledge Agent) ---")
        extracted_type = state["inquiry_fields"].get("inquiry_type", "").lower()
        answer = response_generator.generate(state, "ERROR", {"details": f"I can't answer questions about '{extracted_type}' at the moment."})

        inquiry_types = self.task_registry.get_inquiry_types()
        matched_type = None

        for itype in inquiry_types:
            if extracted_type == itype["name"] or extracted_type in itype["aliases"]:
                matched_type = itype["name"]
                break
        
        if matched_type == "balance":
            simulated_balance = 1000.00  # Match the README
            pending_task = state.get("pending_task")
            transaction_fields = state.get("transaction_fields", {})

            if pending_task and pending_task.get("type") == "Transfer funds" and "amount" in transaction_fields:
                amount = float(transaction_fields["amount"])
                new_balance = simulated_balance - amount
                answer = response_generator.generate(state, "BALANCE_INQUIRY", {"current_balance": simulated_balance, "transfer_amount": amount, "new_balance": new_balance})
            elif pending_task and pending_task.get("type") == "Transfer funds":
                # If transfer is pending but amount is not known, provide balance and then re-prompt for amount
                balance_info = response_generator.generate(state, "BALANCE_INQUIRY", {"current_balance": simulated_balance, "pending_transfer": True})
                from .flow_agent import flow_agent
                reprompt_message = flow_agent.get_current_step_question(state)
                # Combine balance info with the specific re-prompt for the amount
                answer = f"{balance_info}\n{reprompt_message}" if reprompt_message else balance_info
            else:
                answer = response_generator.generate(state, "BALANCE_INQUIRY", {"current_balance": simulated_balance})

        elif matched_type == "remaining_transfer_limit":
            # Simulate a remaining limit for now.
            # In a real scenario, this would be calculated based on user's transaction history.
            daily_limit = APP_CONFIG["banking"]["transfer_limit_daily"]
            simulated_used_amount = 2500
            remaining_limit = daily_limit - simulated_used_amount
            answer = response_generator.generate(state, "REMAINING_TRANSFER_LIMIT_INQUIRY", {"remaining_limit": remaining_limit, "daily_limit": daily_limit})

        return {**state, "answer": answer, "reprompt_handled": True}
