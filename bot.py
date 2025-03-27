import pyautogui
import openai
from openai import OpenAI
import base64
import time
import json
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import pytesseract
import re

# --- Configuration (if you want to load it from env) ---
# from dotenv import load_dotenv
# import os

# # --- Configuration ---
# load_dotenv()
# API_KEY = os.getenv("OPENAI_API_KEY")
# if not API_KEY:
#     raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY in environment or .env file.")


# --- Tesseract Configuration (Optional - If not in PATH) ---
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- Safety Features ---
pyautogui.PAUSE = 0.7
pyautogui.FAILSAFE = True

# --- OpenAI Client (Using OpenRouter) ---
# WARNING: Hardcoding API keys is a security risk!
OPENROUTER_API_KEY = "###" # Replace with your openrouter or local ai key
OPENAI_API_KEY = "###" # Replace with your openai key

try:
    # local or openrouter api
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

    # openai
    # client = OpenAI(
    #     api_key=OPENAI_API_KEY,
    # )
except Exception as e: print(f"Error initializing OpenAI client: {e}"); exit()

# --- Constants ---
VISION_MODEL_NAME = "google/gemma-3-12b-it:free" # Ensure available on OpenRouter or OpenAI
OCR_CONFIDENCE_THRESHOLD = 55
AI_CONFIDENCE_THRESHOLD = 0.55 # Slightly higher threshold for OCR-based decisions
REPEAT_PRESS_DELAY=0.01

# --- Helper Functions ---

def take_screenshot():
    # ... (same as before)
    try:
        screenshot = pyautogui.screenshot()
        # screenshot.save(f"debug_step_ocr_{time.time()}.png") # Optional debug save
        return screenshot
    except Exception as e: print(f"Error taking screenshot: {e}"); return None

