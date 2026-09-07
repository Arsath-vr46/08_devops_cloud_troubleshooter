"""
app.py - Production Flask application for domain-specific AI copilot.
"""
import os
import logging
from flask import Flask, render_template, request, jsonify
from google import genai
from google.genai import types

from chatbot_config import (
    CHATBOT_TITLE,
    DOMAIN_NAME,
    ALLOWED_TOPICS,
    OUT_OF_DOMAIN_REFUSAL_MESSAGE,
    SYSTEM_PROMPT
)
from firebase_config import fetch_all_firestore_knowledge

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize GenAI client via GEMINI_API_KEY environment variable
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None

@app.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html",
        title=CHATBOT_TITLE,
        domain_name=DOMAIN_NAME,
        allowed_topics=ALLOWED_TOPICS
    )

@app.route("/api/chat", methods=["POST"])
def chat():
    if not client:
        return jsonify({
            "reply": "Service Error: GEMINI_API_KEY environment variable is not configured on the server."
        }), 500

    payload = request.get_json(silent=True) or {}
    user_message = payload.get("message", "").strip()
    history = payload.get("history", [])

    if not user_message:
        return jsonify({"reply": "Please provide a valid query."}), 400

    try:
        # 1. Fetch dynamic domain ground truth from Firestore
        db_knowledge = fetch_all_firestore_knowledge()

        # 2. Combine system prompt with retrieved database context
        full_system_instruction = (
            f"{SYSTEM_PROMPT}\n\n"
            f"If Firestore data is provided below, treat it as STRICT GROUND TRUTH:\n"
            f"{db_knowledge}\n"
            f"If user query falls completely outside: {ALLOWED_TOPICS}, "
            f"politely reply with: \"{OUT_OF_DOMAIN_REFUSAL_MESSAGE}\""
        )

        # 3. Format conversational multi-turn contents for Gemini SDK
        contents = []
        for turn in history:
            role = "user" if turn.get("role") == "user" else "model"
            parts_raw = turn.get("parts", [])
            text_val = parts_raw[0] if (parts_raw and isinstance(parts_raw, list)) else str(parts_raw)
            if text_val:
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=text_val)]))

        # Add current user prompt
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

        # 4. Invoke gemini-3.1-flash-lite
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=full_system_instruction,
                temperature=0.2,
            )
        )

        reply_text = response.text if response and response.text else "No response could be generated."
        return jsonify({"reply": reply_text})

    except Exception as e:
        logger.error("Chat generation failed: %s", e)
        return jsonify({"reply": "An error occurred while evaluating your request. Please try again."}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
