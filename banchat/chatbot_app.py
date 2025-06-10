# chatbot_app.py (FINAL, WORKING VERSION)
import streamlit as st
import os
import json
import requests
from dotenv import load_dotenv

# Import our helper modules
from bannerbear_helpers import list_templates, get_template_details, create_image, poll_for_image
from gemini_helpers import get_gemini_model, generate_gemini_response

# --- Page Configuration & API Keys ---
st.set_page_config(page_title="AI Design Assistant", layout="centered")

load_dotenv()
BB_API_KEY = os.getenv("BANNERBEAR_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BB_API_KEY or not GEMINI_API_KEY:
    st.error("API keys for Bannerbear or Gemini are missing. Check your .env file.")
    st.stop()

# --- Session State Initialization ---
def initialize_session_state():
    defaults = {
        "messages": [{"role": "assistant", "content": "Hello! I'm your AI design assistant. Type **choose template** to begin."}],
        "gemini_model": get_gemini_model(GEMINI_API_KEY),
        "selected_template_details": None,
        "current_modifications": [],
        "download_image": None
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

# --- Handler Functions ---

def handle_template_selection(template_summary):
    """
    THIS IS THE FULLY CORRECTED FUNCTION.
    It now uses the 'available_modifications' key from the user's provided data.
    """
    st.session_state.messages = [msg for msg in st.session_state.messages if not (isinstance(msg["content"], dict) and msg["content"].get("type") == "template_picker")]
    st.session_state.messages.append({"role": "user", "content": f"I'll use the '{template_summary['name']}' template."})

    with st.spinner(f"Loading details for '{template_summary['name']}'..."):
        full_template_details = get_template_details(BB_API_KEY, template_summary['uid'])
    
    if not full_template_details:
        st.session_state.messages.append({"role": "assistant", "content": "Sorry, I failed to load the detailed information for that template."})
        return

    st.session_state.selected_template_details = full_template_details
    
    # --- THE DEFINITIVE, FINAL FIX IS HERE ---
    modifications = []
    layer_names = []
    try:
        # Use the correct key based on the user's provided JSON data.
        layers_data = full_template_details['available_modifications']
        for layer_info in layers_data:
            layer_name = layer_info['name']
            layer_names.append(f"`{layer_name}`")
            
            # This is exactly what the create_image API call needs.
            modifications.append(layer_info)

        st.session_state.current_modifications = modifications
    except KeyError:
        # This is the final safeguard, but it should not be triggered now.
        st.session_state.messages.append({"role": "assistant", "content": "Critical Error: The key 'available_modifications' was not found in the template data."})
        return
    # --- END OF THE FIX ---

    layer_list_str = "\n- ".join(layer_names)
    st.session_state.messages.append({
        "role": "assistant",
        "content": f"Success! I've loaded the **'{full_template_details['name']}'** template.\n\n"
                   f"Here are the layers you can edit:\n- {layer_list_str}\n\n"
                   "You can now ask me to change things, like 'Set the title to...'. "
                   "When you're ready, type **generate image**."
    })

def handle_gemini_function_call(function_call):
    layer_name = function_call.args.get("layer_name")
    
    found_layer = False
    for mod in st.session_state.current_modifications:
        if mod["name"] == layer_name:
            if "new_text" in function_call.args:
                mod["text"] = function_call.args["new_text"]
            elif "new_image_url" in function_call.args:
                mod["image_url"] = function_call.args["new_image_url"]
            st.session_state.messages.append({"role": "assistant", "content": f"✅ Updated `{layer_name}`."})
            found_layer = True
            break
            
    if not found_layer:
        st.session_state.messages.append({"role": "assistant", "content": f"⚠️ I couldn't find a layer named `{layer_name}`. Please use one of the available layer names."})

def handle_image_generation():
    if not st.session_state.selected_template_details:
        st.session_state.messages.append({"role": "assistant", "content": "Please `choose template` before trying to generate an image."})
        return

    st.session_state.messages.append({"role": "assistant", "content": "Got it! Generating your image..."})
    
    # We need to filter out any 'null' values before sending to the API
    final_modifications = []
    for mod in st.session_state.current_modifications:
        # Create a new dict with only non-null values
        clean_mod = {key: value for key, value in mod.items() if value is not None}
        final_modifications.append(clean_mod)

    with st.spinner("Step 1/2: Submitting request..."):
        initial_response = create_image(
            BB_API_KEY, 
            st.session_state.selected_template_details['uid'], 
            final_modifications
        )
    if not initial_response:
        st.session_state.messages.append({"role": "assistant", "content": "❌ Failed to start image generation. Check API Key & Bannerbear Dashboard."})
        return

    with st.spinner("Step 2/2: Rendering image..."):
        final_image = poll_for_image(BB_API_KEY, initial_response)
        
    if final_image and final_image.get("image_url_png"):
        image_url = final_image["image_url_png"]
        st.session_state.messages.append({"role": "assistant", "content": f"🎉 Here is your generated image! \n\n![Generated Image]({image_url})"})
        try:
            image_bytes = requests.get(image_url).content
            st.session_state.download_image = {"bytes": image_bytes, "name": f"generated_{final_image['uid']}.png"}
            st.session_state.messages.append({"role": "assistant", "content": "DOWNLOAD_BUTTON"})
        except Exception as e:
            st.session_state.messages.append({"role": "assistant", "content": f"Could not prepare image for download: {e}"})
    else:
        st.session_state.messages.append({"role": "assistant", "content": "❌ Image generation failed. The final image could not be retrieved."})

def process_prompt(prompt):
    command = prompt.strip().lower()

    if command == "choose template":
        with st.spinner("Fetching templates..."):
            templates = list_templates(BB_API_KEY)
            if templates:
                st.session_state.messages.append({"role": "assistant", "content": {"type": "template_picker", "data": templates}})
            else:
                st.session_state.messages.append({"role": "assistant", "content": "Sorry, I couldn't fetch any templates."})
    elif command == "generate image":
        handle_image_generation()
    else:
        with st.spinner("Thinking..."):
            response = generate_gemini_response(
                model=st.session_state.gemini_model,
                chat_history=st.session_state.messages,
                user_prompt=prompt,
                selected_template=st.session_state.selected_template_details,
                modifications=st.session_state.current_modifications
            )
            if response and response.candidates:
                first_candidate = response.candidates[0]
                if first_candidate.content.parts and first_candidate.content.parts[0].function_call.name:
                    handle_gemini_function_call(first_candidate.content.parts[0].function_call)
                else:
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
            else:
                st.session_state.messages.append({"role": "assistant", "content": "Sorry, the AI is not responding."})

# --- Main App Flow & UI Rendering ---
def main():
    initialize_session_state()
    st.title("AI Design Assistant 🤖🎨")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            content = msg["content"]
            if isinstance(content, dict) and content.get("type") == "template_picker":
                st.write("Please choose a template from the options below:")
                templates = content["data"]
                num_columns = min(len(templates), 3)
                cols = st.columns(num_columns)
                for i, template in enumerate(templates):
                    with cols[i % num_columns]:
                        st.image(template['preview_url'], caption=template['name'], use_container_width=True)
                        st.button("Select", key=f"select_{template['uid']}", on_click=handle_template_selection, args=(template,))
            elif content == "DOWNLOAD_BUTTON" and st.session_state.download_image:
                st.download_button("Download Image", st.session_state.download_image["bytes"], st.session_state.download_image["name"], "image/png")
            else:
                st.markdown(content)

    if prompt := st.chat_input("Your message..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        process_prompt(prompt)
        st.rerun()

if __name__ == "__main__":
    main()