def encode_image_to_base64(image):
    # ... (same as before)
    if not image: return None
    buffered = BytesIO(); image.save(buffered, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"

def parse_instruction(instruction):
    # 1. Check for Coordinates (same as before)
    coord_pattern = re.compile(r"(\b(?:click|rightClick|doubleClick|type)\b\s*(?:at|on)?\s*)?\((\d+)\s*,\s*(\d+)\)")
    match = coord_pattern.search(instruction)
    if match:
        # ... (coordinate handling same as before) ...
        action_hint_raw = match.group(1); x = int(match.group(2)); y = int(match.group(3))
        coords = [x, y]; action_hint = 'click'
        if action_hint_raw:
             action_hint_clean = action_hint_raw.strip().split()[0].lower()
             action_map = {"rightclick": "rightClick", "doubleclick": "doubleClick", "type": "type", "click": "click"}
             action_hint = action_map.get(action_hint_clean, 'click')
        print(f"  Parsed instruction: Action '{action_hint}' at {coords}")
        if action_hint == "type": return "defer_to_ai", None
        return action_hint, coords

    # 2. Check for HOTKEYS (NEW)
    # Pattern: Optional verb + optional "keys" + modifier(s) + key (e.g., "ctrl+t", "shift+alt+del")
    # Modifiers: ctrl, alt, shift, win, cmd (pyautogui accepts these)
    # Key: Mostly single letters/numbers, function keys (f1-f12), or special keys ('enter', 'tab', 'delete', etc.)
    hotkey_pattern = re.compile(
        r"^\s*(?:press|hit|do|perform)\s+(?:hotkey|shortcut|keys?)\s+" # Optional verb part
        r"(['\"]?([\w\s\+\-]+)['\"]?)"                            # The key combination itself (e.g., "ctrl+t", "alt + f4")
        r"\s*$", re.IGNORECASE
    )
    # Simpler pattern if no verb is used: "ctrl+t"
    simple_hotkey_pattern = re.compile(
         r"^\s*(['\"]?((?:ctrl|alt|shift|win|cmd)\s*[\+\-]\s*\w+)['\"]?)\s*$", # Requires at least one modifier + key
         re.IGNORECASE
    )

    hotkey_match = hotkey_pattern.match(instruction) or simple_hotkey_pattern.match(instruction)

    if hotkey_match:
        # Extract the key combination string (group 2 in both patterns)
        key_combo_str = hotkey_match.group(2).strip().lower()
        # Split keys by '+' or '-' allowing spaces around them
        keys = [k.strip() for k in re.split(r'\s*[\+\-]\s*', key_combo_str)]

        # Validate keys (basic check - pyautogui handles more validation)
        valid_keys = pyautogui.KEYBOARD_KEYS + ['ctrl', 'alt', 'shift', 'win', 'cmd', 'command', 'option'] # Add common modifier names
        validated_keys = []
        valid = True
        for key in keys:
            # Map common names/aliases if needed
            if key in ['control', 'ctl']: key = 'ctrl'
            elif key in ['windows', 'super']: key = 'win'
            elif key in ['command', 'apple']: key = 'cmd' # Mac
            elif key == 'option': key = 'alt' # Mac

            if key in valid_keys:
                 validated_keys.append(key)
            else:
                 print(f"  Warning: Parsed hotkey '{key_combo_str}', but key '{key}' is potentially invalid.")
                 valid = False
                 break # Stop processing if one key is bad

        if valid and len(validated_keys) >= 2: # Need at least modifier + key
            key_string_for_execution = "+".join(validated_keys) # Create a standardized string maybe? Or just use the list.
            print(f"  Parsed instruction: Found HOTKEY {validated_keys}")
            return "hotkey", validated_keys # Return list of keys
        else:
            print(f"  Warning: Parsed hotkey '{key_combo_str}' seems invalid or incomplete.")
            return "defer_to_ai", None

    # 3. Check for REPEATED KEY PRESS (NEW) - Check BEFORE simple press
    # Pattern: press [key] x [number] times?
    repeat_press_pattern = re.compile(
        r"^\s*press\s+(?:the\s+)?(['\"]?([\w\s]+)['\"]?)\s+x\s*(\d+)(?:\s+times?)?\s*$",
        re.IGNORECASE
    )
    repeat_match = repeat_press_pattern.match(instruction)
    if repeat_match:
        key_name = repeat_match.group(2).strip().lower()
        count = int(repeat_match.group(3))

        if count <= 0:
             print(f"  Warning: Parsed 'press {key_name} x{count}' - count must be positive. Deferring.")
             return "defer_to_ai", None

        # Validate the key name
        validated_key = key_name
        if key_name not in pyautogui.KEYBOARD_KEYS:
             alias_map = {"return": "enter", "escape": "esc"}
             validated_key = alias_map.get(key_name, key_name)

        if validated_key in pyautogui.KEYBOARD_KEYS:
             print(f"  Parsed instruction: Found REPEAT PRESS '{validated_key}' {count} times.")
             return "press_repeat", {"key": validated_key, "count": count} # Return dict with key and count
        else:
             print(f"  Warning: Parsed 'press {key_name} x{count}' but key '{key_name}' (validated: '{validated_key}') is not valid. Deferring.")
             return "defer_to_ai", None

    # 4. Check simple press/type/wait (improved robustness from previous step)
    press_match = re.match(r"^\s*press\s+(?:the\s+)?(['\"]?([\w\s]+)['\"]?)(\s+key)?\s*$", instruction, re.IGNORECASE)
    if press_match:
        # ... (press handling same as before, use defer_to_ai if key invalid) ...
        key_name = press_match.group(2).strip().lower()
        validated_key = key_name
        if key_name not in pyautogui.KEYBOARD_KEYS:
             alias_map = {"return": "enter", "escape": "esc"}
             validated_key = alias_map.get(key_name, key_name)
        if validated_key in pyautogui.KEYBOARD_KEYS:
             print(f"  Parsed instruction: Found direct 'press {validated_key}'.")
             return "press", validated_key
        else:
             print(f"  Warning: Parsed 'press {key_name}' but key is not valid.")
             return "defer_to_ai", None

    type_match = re.match(r"^\s*type\s+['\"](.+)['\"]\s*$", instruction, re.IGNORECASE)
    if type_match:
        print(f"  Parsed instruction: Found direct 'type'.")
        return "type", type_match.group(1)
    wait_match = re.match(r"^\s*wait\s+(\d+(?:\.\d+)?)\s*seconds?\s*$", instruction, re.IGNORECASE)
    if wait_match:
        print(f"  Parsed instruction: Found direct 'wait'.")
        return "wait", float(wait_match.group(1))

    # 4. If nothing else matches, defer to AI
    print("  Instruction not directly parsed, will use AI.")
    return None, None


# COPIED/ADAPTED: Get elements via OCR (runs on full image)
def get_elements_from_ocr(full_image):
    """Uses Tesseract OCR on the full image. Returns list and map."""
    elements = []; element_id_counter = 1
    try:
        ocr_data = pytesseract.image_to_data(full_image, output_type=pytesseract.Output.DICT, config='--oem 3 --psm 6')
        n_boxes = len(ocr_data['level'])
        for i in range(n_boxes):
            confidence = int(ocr_data['conf'][i])
            text = ocr_data['text'][i].strip()
            if confidence > OCR_CONFIDENCE_THRESHOLD and text:
                (x, y, w, h) = (ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i])
                center_x, center_y = x + w // 2, y + h // 2
                cleaned_text = re.sub(r'[^\x00-\x7F]+', '', text)
                if not cleaned_text: continue
                elements.append({ "id": f"elem_{element_id_counter}", "text": cleaned_text, "center_coords": [center_x, center_y], "bbox": [x, y, x+w, y+h] })
                element_id_counter += 1
        print(f"  OCR found {len(elements)} elements.")
        elements_map = {elem['id']: elem for elem in elements}
        return elements, elements_map
    except pytesseract.TesseractNotFoundError: print("\n--- Tesseract Error ---\n"); return None, None
    except Exception as e: print(f"Error during OCR: {e}"); return [], {}


