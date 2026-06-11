import streamlit as st
import asyncio
import os
import sys
import json
import uuid
import queue
import threading
import dotenv
from typing import Generator

# Load environment configuration
ENV_PATH = os.path.join(os.path.dirname(__file__), "adk_agent/mcp_bakery_app/.env")
dotenv.load_dotenv(dotenv_path=ENV_PATH)

# Add adk_agent directory to sys.path to allow importing mcp_bakery_app
sys.path.append(os.path.join(os.path.dirname(__file__), "adk_agent"))

try:
    from mcp_bakery_app.agent import root_agent
    from google.adk.runners import InMemoryRunner
    from google.genai import types
except ImportError as e:
    st.error(f"Failed to import ADK agent modules: {e}")
    st.stop()

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="Launch My Bakery AI Assistant",
    page_icon="🥖",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for Premium Design & Fonts
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Playfair+Display:ital,wght@0,600;1,400&display=swap');

/* Main font styling */
html, body, [class*="css"], .stMarkdown {
    font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Stunning Gradient Title */
.title-container {
    background: linear-gradient(135deg, #FF9933 0%, #FF5E36 50%, #9E00C5 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-align: center;
    font-weight: 800;
    font-size: 3.2rem;
    margin-bottom: 0px;
    padding-bottom: 0px;
}

.subtitle {
    text-align: center;
    color: #8C8C8C;
    font-size: 1.1rem;
    margin-top: -10px;
    margin-bottom: 30px;
    font-weight: 300;
}

/* Glassmorphism card for instructions */
.instructions-card {
    background: rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 25px;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
}

/* Chat bubble enhancements */
.stChatMessage {
    border-radius: 16px;
    padding: 12px 16px;
    margin-bottom: 12px;
}

/* Add custom animations/transitions */
button {
    transition: all 0.3s ease-in-out !important;
}
button:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(255, 94, 54, 0.3) !important;
}

/* Custom design for status log */
div[data-testid="stStatus"] {
    background-color: rgba(255, 94, 54, 0.08);
    border: 1px solid rgba(255, 94, 54, 0.2);
    border-radius: 12px;
}

</style>
""", unsafe_allow_html=True)

# App Header
st.markdown('<div class="title-container">🥖 Launch My Bakery</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">LA Sourdough Location & Strategy AI Advisor</div>', unsafe_allow_html=True)

# Initialize Session States
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "runner" not in st.session_state:
    # Build InMemoryRunner and enable auto-session creation
    runner = InMemoryRunner(agent=root_agent)
    runner.auto_create_session = True
    st.session_state.runner = runner

# Sidebar with demo controls
with st.sidebar:
    st.title("Settings")
    st.info(f"Session ID: `{st.session_state.session_id}`")
    if st.button("Reset Chat Session"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        # Recreate runner
        runner = InMemoryRunner(agent=root_agent)
        runner.auto_create_session = True
        st.session_state.runner = runner
        st.rerun()

# Welcome / Instructions banner
if len(st.session_state.messages) == 0:
    st.markdown("""
    <div class="instructions-card">
        <h4>💡 Welcome to your Bakery Business Advisor!</h4>
        <p>This AI Agent utilizes <strong>Google Maps MCP</strong> for real-world LA location analysis and 
        <strong>BigQuery MCP</strong> to study LA demographics, foot traffic, competitor pricing, and sales history.</p>
        <p><strong>Try asking questions like:</strong></p>
        <ul>
            <li><em>"I need a neighborhood with early activity in LA. Find the zip code with the highest morning foot traffic."</em></li>
            <li><em>"Search for bakeries in that zip code to check if it's saturated. If so, find Specialty Coffee shops."</em></li>
            <li><em>"What is the premium pricing model for a Sourdough Loaf in the LA Metro area?"</em></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Async-to-Sync Generator Runner using Queue
def run_agent_sync(runner, message, session_id) -> Generator[types.Content, None, None]:
    q = queue.Queue()
    
    def run_async_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def run():
            try:
                async for event in runner.run_async(
                    user_id="streamlit_user",
                    session_id=session_id,
                    new_message=message
                ):
                    q.put(("event", event))
            except Exception as e:
                q.put(("error", e))
            finally:
                q.put(("done", None))
                
        loop.run_until_complete(run())
        loop.close()
        
    thread = threading.Thread(target=run_async_loop)
    thread.start()
    
    while True:
        item_type, val = q.get()
        if item_type == "event":
            yield val
        elif item_type == "error":
            raise val
        elif item_type == "done":
            break

# Handle Chat Input
if prompt := st.chat_input("Message the Bakery Assistant..."):
    # Render user query
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Render assistant response block
    with st.chat_message("assistant"):
        # Setup content model
        message_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)]
        )
        
        final_text = ""
        
        # Display real-time progress using st.status
        with st.status("Thinking...", expanded=True) as status:
            try:
                for event in run_agent_sync(st.session_state.runner, message_content, st.session_state.session_id):
                    # Inspect function calls (tools being called)
                    func_calls = event.get_function_calls()
                    if func_calls:
                        for fc in func_calls:
                            st.markdown(f"🔍 **Executing Tool**: `{fc.name}`")
                            if fc.args:
                                st.code(json.dumps(fc.args, indent=2), language="json")
                                
                    # Inspect function responses (tool output received)
                    func_responses = event.get_function_responses()
                    if func_responses:
                        for fr in func_responses:
                            st.markdown(f"✅ **Received response from**: `{fr.name}`")
                    
                    # Accumulate text response
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.text:
                                final_text += part.text
                
                status.update(label="Analysis complete!", state="complete", expanded=False)
            except Exception as e:
                status.update(label="An error occurred!", state="error", expanded=True)
                st.error(f"Error executing agent: {e}")
                st.stop()
        
        # Display the final aggregated answer
        if final_text:
            st.markdown(final_text)
            st.session_state.messages.append({"role": "assistant", "content": final_text})
