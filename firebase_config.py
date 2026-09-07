"""
firebase_config.py - Dynamic Firestore knowledge aggregator with safe fallbacks.
"""
import os
import json
import logging
import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger(__name__)

_db = None

def init_firebase():
    """Safely initialize Firebase Admin SDK using local key file."""
    global _db
    if _db is not None:
        return _db

    key_path = os.path.join(os.path.dirname(__file__), "firebase-key.json")
    if not os.path.exists(key_path):
        logger.warning("firebase-key.json not found. Proceeding in standalone memory mode.")
        return None

    try:
        with open(key_path, "r", encoding="utf-8") as f:
            key_data = json.load(f)
            
        # Check for placeholder credentials
        if "REPLACE_WITH" in key_data.get("private_key_id", "") or "your-firebase-project-id" in key_data.get("project_id", ""):
            logger.info("firebase-key.json contains placeholder values. Running without Firestore connectivity.")
            return None

        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
        _db = firestore.client()
        return _db
    except Exception as e:
        logger.warning("Failed to initialize Firebase Admin SDK: %s. Using fallback mode.", e)
        return None

def fetch_all_firestore_knowledge():
    """
    Scans all root Firestore collections and documents dynamically.
    Returns a unified, human-readable summary string for LLM prompting.
    """
    db = init_firebase()
    if not db:
        return ""

    knowledge_entries = []
    try:
        collections = db.collections()
        for col in collections:
            col_id = col.id
            docs = col.stream()
            for doc in docs:
                data = doc.to_dict()
                knowledge_entries.append(f"[{col_id} -> Doc ID: {doc.id}]: {json.dumps(data, ensure_ascii=False)}")
    except Exception as e:
        logger.error("Error reading Firestore knowledge base: %s", e)
        return ""

    if not knowledge_entries:
        return ""

    return "\n=== LIVE FIRESTORE KNOWLEDGE BASE ===\n" + "\n".join(knowledge_entries) + "\n====================================\n"
