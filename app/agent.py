# ruff: noqa
# Copyright 2026 Google LLC

import base64
import datetime
import json
import os
import requests
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from google.cloud import firestore, storage
from google.cloud.firestore_v1.base_query import FieldFilter

from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors.agent_engine_sandbox_code_executor import (
    AgentEngineSandboxCodeExecutor,
)
from google.adk.memory.vertex_ai_memory_bank_service import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from app.a2ui_utils import a2ui_callback

# Load local environment variables from .env
load_dotenv()

# Hardcoded project ID & bucket as required to prevent Agent Platform project-number resolution errors
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-7a8c674b8d70"
GCS_BUCKET_NAME = "fitcoach-ai-media-qwiklabs-gcp-03-7a8c674b8d70"
MEMORY_BANK_ID = "2293869327587213312"

# Load Agent Engine resource name from deployment_metadata.json
AGENT_ENGINE_RESOURCE_NAME = f"projects/216397559854/locations/us-east1/reasoningEngines/{MEMORY_BANK_ID}"
SANDBOX_RESOURCE_NAME = None

deployment_metadata_path = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "deployment_metadata.json"
)
if os.path.exists(deployment_metadata_path):
    try:
        with open(deployment_metadata_path, "r") as f:
            metadata = json.load(f)
            AGENT_ENGINE_RESOURCE_NAME = metadata.get("remote_agent_runtime_id") or AGENT_ENGINE_RESOURCE_NAME
            SANDBOX_RESOURCE_NAME = metadata.get("sandbox_resource_name")
            if AGENT_ENGINE_RESOURCE_NAME:
                MEMORY_BANK_ID = AGENT_ENGINE_RESOURCE_NAME.split("/")[-1]
    except Exception:
        pass

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=AGENT_ENGINE_RESOURCE_NAME,
    sandbox_resource_name=SANDBOX_RESOURCE_NAME,
)

