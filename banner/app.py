import streamlit as st
import requests
import google.generativeai as genai
import time
import json
import base64 # Import the base64 library

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Banner Generator",
    page_icon="🤖",
    layout="wide"
)

# --- API Key and Model Configuration ---
try:
    BANNERBEAR_API_KEY = st.secrets["BANNERBEAR_API_KEY"]
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    FREEIMAGE_API_KEY = st.secrets["FREEIMAGE_API_KEY"] 
    genai.configure(api_key=GOOGLE_API_KEY)
    GEMINI_MODEL = genai.GenerativeModel('gemini-1.5-flash')
except (KeyError, FileNotFoundError):
    st.error("🚨 Error: API keys not found. Please check your .streamlit/secrets.toml file for BANNERBEAR_API_KEY, GOOGLE_API_KEY, and FREEIMAGE_API_KEY.")
    st.stop()


# --- Bannerbear API Helper Functions ---
@st.cache_data(ttl=3600)
def fetch_all_bannerbear_templates():
    st.info("Fetching templates from your Bannerbear project...")
    url = "https://api.bannerbear.com/v2/templates"
    headers = {"Authorization": f"Bearer {BANNERBEAR_API_KEY}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch Bannerbear templates: {e}")
        return None

def fetch_bannerbear_template_details(template_id):
    url = f"https://api.bannerbear.com/v2/templates/{template_id}"
    headers = {"Authorization": f"Bearer {BANNERBEAR_API_KEY}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch Bannerbear template details: {e}")
        return None

def generate_bannerbear_image(template_id, modifications):
    url = "https://api.bannerbear.com/v2/images"
    headers = {"Authorization": f"Bearer {BANNERBEAR_API_KEY}"}
    payload = {"template": template_id, "modifications": modifications}
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to generate Bannerbear image: {e}")
        return None

def poll_for_image_completion(image_uid):
    url = f"https://api.bannerbear.com/v2/images/{image_uid}"
    headers = {"Authorization": f"Bearer {BANNERBEAR_API_KEY}"}
    
    with st.spinner("⏳ Your banner is being crafted by digital artisans..."):
        for _ in range(20):
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                if data["status"] == "completed":
                    return data["image_url_png"]
                elif data["status"] == "failed":
                    st.error("Image generation failed on Bannerbear's side.")
                    return None
                time.sleep(2)
            except requests.exceptions.RequestException as e:
                st.error(f"Polling failed: {e}")
                return None
        st.warning("Image generation is taking longer than expected.")
        return None

# --- Gemini AI Helper Function ---
@st.cache_data(ttl=3600)
def analyze_template_with_gemini(_template_data_str):
    template_data = json.loads(_template_data_str)
    layers_data = template_data.get("available_modifications", [])
    
    # --- THIS IS THE FULL, CORRECTED PROMPT ---
    prompt = f"""
    You are an expert UI generator. Your task is to analyze the JSON data of a Bannerbear template's layers and identify the editable text and image fields.

    Produce a clean JSON object containing two lists: 'text_fields' and 'image_fields'.
    - For 'text_fields', each item should have a 'name' (the original layer name) and a 'label' (a user-friendly, title-cased version of the name).
    - For 'image_fields', do the same.
    - Only include layers of type 'text' or 'image'. Exclude all other types like 'rect'.
    - Your output MUST be a valid JSON object and nothing else.

    Here is the JSON data for the template layers:
    {json.dumps(layers_data, indent=2)}
    """

    with st.spinner("🧠 Gemini is analyzing the template..."):
        try:
            response = GEMINI_MODEL.generate_content(prompt)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_response)
        except (json.JSONDecodeError, Exception) as e:
            st.error(f"Failed to parse Gemini's response: {e}")
            st.code(response.text)
            return None

# --- Main Streamlit App ---
st.title("🤖 AI-Powered Banner Generator")
st.markdown("Choose a template from your Bannerbear project, and Gemini AI will create a form to customize it.")

for key in ['analysis_result', 'template_data', 'selected_template_id']:
    if key not in st.session_state:
        st.session_state[key] = None

with st.sidebar:
    st.header("1. Select a Template")
    all_templates = fetch_all_bannerbear_templates()
    if all_templates:
        template_options = {t['name']: t['uid'] for t in all_templates}
        selected_name = st.selectbox(
            label="Choose from your Bannerbear templates:",
            options=list(template_options.keys()),
            index=None,
            placeholder="Select a template..."
        )
        if selected_name:
            selected_id = template_options[selected_name]
            if selected_id != st.session_state.get('selected_template_id'):
                st.session_state.selected_template_id = selected_id
                st.session_state.template_data = fetch_bannerbear_template_details(selected_id)
                if st.session_state.template_data:
                    st.session_state.analysis_result = analyze_template_with_gemini(
                        json.dumps(st.session_state.template_data)
                    )
    else:
        st.warning("Could not find any templates. Please create one in your Bannerbear project.")

if st.session_state.get('analysis_result'):
    col1, col2 = st.columns([1, 1.5])
    with col1:
        st.header("2. Preview")
        if st.session_state.template_data:
            st.image(
                st.session_state.template_data["preview_url"],
                caption="Template Preview",
                use_container_width=True
            )

    with col2:
        st.header("3. Customize Your Banner")
        analysis = st.session_state.analysis_result
        modifications = []

        with st.form("customization_form"):
            if analysis.get("text_fields"):
                st.subheader("Text Content")
                for field in analysis["text_fields"]:
                    text_input = st.text_input(label=field["label"], key=f"text_{field['name']}")
                    if text_input:
                        modifications.append({"name": field["name"], "text": text_input})
            
            if analysis.get("image_fields"):
                st.subheader("Image Content")
                for field in analysis["image_fields"]:
                    uploaded_file = st.file_uploader(
                        label=field["label"], type=["png", "jpg", "jpeg", "webp"], key=f"image_{field['name']}"
                    )
                    if uploaded_file:
                        with st.spinner(f"Uploading {field['label']} securely..."):
                            try:
                                url = "https://freeimage.host/api/1/upload"
                                image_bytes = uploaded_file.getvalue()
                                b64_image = base64.b64encode(image_bytes).decode('utf-8')
                                payload = {
                                    "key": FREEIMAGE_API_KEY,
                                    "source": b64_image,
                                    "format": "json"
                                }
                                response = requests.post(url, data=payload)
                                response.raise_for_status()
                                result = response.json()
                                direct_image_url = result['image']['url']

                                modifications.append({"name": field["name"], "image_url": direct_image_url})
                                st.success(f"✅ {uploaded_file.name} is ready!")
                            
                            except requests.exceptions.RequestException as e:
                                st.error(f"Image upload failed: {e}")
                                if e.response:
                                    st.json(e.response.json())
                            except Exception as e:
                                st.error(f"An unexpected error occurred during upload: {e}")

            submitted = st.form_submit_button("✨ Generate Image", use_container_width=True, type="primary")

        if submitted:
            if not modifications:
                st.warning("You haven't made any changes! Please fill out at least one field.")
            else:
                st.info(f"Sending {len(modifications)} modification(s) to Bannerbear...")
                generation_response = generate_bannerbear_image(st.session_state.selected_template_id, modifications)
                
                if generation_response:
                    final_image_url = poll_for_image_completion(generation_response["uid"])
                    if final_image_url:
                        st.header("🎉 Your Banner is Ready!")
                        st.image(final_image_url, caption="Generated Banner", use_container_width=True)
                        st.success("Image generated successfully!")
                        st.markdown(f"**Image URL:** `{final_image_url}`")
else:
    st.info("👈 Select a template from the sidebar to begin.")