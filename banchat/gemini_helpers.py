# gemini_helpers.py
import google.generativeai as genai
import json

def get_gemini_model(api_key):
    """Initializes and returns the Gemini 1.5 Flash model with function calling."""
    genai.configure(api_key=api_key)
    update_function = genai.protos.FunctionDeclaration(
        name="update_modifications",
        description="Updates the text or image_url for a specific layer in the design. Use this whenever the user wants to change a part of the image content.",
        parameters=genai.protos.Schema(
            type=genai.protos.Type.OBJECT,
            properties={
                "layer_name": genai.protos.Schema(type=genai.protos.Type.STRING, description="The exact name of the layer to update, e.g., 'headline', 'main_image'."),
                "new_text": genai.protos.Schema(type=genai.protos.Type.STRING, description="The new text content for the layer. Use only for text layers."),
                "new_image_url": genai.protos.Schema(type=genai.protos.Type.STRING, description="The new URL for the image. Use only for image layers.")
            },
            required=["layer_name"]
        )
    )
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        tools=[update_function]
    )
    return model

def generate_gemini_response(model, chat_history, user_prompt, selected_template, modifications):
    """
    Generates a response from Gemini, providing context about the selected template
    and current modification data.
    """
    if selected_template:
        template_name = selected_template.get('name', 'Unknown')
        # This prompt is now much more directive
        context_prompt = f"""You are an expert design assistant for Bannerbear helping a user customize the '{template_name}' template.
        
        - Your goal is to help the user modify the template's content.
        - The user will ask to change text or images. When they do, you MUST use the `update_modifications` function.
        - **Crucially, you may ONLY use the layer names provided below. Do not invent or guess layer names.**
        - After a successful update, confirm it to the user.

        CONTEXT:
        - Selected Template: {template_name}
        - **Available Layers and their Current Data (This is the source of truth):** {json.dumps(modifications, indent=2)}
        """
    else:
        context_prompt = """You are a friendly design assistant. Your main job is to guide the user.
        - Start by telling the user they can type 'choose template' to see options.
        - You cannot edit anything until a template has been chosen.
        """

    conversation = [
        {'role': 'user', 'parts': [context_prompt]},
        {'role': 'model', 'parts': ["Understood. I am ready to assist based on the provided context."]}
    ]
    for msg in chat_history[-6:]:
        if msg['role'] == 'user':
            conversation.append({'role': 'user', 'parts': [msg['content']]})
        elif msg['role'] == 'assistant' and "![Generated Image]" not in msg['content']:
            conversation.append({'role': 'model', 'parts': [msg['content']]})

    conversation.append({'role': 'user', 'parts': [user_prompt]})

    try:
        response = model.generate_content(conversation)
        return response
    except Exception as e:
        print(f"Error generating Gemini response: {e}")
        return None