# Build system prompt with A2UI version 0.8 and Basic Catalog
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are FitCoach AI, a personal fitness and workout coaching assistant. "
        "You remember all user fitness goals (e.g. target weights, strength PR goals, weight loss/gain targets, "
        "target muscle focus areas, dietary preferences, and workout schedules) across sessions using Memory Bank, "
        "and personalize all advice and recommendations accordingly. "
        "Whenever a user states a fitness goal or preference, acknowledge it clearly so it is stored in Memory Bank. "
        "You help users look up exercises from their library catalog, log workout sets, "
        "review training history, generate customized workout routines, calculate 1-Rep Max (1RM) metrics, "
        "look up food nutrition facts via Open Food Facts, geocode addresses to coordinates, "
        "find nearby gyms and fitness places using Google Maps & Places API, "
        "generate visual fitness item images using gemini-3.1-flash-lite-image, "
        "generate short exercise videos using gemini-omni-flash-preview, "
        "execute Python code safely using AgentEngineSandboxCodeExecutor, "
        "and generate milestone achievement badges."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback triggered after each agent turn to send durable facts and preferences to Memory Bank."""
    await callback_context.add_session_to_memory()
    return None


def memory_bank_service_builder():
    """Builds VertexAiMemoryBankService for Memory Bank persistence when deployed."""
    return VertexAiMemoryBankService(
        project=FIRESTORE_PROJECT_ID,
        location="us-east1",
        agent_engine_id=MEMORY_BANK_ID,
    )


def _get_firestore_client():
    return firestore.Client(project=FIRESTORE_PROJECT_ID)


def list_exercises(category: str = "") -> str:
    """Lists available exercises from the exercise library, optionally filtered by muscle group/category.

    Args:
        category: Optional category or muscle group to filter by (e.g., 'Chest', 'Legs', 'Back', 'Shoulders').

    Returns:
        A list of exercises with details formatted as text.
    """
    db = _get_firestore_client()
    docs = db.collection("exercises").stream()

    results = []
    for doc in docs:
        data = doc.to_dict()
        if category:
            doc_category = data.get("category", "").lower()
            if category.lower() not in doc_category:
                continue
        results.append(data)

    if not results:
        return f"No exercises found for category '{category}'." if category else "No exercises found in library."

    output = ["### Exercise Library Catalog:"]
    for ex in results:
        output.append(
            f"- **{ex.get('name')}** (ID: {ex.get('exercise_id')}) | Category: {ex.get('category')}\n"
            f"  Target Muscles: {', '.join(ex.get('target_muscles', []))}\n"
            f"  Equipment: {ex.get('equipment')} | Difficulty: {ex.get('difficulty')}\n"
            f"  Instructions: {ex.get('instructions')}\n"
        )

    return "\n".join(output)


def log_workout(exercise_name: str, sets: int, reps: int, weight_lbs: float, notes: str = "", user_id: str = "default_user") -> str:
    """Logs a completed workout set/session into the user's workout history log.

    Args:
        exercise_name: Name of the exercise performed (e.g. 'Barbell Bench Press').
        sets: Number of sets completed.
        reps: Number of repetitions per set.
        weight_lbs: Weight lifted in pounds (lbs).
        notes: Optional notes on performance, form, or effort.
        user_id: User identifier (defaults to 'default_user').

    Returns:
        Confirmation string indicating the workout log was saved to Firestore.
    """
    db = _get_firestore_client()
    today_str = datetime.date.today().isoformat()
    doc_id = f"{user_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

    log_data = {
        "log_id": doc_id,
        "user_id": user_id,
        "exercise_name": exercise_name,
        "sets": sets,
        "reps": reps,
        "weight_lbs": weight_lbs,
        "date": today_str,
        "notes": notes,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    db.collection("workout_logs").document(doc_id).set(log_data)
    return f"Successfully logged workout: {sets} sets x {reps} reps of {exercise_name} at {weight_lbs} lbs on {today_str}."


def get_workout_history(user_id: str = "default_user") -> str:
    """Retrieves the workout history log for a user from Firestore.

    Args:
        user_id: User identifier to fetch logs for (defaults to 'default_user').

    Returns:
        A formatted summary of past workout logs.
    """
    db = _get_firestore_client()
    docs = db.collection("workout_logs").where(filter=FieldFilter("user_id", "==", user_id)).stream()

    logs = [doc.to_dict() for doc in docs]
    if not logs:
        return f"No workout history found for user '{user_id}'."

    output = [f"### Workout History for {user_id}:"]
    for entry in logs:
        notes_str = f" | Notes: {entry['notes']}" if entry.get("notes") else ""
        output.append(
            f"- **{entry.get('date')}** | {entry.get('exercise_name')}: {entry.get('sets')} sets x {entry.get('reps')} reps @ {entry.get('weight_lbs')} lbs{notes_str}"
        )

    return "\n".join(output)


def calculate_one_rep_max(weight_lbs: float, reps: int) -> str:
    """Calculates estimated 1-Rep Max (1RM) using Epley and Brzycki exercise science formulas,
    and provides target weight recommendations for strength, hypertrophy, and endurance training zones.

    Args:
        weight_lbs: Weight lifted in pounds (lbs).
        reps: Repetitions completed in the set.

    Returns:
        A formatted summary showing estimated 1RM and target training weight percentages.
    """
    if reps <= 0 or weight_lbs <= 0:
        return "Weight and reps must both be positive numbers."

    if reps == 1:
        epley_1rm = weight_lbs
        brzycki_1rm = weight_lbs
    else:
        epley_1rm = weight_lbs * (1 + reps / 30.0)
        brzycki_1rm = weight_lbs * (36.0 / max(1, 37 - reps))

    avg_1rm = (epley_1rm + brzycki_1rm) / 2.0

    return (
        f"### Estimated 1-Rep Max (1RM) Breakdown for {weight_lbs} lbs x {reps} reps:\n"
        f"- **Epley Formula 1RM**: {round(epley_1rm, 1)} lbs\n"
        f"- **Brzycki Formula 1RM**: {round(brzycki_1rm, 1)} lbs\n"
        f"- **Estimated Average 1RM**: **{round(avg_1rm, 1)} lbs**\n\n"
        f"**Target Training Weight Zones:**\n"
        f"- **Heavy Strength (90% 1RM)**: {round(avg_1rm * 0.90, 1)} lbs (~3-5 reps)\n"
        f"- **Hypertrophy / Muscle Building (80% 1RM)**: {round(avg_1rm * 0.80, 1)} lbs (~8-10 reps)\n"
        f"- **Muscular Endurance (70% 1RM)**: {round(avg_1rm * 0.70, 1)} lbs (~12-15 reps)"
    )


def generate_workout_routine(fitness_goal: str, target_muscle: str = "") -> str:
    """Generates a custom workout routine by selecting exercises from the exercise library catalog in Firestore.

    Args:
        fitness_goal: Goal of the workout (e.g. 'Strength', 'Hypertrophy', 'Endurance').
        target_muscle: Optional target muscle group (e.g. 'Chest', 'Legs', 'Back', 'Shoulders').

    Returns:
        A formatted custom workout routine with sets and reps.
    """
    db = _get_firestore_client()
    docs = db.collection("exercises").stream()

    matched = []
    for doc in docs:
        data = doc.to_dict()
        if target_muscle and target_muscle.lower() not in data.get("category", "").lower():
            continue
        matched.append(data)

    if not matched:
        return f"No exercises found in library matching target muscle '{target_muscle}'."

    sets_reps = "4 sets x 5 reps" if "strength" in fitness_goal.lower() else "3 sets x 10 reps"
    routine = [f"### Customized {fitness_goal} Routine ({target_muscle or 'Full Body'} Focus):"]
    for idx, ex in enumerate(matched, 1):
        routine.append(f"{idx}. **{ex.get('name')}**: {sets_reps} | Focus: {', '.join(ex.get('target_muscles', []))}")

    return "\n".join(routine)


def generate_milestone_badge(achievement_name: str) -> str:
    """Generates a visual milestone achievement badge icon for a fitness accomplishment and saves it to Cloud Storage.

    Args:
        achievement_name: Description of the accomplishment (e.g. '225 lb Bench Club', '50 Workouts Completed').

    Returns:
        Public image URL of the generated achievement badge.
    """
    try:
        svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e1b4b"/>
      <stop offset="100%" stop-color="#312e81"/>
    </linearGradient>
    <linearGradient id="goldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#fbbf24"/>
      <stop offset="50%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#b45309"/>
    </linearGradient>
  </defs>
  <rect width="400" height="400" rx="30" fill="url(#bgGrad)"/>
  <circle cx="200" cy="180" r="120" fill="none" stroke="url(#goldGrad)" stroke-width="12"/>
  <polygon points="200,80 230,140 295,150 250,195 260,260 200,230 140,260 150,195 105,150 170,140" fill="url(#goldGrad)"/>
  <text x="200" y="340" font-family="Arial, sans-serif" font-size="20" font-weight="bold" fill="#f8fafc" text-anchor="middle">{achievement_name}</text>
  <text x="200" y="370" font-family="Arial, sans-serif" font-size="12" fill="#94a3b8" text-anchor="middle">FITCOACH AI MILESTONE</text>
</svg>'''

        file_name = f"badge_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.svg"

        gcs_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = gcs_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(file_name)
        blob.upload_from_string(svg_content, content_type="image/svg+xml")

        public_url = f"https://storage.googleapis.com/fitcoach-ai-media-qwiklabs-gcp-03-7a8c674b8d70/{file_name}"
        return f"Milestone badge created for '{achievement_name}'! View badge: {public_url}"
    except Exception as e:
        return f"Error generating badge: {e}"


def search_food_nutrition(query: str) -> str:
    """Searches the Open Food Facts public database for real nutritional facts (calories, protein, carbs, fat per 100g) on foods and supplements.

    Args:
        query: Name of food, drink, or supplement to search (e.g. 'whey protein', 'banana', 'chicken breast', 'greek yogurt').

    Returns:
        A formatted summary of calories and macronutrients per 100g.
    """
    user_agent = os.environ.get("OPENFOODFACTS_USER_AGENT", "FitCoachAI/1.0 (contact@fitcoach.ai)")
    headers = {"User-Agent": user_agent}
    api_key = os.environ.get("NUTRITION_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key

    url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={query}&search_simple=1&action=process&json=1&page_size=3"

    try:
        response = requests.get(url, headers=headers, timeout=6)
        if response.status_code != 200:
            return f"Unable to fetch nutrition data (HTTP {response.status_code})."

        data = response.json()
        products = data.get("products", [])
        if not products:
            return f"No nutritional data found for '{query}'."

        results = [f"### Open Food Facts Nutrition Data for '{query}':"]
        for p in products[:3]:
            name = p.get("product_name") or p.get("product_name_en") or "Unknown Product"
            n = p.get("nutriments", {})
            kcal = n.get("energy-kcal_100g", "N/A")
            protein = n.get("proteins_100g", "N/A")
            carbs = n.get("carbohydrates_100g", "N/A")
            fat = n.get("fat_100g", "N/A")
            results.append(f"- **{name}** (per 100g):\n  Calories: {kcal} kcal | Protein: {protein}g | Carbs: {carbs}g | Fat: {fat}g")

        return "\n".join(results)
    except Exception as e:
        return f"Error connecting to Open Food Facts API: {e}"


def geocode_address(address: str) -> str:
    """Converts a street address or location name into geographical coordinates (latitude and longitude) using the Google Geocoding API.

    Args:
        address: Street address or location (e.g. '1600 Amphitheatre Pkwy, Mountain View, CA').

    Returns:
        A formatted summary with the formatted address and latitude/longitude coordinates.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "GOOGLE_MAPS_API_KEY is not configured in the environment."

    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}"

    try:
        response = requests.get(url, timeout=6)
        data = response.json()

        if data.get("status") == "OK" and data.get("results"):
            first_result = data["results"][0]
            formatted_address = first_result.get("formatted_address", address)
            location = first_result.get("geometry", {}).get("location", {})
            lat = location.get("lat")
            lng = location.get("lng")
            return (
                f"### Geocoding Results for '{address}':\n"
                f"- **Address**: {formatted_address}\n"
                f"- **Location**: Latitude {lat}, Longitude {lng}"
            )
        else:
            status = data.get("status")
            error_msg = data.get("error_message", "No additional details")
            return f"Geocoding request failed. Status: {status} ({error_msg})"
    except Exception as e:
        return f"Error connecting to Geocoding API: {e}"


