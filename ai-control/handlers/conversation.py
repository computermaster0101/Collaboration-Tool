from typing import Dict, List, Any
import uuid

class ConversationHandler:
    def __init__(self):
        self.conversations: Dict[str, List[Dict[str, Any]]] = {}
        
    def create_conversation(self, name: str) -> str:
        conversation_id = str(uuid.uuid4())
        self.conversations[conversation_id] = []
        return conversation_id
        
    def get_conversation(self, conversation_id: str) -> List[Dict[str, Any]]:
        return self.conversations.get(conversation_id, [])
        
    def add_message(self, conversation_id: str, message: Dict[str, Any]):
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        self.conversations[conversation_id].append(message)

    def truncate_history(self, conversation_id: str, max_messages: int = 100):
        if conversation_id in self.conversations:
            self.conversations[conversation_id] = self.conversations[conversation_id][-max_messages:]