def ask_vision_ai_step_ocr(base64_image, current_instruction, ocr_elements):
    if not base64_image: return None
    element_texts = [f"- {elem['id']}: '{elem['text']}' (bbox: {elem['bbox']})" for elem in ocr_elements]
    element_prompt_part = "OCR elements:\n" + "\n".join(element_texts) if ocr_elements else "No OCR elements."

    prompt_text = f"""
You are a GUI automation assistant executing ONE instruction: "{current_instruction}".
Analyze the screenshot and OCR list. Decide BEST action (PRIORITY: OCR Element > Direct Action).

Respond ONLY with JSON. Choose ONE format:

Format 1: Use OCR Element
{{ "decision_type": "use_ocr_element", "element_id": "<elem_id>", "action": "<'click'/'doubleClick'/'rightClick'>", "reasoning": "...", "confidence": <float> }}

Format 2: Perform Direct Action
{{ "decision_type": "perform_direct_action", "action": "<action_type>", "coordinates": [<x>, <y>]|null, "text": "<string>"|null, "scroll_amount": <int>|null, "wait_seconds": <float>|null, "reasoning": "...", "confidence": <float> }}
   - Action Types: 'click', 'doubleClick', 'rightClick', 'type', 'press' (single key), 'hotkey' (combo like ctrl+t), 'scroll', 'wait', 'error'
   - 'text' field used for: text to type (action 'type'), single key name (action 'press'), OR key combo string like "ctrl+t" (action 'hotkey').

RULES:
- Prioritize `use_ocr_element` if target matches OCR.
- **IMPORTANT**: If action is 'press', key name MUST be in `text` field.
- **IMPORTANT**: If action is 'type', string MUST be in `text` field.
- **IMPORTANT**: If instruction is a shortcut like 'Press Ctrl+T', use action 'hotkey' and put "ctrl+t" (or similar representation) in the `text` field.
- if action is wait, provide duration in seconds, default is 5 seconds.
- If target not found / unclear, use Format 2, action "error".

{element_prompt_part}
Instruction: "{current_instruction}"
Provide the JSON:
"""
    prompt_content = [ {"type": "text", "text": prompt_text}, {"type": "image_url", "image_url": {"url": base64_image, "detail": "high"}} ]

    try:
        print(f"  Asking AI ({VISION_MODEL_NAME}) with OCR context...")
        response = client.chat.completions.create( model=VISION_MODEL_NAME, messages=[{"role": "user", "content": prompt_content}], max_tokens=400, temperature=0.0 )
        response_text = response.choices[0].message.content
        try:
            # ... (JSON parsing same) ...
            json_start_index = response_text.find('{'); json_end_index = response_text.rfind('}') + 1
            if json_start_index != -1 and json_end_index != -1:
                json_string = response_text[json_start_index:json_end_index]
                ai_decision = json.loads(json_string)
                print(f"  AI Parsed Decision: {ai_decision}")

                # --- UPDATED VALIDATION ---
                dtype = ai_decision.get("decision_type")
                action = ai_decision.get("action")
                text = ai_decision.get("text") # Check text for relevant actions

                if dtype == "perform_direct_action":
                    if action == "press" and not text:
                        raise ValueError("AI Error: 'press' action requested without 'text' (key name).")
                    if action == "type" and text is None:
                        raise ValueError("AI Error: 'type' action requested without 'text'.")
                    if action == "hotkey" and not text: # NEW validation
                        raise ValueError("AI Error: 'hotkey' action requested without 'text' (key combo string).")
                    # Add more validation as needed (e.g., coords for direct clicks)

                elif dtype == "use_ocr_element":
                     if not ai_decision.get("element_id") or not action:
                         raise ValueError("AI Error: 'use_ocr_element' missing element_id or action.")
                elif not dtype: raise ValueError("AI Error: Missing 'decision_type'.")

                return ai_decision
            else: return {"decision_type": "perform_direct_action", "action": "error", "reasoning": "AI response no JSON", "confidence": 0.0}
        except (json.JSONDecodeError, ValueError) as e:
             print(f"  Error validating/decoding AI step decision: {e}")
             return {"decision_type": "perform_direct_action", "action": "error", "reasoning": f"AI JSON invalid/validation failed: {response_text}", "confidence": 0.0}
    except openai.APIError as e: print(f" OpenAI/OpenRouter API Error: {e}")
    except Exception as e: print(f" Unexpected error calling API: {e}")
    return {"decision_type": "perform_direct_action", "action": "error", "reasoning": "Failed API call", "confidence": 0.0}


