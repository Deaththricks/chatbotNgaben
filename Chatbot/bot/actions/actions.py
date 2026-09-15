"""Custom actions for the GraphRAG Ngaben bot using Neo4j and Qwen via Ollama."""
import os
import json
from typing import Any, Dict, List, Text, Optional

from dotenv import find_dotenv, load_dotenv
from neo4j import GraphDatabase
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv(find_dotenv())

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# Initialize Qwen via Ollama
llm = ChatOllama(model="qwen2.5", temperature=0)

class Neo4jConnection:
    def __init__(self, uri: str, user: str, password: str) -> None:
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def query(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        try:
            with self._driver.session() as session:
                return [r.data() for r in session.run(cypher, params or {})]
        except Exception as e:
            print(f"Neo4j Error: {e}")
            return []

    def close(self) -> None:
        self._driver.close()

neo4j_conn = Neo4jConnection(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

class ActionGraphRAG(Action):
    def name(self) -> Text:
        return "action_graph_rag"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        user_msg = tracker.latest_message.get("text", "")
        current_entity = tracker.get_slot("current_entity")
        
        # Step 1: Zero-Shot Entity Resolution via Qwen
        resolve_prompt = f"""
        You are an exact entity extractor for a Balinese Ngaben database.
        User Input: "{user_msg}"
        Previous Context: "{current_entity or 'None'}"
        
        Task: Identify the single main Balinese term the user is asking about. 
        - Fix common typos (e.g., "panca maha buta" must become "pancamahabutha").
        - If they use a pronoun like "itu", use the Previous Context.
        - Return ONLY the canonical name of the entity in lowercase. No extra text, no punctuation, no explanations.
        """
        resolved_entity = llm.invoke([HumanMessage(content=resolve_prompt)]).content.strip().lower()
        
        # Step 2: Retrieve from Neo4j
        cypher_query = """
        MATCH (n:Node)
        WHERE toLower(n.name) CONTAINS $entity_name OR toLower(n.id) = $entity_name
        OPTIONAL MATCH (n)-[r]-(m:Node)
        WHERE coalesce(r.confidence, '') <> 'LOW'
        RETURN n.name AS name, 
               coalesce(n.definition, 'Tidak ada definisi langsung') AS definition, 
               labels(n) AS labels, 
               collect(DISTINCT {
                 relation: type(r), 
                 target: m.name, 
                 target_labels: labels(m)
               })[..15] AS relationships
        LIMIT 1
        """
        graph_data = neo4j_conn.query(cypher_query, {"entity_name": resolved_entity})
        
        if not graph_data:
            dispatcher.utter_message(text=f"Maaf, saya tidak menemukan informasi spesifik tentang '{resolved_entity}' di basis data.")
            return [SlotSet("current_entity", None)]
            
        raw_context = json.dumps(graph_data[0], indent=2)
        
        # Step 3: Synthesis via Qwen
        synth_sys_prompt = """
        You are a strict, factual assistant for the Balinese Ngaben ceremony.
        
        RULES:
        1. Answer the user's question ONLY using the provided Neo4j Graph Data context.
        2. If the 'definition' field says 'Tidak ada definisi langsung', DO NOT make up a generic dictionary definition. Instead, explain what the term is by synthesizing its 'relationships' (e.g., what it is made of, its role, or related terms).
        3. If the provided Graph Data does NOT contain the specific answer or detail requested by the user, you MUST reply with exactly: "Maaf, informasi detail mengenai hal tersebut belum tercatat di basis data." Do not attempt to guess or fill in the blanks.
        4. NEVER fabricate translations, ritual steps, physical descriptions, or lore that are not explicitly stated in the JSON.
        5. Answer in natural, fluid Indonesian.
        """ 
        answer = llm.invoke([
            SystemMessage(content=synth_sys_prompt), 
            HumanMessage(content=synth_user_prompt)
        ]).content
        
        dispatcher.utter_message(text=answer)
        
        # Step 4: Save Context Memory
        return [SlotSet("current_entity", graph_data[0]['name'])]

class ActionLLMFallback(Action):
    def name(self) -> Text:
        return "action_llm_fallback"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        user_msg = tracker.latest_message.get("text", "")
        
        fallback_prompt = f"""
        You are an assistant for Balinese Ngaben. A user asked: "{user_msg}". 
        Answer conversationally in Indonesian. If the question is weird, provide a safe, general answer about Ngaben.
        """
        answer = llm.invoke([HumanMessage(content=fallback_prompt)]).content
        dispatcher.utter_message(text=answer)
        return []