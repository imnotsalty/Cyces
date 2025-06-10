import streamlit as st
import google.generativeai as genai
import requests
from PIL import Image
import os
import json
from dotenv import load_dotenv

# --- Configuration ---
# Load environment variables from .env file
load_dotenv()

# Set page configuration
st.set_page_config(
    page_title="Image Remix Studio 2.0",
    page_icon="🎨",
    layout="wide"
)

# --- Core Logic Functions ---

def get_structured_prompt_from_gemini(image: Image.Image, api_key: str):
    """
    Sends an image to Gemini 1.5 Flash and gets a highly structured JSON prompt.
    """
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
    except Exception as e:
        st.error(f"Error configuring Gemini: {e}")
        return None

    # The new, highly detailed instruction for Gemini based on user's request
    system_prompt = """
    You are an expert image analyst and prompt creator for generative AI art.
    Analyze the provided image and generate a JSON object describing it in detail.
    The JSON object must have the following keys: "style_name", "subject_description", "background", "lighting", "composition", "mood", "color_palette", "visual_elements", and "negative_prompt".

    - "style_name": A short phrase for the artistic style (e.g., "Modern Fashion Photography", "Impressionistic Oil Painting", "Cyberpunk Concept Art").
    - "subject_description": A detailed paragraph describing the main subject(s), including their appearance, clothing, actions, and expression.
    - "background": A description of the background and setting.
    - "lighting": A description of the lighting (e.g., "Soft and diffused", "Dramatic cinematic lighting", "Golden hour sunlight").
    - "composition": A description of the composition (e.g., "Rule of Thirds", "Centered portrait", "Symmetrical").
    - "mood": A word or short phrase for the overall mood or feeling (e.g., "Elegant", "Mysterious", "Joyful").
    - "color_palette": A JSON array of strings listing the dominant colors.
    - "visual_elements": A JSON array of strings listing the key nouns in the image.
    - "negative_prompt": A comma-separated list of things to avoid (e.g., "blurry, low quality, bad anatomy, watermark, text").

    Return ONLY the raw JSON object, without any markdown formatting like ```json ... ```.
    """

    try:
        response = model.generate_content([system_prompt, image])
        # Clean up the response to ensure it's valid JSON
        json_text = response.text.strip().replace("```json", "").replace("```", "").strip()
        
        prompt_data = json.loads(json_text)
        
        # Validate that all required keys are present
        required_keys = ["style_name", "subject_description", "background", "lighting", "composition", "mood", "color_palette", "visual_elements", "negative_prompt"]
        if all(k in prompt_data for k in required_keys):
            return prompt_data
        else:
            st.error("Gemini returned JSON in an unexpected format. Missing required keys.")
            st.code(json_text)
            return None

    except json.JSONDecodeError:
        st.error("Failed to decode JSON from Gemini's response.")
        st.write("Gemini's raw response:")
        st.code(response.text)
        return None
    except Exception as e:
        st.error(f"An error occurred while calling the Gemini API: {e}")
        return None

def synthesize_prompt_for_deepai(structured_prompt: dict):
    """
    Combines the structured JSON data into a single, effective text prompt for DeepAI.
    """
    # Start with the core subject and background
    main_prompt = f"{structured_prompt['subject_description']}. "
    main_prompt += f"The setting is {structured_prompt['background']}. "
    
    # Add details about style, lighting, and mood
    main_prompt += f"The style is {structured_prompt['style_name']}, with {structured_prompt['lighting']}. "
    main_prompt += f"The overall mood is {structured_prompt['mood']}. "
    
    # Mention composition and key colors
    main_prompt += f"The composition follows the {structured_prompt['composition']}. "
    main_prompt += f"Key colors include {', '.join(structured_prompt['color_palette'])}."
    
    return main_prompt

def generate_image_with_deepai(structured_prompt: dict, api_key: str):
    """
    Generates an image using the DeepAI API from the synthesized prompt.
    """
    # Synthesize the detailed JSON into a single text prompt
    final_text_prompt = synthesize_prompt_for_deepai(structured_prompt)
    
    # Display the synthesized prompt for transparency
    with st.expander("🔬 View Synthesized Prompt for DeepAI"):
        st.write(final_text_prompt)

    try:
        response = requests.post(
            "https://api.deepai.org/api/text2img",
            data={
                'text': final_text_prompt,
                'style': structured_prompt.get('style_name'), # Use the specific style from Gemini
                'negative_prompt': structured_prompt.get('negative_prompt'),
                'grid_size': '1',
            },
            headers={'api-key': api_key}
        )
        response.raise_for_status()
        result = response.json()
        return result.get('output_url')
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while calling the DeepAI API: {e}")
        try:
            error_details = response.json()
            st.error(f"DeepAI API Error: {error_details.get('err', 'No details provided.')}")
        except (ValueError, AttributeError):
            pass
        return None

# --- Streamlit UI ---

st.title("🎨 Image Remix Studio 2.0")
st.markdown("Upload an image, and let **Gemini 1.5 Flash** analyze it to create a detailed prompt. Then, **DeepAI** will generate a new image from that analysis.")

# Sidebar for API keys
st.sidebar.header("🔑 API Configuration")
st.sidebar.info("Your API keys are loaded from the `.env` file.")
gemini_api_key = st.sidebar.text_input("Gemini API Key", value=os.getenv("GEMINI_API_KEY", ""), type="password")
deepai_api_key = st.sidebar.text_input("DeepAI API Key", value=os.getenv("DEEPAI_API_KEY", ""), type="password")

if not gemini_api_key or not deepai_api_key:
    st.warning("Please enter your API keys in the sidebar to start.")
    st.stop()

# Main app layout
uploaded_file = st.file_uploader("Choose an image to analyze and remix...", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Original Image")
        try:
            input_image = Image.open(uploaded_file)
            st.image(input_image, caption="Your uploaded image.", use_column_width=True)
        except Exception as e:
            st.error(f"Error opening image file: {e}")
            st.stop()

    with col2:
        st.subheader("Remixed Image")
        if st.button("✨ Remix My Image!"):
            with st.spinner("Step 1/2: Gemini is analyzing your image..."):
                structured_prompt_json = get_structured_prompt_from_gemini(input_image, gemini_api_key)

            if structured_prompt_json:
                st.success("✅ Gemini created a structured prompt!")
                with st.expander("🔍 View the full JSON from Gemini"):
                    st.json(structured_prompt_json)

                with st.spinner("Step 2/2: DeepAI is generating the new image..."):
                    generated_image_url = generate_image_with_deepai(structured_prompt_json, deepai_api_key)

                if generated_image_url:
                    st.success("✅ DeepAI generated the image!")
                    st.image(generated_image_url, caption="Your remixed image by DeepAI.", use_column_width=True)
                else:
                    st.error("❌ Failed to generate image with DeepAI.")
            else:
                st.error("❌ Failed to get a valid structured prompt from Gemini.")