def execute_step_action_hybrid(step_decision, elements_map):
    # ... (Get decision_type, confidence, reasoning, action as before) ...
    decision_type = step_decision.get("decision_type")
    confidence = step_decision.get("confidence", 0.0)
    reasoning = step_decision.get("reasoning", "N/A")
    action = step_decision.get("action")

    print(f"  Executing Decision: {decision_type}", end='')
    if action: print(f" - Action: {action}", end='')
    if confidence: print(f" (AI Confidence: {confidence*100:.1f}%)", end='')
    print(f" Reason: {reasoning}")

    is_ai_decision = not step_decision.get("_parsed_directly", False)
    if is_ai_decision and confidence < AI_CONFIDENCE_THRESHOLD:
        print(f"  Skipping execution due to low AI confidence.")
        return False

    try:
        if decision_type == "use_ocr_element":
            # ... (same as before) ...
            element_id = step_decision.get("element_id"); element_action = step_decision.get("action")
            valid_element_actions = ["click", "doubleClick", "rightClick"]
            if element_id in elements_map and element_action in valid_element_actions:
                target_element = elements_map[element_id]; target_coords = target_element["center_coords"]
                print(f"    Targeting OCR '{target_element['text']}' ({element_id}) at {target_coords}")
                action_func = getattr(pyautogui, element_action); action_func(x=target_coords[0], y=target_coords[1])
            else: raise ValueError(f"Invalid OCR element ID/action: {element_id}/{element_action}")

        elif decision_type == "perform_direct_action":
            direct_action = step_decision.get("action")
            coords = step_decision.get("coordinates")
            text = step_decision.get("text")
            scroll_amount = step_decision.get("scroll_amount")
            wait_seconds = step_decision.get("wait_seconds")

            # --- ADDED HOTKEY CASE ---
            if direct_action == "hotkey":
                if not text: raise ValueError("Hotkey action needs key combo string in 'text'")
                # Parse the text string into arguments for pyautogui.hotkey()
                keys_to_press = [k.strip() for k in re.split(r'\s*[\+\-]\s*', text.lower())]
                # Basic validation - ensure all keys seem valid before passing
                valid_pyautogui_keys = pyautogui.KEYBOARD_KEYS + ['ctrl', 'alt', 'shift', 'win', 'cmd', 'command', 'option']
                validated_for_hotkey = []
                all_valid = True
                for k in keys_to_press:
                    # Remap common names
                    if k in ['control', 'ctl']: k = 'ctrl'
                    elif k in ['windows', 'super']: k = 'win'
                    elif k in ['command', 'apple']: k = 'cmd'
                    elif k == 'option': k = 'alt'

                    if k in valid_pyautogui_keys:
                         validated_for_hotkey.append(k)
                    else:
                         print(f"    Warning: Invalid key '{k}' found in hotkey string '{text}'")
                         all_valid = False
                         break
                if all_valid and len(validated_for_hotkey) >= 2:
                    print(f"    Performing hotkey: {validated_for_hotkey}")
                    pyautogui.hotkey(*validated_for_hotkey)
                elif not all_valid:
                    raise ValueError(f"Invalid key found in hotkey combo '{text}'")
                else:
                    raise ValueError(f"Hotkey combo '{text}' needs at least two keys (modifier + key)")

            elif direct_action == "press":
                 # ... (press logic same as before, validation moved earlier) ...
                 if not text: raise ValueError("Direct press needs key name ('text' field missing)")
                 key_name = text.lower();
                 if key_name in pyautogui.KEYBOARD_KEYS: pyautogui.press(key_name)
                 else: raise ValueError(f"Invalid key '{key_name}' for press")
            # ... (other direct actions: click, type, scroll, wait, error) ...
            elif direct_action == "click":
                 if not coords: raise ValueError("Direct click needs coordinates");
                 pyautogui.click(x=coords[0], y=coords[1])
            # ... handle doubleClick, rightClick, type, scroll, wait, error ...
            elif direct_action == "doubleClick":
                if not coords: raise ValueError("Direct doubleClick needs coordinates");
                pyautogui.doubleClick(x=coords[0], y=coords[1])
            elif direct_action == "rightClick":
                if not coords: raise ValueError("Direct rightClick needs coordinates");
                pyautogui.rightClick(x=coords[0], y=coords[1])
            elif direct_action == "type":
                if text is None: raise ValueError("Direct type needs text");
                if coords: pyautogui.click(x=coords[0], y=coords[1]); time.sleep(0.3)
                pyautogui.typewrite(text, interval=0.05)
            elif direct_action == "scroll":
                if scroll_amount is None: raise ValueError("Direct scroll needs amount");
                pyautogui.scroll(scroll_amount)
            elif direct_action == "wait":
                if not wait_seconds or wait_seconds <=0: raise ValueError("Invalid wait duration");
                time.sleep(wait_seconds)
            elif direct_action == "error":
                print(f"    AI reported error for this step: {reasoning}"); return False
            else: raise ValueError(f"Unknown direct action '{direct_action}'")

        else: # Handle directly parsed actions
            parsed_action = step_decision.get("action")
            parsed_value = step_decision.get("value")
            coords = step_decision.get("coordinates")

            print(f"    Executing parsed action: {parsed_action}")
            if parsed_action == "hotkey": # Added parsed hotkey
                 if not parsed_value or not isinstance(parsed_value, list) or len(parsed_value) < 2:
                     raise ValueError("Parsed hotkey missing valid key list")
                 print(f"    Performing parsed hotkey: {parsed_value}")
                 pyautogui.hotkey(*parsed_value) # Pass list elements as arguments
            elif parsed_action == "press":
                 # ... (same as before) ...
                 if not parsed_value: raise ValueError("Parsed press missing key name")
                 key_name = parsed_value.lower();
                 if key_name in pyautogui.KEYBOARD_KEYS: pyautogui.press(key_name)
                 else: raise ValueError(f"Invalid parsed key '{key_name}'")
            elif parsed_action == "type":
                 if parsed_value is None : raise ValueError("Parsed type missing text");
                 pyautogui.typewrite(parsed_value, interval=0.05)
            elif parsed_action == "wait":
                 if not parsed_value or parsed_value <=0: raise ValueError("Invalid parsed wait duration");
                 time.sleep(parsed_value)
            elif parsed_action in ["click", "rightClick", "doubleClick"]:
                 if not coords: raise ValueError(f"Missing coordinates for parsed {parsed_action}");
                 action_func = getattr(pyautogui, parsed_action); action_func(x=coords[0], y=coords[1])
            elif parsed_action == "press_repeat":
                if not isinstance(parsed_value, dict) or "key" not in parsed_value or "count" not in parsed_value:
                    raise ValueError("Parsed 'press_repeat' missing valid key/count dictionary")
                key_name = parsed_value["key"]
                count = parsed_value["count"]
                if count <= 0: raise ValueError("Parsed 'press_repeat' count must be positive")
                print(f"      Pressing key: '{key_name}' {count} times (with {REPEAT_PRESS_DELAY}s delay)")
                for i in range(count):
                    pyautogui.press(key_name)
                    print(f"        Press {i+1}/{count}") # Optional feedback
                    # Add a small delay between presses, crucial for UIs
                    time.sleep(REPEAT_PRESS_DELAY)
            else: raise ValueError(f"Unhandled parsed action type: {parsed_action}")

        time.sleep(0.5)
        return True

    except Exception as e:
        print(f"\n    Execution failed for step: {e}")
        # Add more detail if possible
        print(f"    Failed Decision Details: {json.dumps(step_decision)}")
        return False