def find_nearby_places(latitude: float, longitude: float, place_type: str = "gym", radius_meters: float = 5000.0) -> str:
    """Finds nearby places of a given type around a latitude/longitude location using the Google Places API (New) searchNearby REST endpoint.

    Args:
        latitude: Latitude coordinate of the search center.
        longitude: Longitude coordinate of the search center.
        place_type: Type of place to search for (e.g., 'gym', 'park', 'fitness_center', 'health').
        radius_meters: Radius in meters around the center location (defaults to 5000.0 meters).

    Returns:
        A list of nearby places returning key fields (name, address, location coordinates).
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "GOOGLE_MAPS_API_KEY is not configured in the environment."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }
    payload = {
        "includedTypes": [place_type],
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": radius_meters,
            }
        },
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=6)
        data = response.json()

        if response.status_code == 200 and "places" in data:
            places = data.get("places", [])
            if not places:
                return f"No nearby places of type '{place_type}' found within {radius_meters}m."

            results = [f"### Nearby Places ('{place_type}') Results:"]
            for place in places:
                name = place.get("displayName", {}).get("text", "Unnamed Place")
                address = place.get("formattedAddress", "No address available")
                loc = place.get("location", {})
                lat = loc.get("latitude")
                lng = loc.get("longitude")
                results.append(f"- **Name**: {name}\n  **Address**: {address}\n  **Location**: ({lat}, {lng})")

            return "\n".join(results)
        else:
            error_details = data.get("error", {}).get("message", response.text)
            return f"Places searchNearby request failed (HTTP {response.status_code}): {error_details}"
    except Exception as e:
        return f"Error connecting to Places API (New): {e}"


async def generate_fitness_item_image(item_description: str, tool_context: ToolContext) -> str:
    """Generates an image for a fitness item (e.g. equipment, gear, or meal) using gemini-3.1-flash-lite-image in the global region.
    Saves the image as an ADK artifact for the Playground's Artifacts panel and uploads it directly to Cloud Storage.

    Args:
        item_description: Description of the fitness item to generate an image for (e.g. 'kettlebell', 'protein shake', 'gym locker').
        tool_context: ADK ToolContext injected automatically.

    Returns:
        Public Cloud Storage HTTPS URL of the generated image.
    """
    try:
        from google import genai
        client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=f"High quality photo of {item_description}, clean background, professional product photography",
            config=types.GenerateContentConfig(
                response_modalities=[types.Modality.IMAGE]
            ),
        )

        image_bytes = None
        mime_type = "image/jpeg"
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type

        if not image_bytes:
            return f"Failed to generate image bytes for '{item_description}'."

        ext = "png" if "png" in mime_type else "jpg"
        file_name = f"item_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"

        # 1. Save with tool_context.save_artifact for Playground Artifacts panel
        part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=file_name, artifact=part)

        # 2. Upload image bytes directly to public Cloud Storage bucket
        gcs_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = gcs_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(file_name)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{file_name}"
        return f"Image generated for '{item_description}'! Public URL: {public_url}"
    except Exception as e:
        return f"Error generating item image: {e}"


async def generate_exercise_video(exercise_name: str, tool_context: ToolContext) -> str:
    """Generates a short video demonstrating an exercise or fitness topic using Google's Omni model (gemini-omni-flash-preview) in the global region.
    Saves the video as an ADK artifact for the Playground's Artifacts panel and uploads it directly to Cloud Storage.

    Args:
        exercise_name: Name or description of the exercise/workout item to generate a video for (e.g. 'dumbbell bench press', 'squat form', 'bicep curl').
        tool_context: ADK ToolContext injected automatically.

    Returns:
        Public Cloud Storage HTTPS URL of the generated video.
    """
    try:
        from google import genai
        client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")

        interaction = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=f"A short 3-second animated fitness video demonstration of {exercise_name} exercise form and technique",
        )

        video_bytes = None
        mime_type = "video/mp4"

        if hasattr(interaction, "output_video") and interaction.output_video:
            data = getattr(interaction.output_video, "data", None)
            if data:
                if isinstance(data, str):
                    video_bytes = base64.b64decode(data)
                else:
                    video_bytes = data

        if not video_bytes:
            return f"Failed to generate video bytes for '{exercise_name}'."

        file_name = f"video_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"

        # 1. Save with tool_context.save_artifact for Playground Artifacts panel
        part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=file_name, artifact=part)

        # 2. Upload video bytes directly to public Cloud Storage bucket
        gcs_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = gcs_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(file_name)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{file_name}"
        return f"Exercise video generated for '{exercise_name}'! Public URL: {public_url}"
    except Exception as e:
        return f"Error generating exercise video: {e}"


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    code_executor=code_executor,
    tools=[
        PreloadMemoryTool(),
        list_exercises,
        log_workout,
        get_workout_history,
        calculate_one_rep_max,
        generate_workout_routine,
        generate_milestone_badge,
        search_food_nutrition,
        geocode_address,
        find_nearby_places,
        generate_fitness_item_image,
        generate_exercise_video,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
