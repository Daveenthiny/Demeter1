import os
import json
import boto3
from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid  # <-- Import the uuid module

app = Flask(__name__)
# Configure CORS for Amplify frontend domain
CORS(app, resources={r"/ask-agent": {"origins": "https://main.dgchwyhaw9222.amplifyapp.com"}})

# Configuration (Use Environment Variables in App Runner)
AGENT_ID = os.environ.get("BEDROCK_AGENT_ID", "YOUR_AGENT_ID") # Ensure this is set in App Runner env vars
AGENT_ALIAS_ID = os.environ.get("BEDROCK_AGENT_ALIAS_ID", "YOUR_AGENT_ALIAS_ID") # Ensure this is set in App Runner env vars
REGION = os.environ.get("AWS_REGION", "us-east-1") # Ensure this is set in App Runner env vars

# Initialize Bedrock client (same as Lambda version)
try:
    # Use the configured REGION
    bedrock_runtime = boto3.client('bedrock-agent-runtime', region_name=REGION)
    print(f"Bedrock client initialized for region: {REGION}")
except Exception as e:
    print(f"Error initializing Bedrock client in region {REGION}: {e}")
    bedrock_runtime = None

@app.route('/ask-agent', methods=['POST'])
def ask_agent():
    # Check if the Bedrock client was initialized successfully
    if not bedrock_runtime:
         print("Bedrock client is not initialized.")
         return jsonify({"error": "Bedrock client not initialized. Check App Runner logs for initialization errors."}), 500

    data = request.json
    if not data:
         return jsonify({"error": "Invalid JSON received"}), 400

    user_input = data.get('question', '')
    # --- CORRECTED LINE ---
    # Get session ID from request or generate a new one using uuid
    session_id = data.get('sessionId', str(uuid.uuid4()))
    # -----------------------

    # Basic input validation
    if not user_input:
        print("No question provided in the request.")
        return jsonify({"answer": "No question provided."}), 400

    print(f"Received request - Session ID: {session_id}, Question: {user_input}")

    # Ensure AGENT_ID and AGENT_ALIAS_ID are loaded from environment variables
    current_agent_id = os.environ.get("BEDROCK_AGENT_ID", AGENT_ID)
    current_agent_alias_id = os.environ.get("BEDROCK_AGENT_ALIAS_ID", AGENT_ALIAS_ID)

    if current_agent_id == "YOUR_AGENT_ID" or current_agent_alias_id == "YOUR_AGENT_ALIAS_ID":
         print("Agent ID or Alias ID not set in environment variables.")
         return jsonify({"error": "Bedrock Agent ID or Alias ID is not configured."}), 500


    try:
        print(f"Invoking agent: ID={current_agent_id}, Alias={current_agent_alias_id}, Session={session_id}")
        # Invoke the Bedrock Agent using the runtime client
        response = bedrock_runtime.invoke_agent(
            agentId=current_agent_id,
            agentAliasId=current_agent_alias_id,
            sessionId=session_id, # Use the determined session ID
            inputText=user_input,
            enableTrace=False # Set to True for debugging agent execution
        )

        print("Agent invocation response received.")

        # Process the streaming response from the agent
        answer = ""
        # The response is a stream, iterate through chunks
        completion = response.get('completion') # Get the 'completion' event stream

        if completion:
            print("Processing completion stream...")
            for event in completion:
                # Each event dictionary should contain a 'chunk' key for text
                if 'chunk' in event:
                    chunk = event['chunk']
                    payload_bytes = chunk.get('bytes', b'')
                    try:
                        # Decode the bytes payload to get the text chunk
                        text_chunk = payload_bytes.decode('utf-8')
                        answer += text_chunk
                        # Optional: print chunks as they arrive for debugging streaming
                        # print(f"Received chunk: {text_chunk}")
                    except UnicodeDecodeError:
                        print("Warning: Could not decode chunk as UTF-8.")
                        # Handle decoding error if necessary, e.g., append raw bytes repr
                # Add handling for other event types if needed (e.g., trace)
                # if 'trace' in event:
                #    print(f"Trace event received: {event['trace']}")
            print("Completion stream processing finished.")
        else:
            print("Warning: No 'completion' stream key found in response.")
            answer = "Agent response format unexpected."

        print("Agent final answer assembled.")
        # Return the assembled answer in a JSON response
        return jsonify({"answer": answer or "No answer received from agent."})

    except Exception as e:
        # Catch any exceptions during the invocation or processing
        print(f"Error invoking agent or processing response: {e}")
        # Provide a more informative error message in the response
        return jsonify({"error": f"Failed to invoke agent or process response: {str(e)}"}), 500


# Simple health check endpoint (optional but recommended for App Runner)
@app.route('/health', methods=['GET'])
def health_check():
    # Basic health check: just return OK
    return 'OK', 200


# This __main__ block is typically not used when running with Gunicorn
# The Dockerfile CMD "gunicorn ..." handles starting the app
if __name__ == '__main__':
    # In a local development environment you might use:
    # app.run(debug=True, host='0.0.0.0', port=8080)
    pass # Gunicorn is typically run via CMD in Dockerfile