# --- Main Workflow Loop ---
def main():
    # ... (Input instructions same as before) ...
    print("Enter steps (prefix with number, optional coords like '(x, y)' or 'Click at (x,y)')... finish with 'done':")

    instructions = []
    while True:
        line = input()
        if line.strip().lower() == 'done':
            break
        if line.strip(): # Ignore empty lines
            instructions.append(line.strip())

    if not instructions:
        print("No instructions provided. Exiting.")
        return

    print("\n--- Starting Workflow ---")
    print("Instructions:")
    for i, instruction in enumerate(instructions):
        print(f"  {i+1}. {instruction}")
    print("-------------------------")
    print("IMPORTANT: Stop manually? Move mouse to top-left corner (0,0).")
    time.sleep(4)

    # Loop through each instruction
    for i, instruction in enumerate(instructions):
        print(f"\n--- Executing Step {i+1}/{len(instructions)} ---")
        print(f"Instruction: {instruction}")

        success = False
        step_params = {} # Store parameters for execution

        # 1. Try parsing instruction directly
        parsed_action, parsed_value = parse_instruction(instruction)

        if parsed_action == "defer_to_ai":
            print("  Instruction needs AI interpretation (e.g., Type at (x,y)).")
            parsed_action = None # Force AI path

        if parsed_action:
             step_params["_parsed_directly"] = True # Mark as non-AI
             step_params["action"] = parsed_action
             if parsed_action in ["click", "rightClick", "doubleClick"]:
                 step_params["coordinates"] = parsed_value
             else: # press, type, wait
                 step_params["value"] = parsed_value # Store key/text/duration here

             print(f"  Executing directly based on parsed instruction: {parsed_action}")
             success = execute_step_action_hybrid(step_params, {}) # No elements_map needed

        # 2. If not executed directly, use AI + OCR
        if not parsed_action:
            screenshot = take_screenshot()
            if not screenshot: print(" Failed screenshot. Stopping."); break

            # Run OCR screen-wide
            ocr_elements, elements_map = get_elements_from_ocr(screenshot)
            if ocr_elements is None: print(" Tesseract error. Stopping."); break # Check for critical error

            base64_img = encode_image_to_base64(screenshot)
            if not base64_img: print(" Failed encoding. Stopping."); break

            # Ask AI to interpret step using OCR context
            ai_decision = ask_vision_ai_step_ocr(base64_img, instruction, ocr_elements)

            if ai_decision:
                step_params = ai_decision # Use AI decision as parameters
                success = execute_step_action_hybrid(step_params, elements_map)
            else:
                print("  Failed to get valid decision from AI. Stopping.")
                break

        # 3. Check step outcome
        if not success:
            print(f"\n--- Step {i+1} failed. Stopping workflow. ---")
            break
        else:
             time.sleep(0.5) # Short delay after success

    # End of loop
    if success: print("\n--- Workflow finished successfully! ---")
    else: print("\n--- Workflow stopped due to failure or interruption. ---")


if __name__ == "__main__":
    main()
