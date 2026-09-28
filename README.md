# FitCoach AI — Agentic Fitness & Workout Assistant

FitCoach AI is an intelligent fitness coaching agent built with Google's **Agent Development Kit (ADK)** and deployed to **Agent Runtime**. It provides personalized workout catalog lookups, strength calculations, exercise form videos, nutrition facts, nearby gym searches, and milestone achievement tracking rendered through an interactive **A2UI** frontend.

![FitCoach AI Demo](demo.gif)

---

## 🌟 Implemented Features & GCP Architecture

All capabilities listed below are fully implemented in code (`app/agent.py`) and backed by Google Cloud infrastructure:

### 1. 🧠 Cross-Session Long-Term Memory (Vertex AI Memory Bank)
- **PreloadMemoryTool & After-Agent Callbacks**: Automatically loads prior user conversation memories upon session start and generates persistent facts across session boundaries using Vertex AI Memory Bank on Agent Engine.

### 2. 🗄️ Firestore Database Integration
- **Exercise Library Catalog (`list_exercises`)**: Queries the Firestore `exercises` collection by muscle group (e.g. chest, legs, arms, core).
- **Workout Set Logging (`log_workout`)**: Persists structured workout logs (exercise name, weight, reps, sets) into the Firestore `workout_logs` collection.
- **Training History (`get_workout_history`)**: Retrieves user workout logs sorted chronologically from Firestore.

### 3. 🖼️ AI Image Generation (Google Gemini Image Model)
- **`generate_fitness_item_image`**: Uses `gemini-3.1-flash-lite-image` in the `global` region to generate fitness visual illustrations.
- **Dual Destination**: Saves images as ADK artifacts (`tool_context.save_artifact`) for the Playground Artifacts panel AND uploads image bytes directly to a public Cloud Storage bucket.

### 4. 🎥 AI Video Generation (Google Omni Model)
- **`generate_exercise_video`**: Uses `gemini-omni-flash-preview` in the `global` region to generate short 3-second animated exercise form videos.
- **Dual Destination**: Saves video files as ADK artifacts for the Playground panel AND uploads MP4 bytes directly to a public Cloud Storage bucket.

### 5. 🗺️ Google Maps & Places Integration
- **`geocode_address`**: Converts street addresses to geographic latitude/longitude coordinates via Google Maps API.
- **`find_nearby_places`**: Locates nearby gyms, fitness centers, and sports facilities using Google Places API.

### 6. 📊 Strength Calculations & Workout Generators
- **`calculate_one_rep_max`**: Computes 1-Rep Max (1RM) using the Epley formula and outputs training intensity percentage tables (90%, 80%, 70%).
- **`generate_workout_routine`**: Generates tailored training splits (e.g., Push/Pull/Legs) based on fitness goals.
- **`generate_milestone_badge`**: Generates custom achievement badges for completed workout milestones.

### 7. 🥗 Nutrition Facts Lookup
- **`search_food_nutrition`**: Searches food items and retrieves macronutrients (calories, protein, carbs, fat) via Open Food Facts API.

### 8. 🐍 Python Code Execution
- **`AgentEngineSandboxCodeExecutor`**: Safely executes Python code snippets in a sandbox environment for fitness math and data analysis.

### 9. 🎨 Modern Frontend & A2UI Renderer
- **FastAPI Proxy**: Proxies browser chat requests to the deployed A2A agent.
- **Category Quick-Filter Bar**: Quick filter pills (`🏋️ Chest`, `🦵 Legs`, `💪 Arms`, `📊 1RM Calculator`, `🏆 Badges`, `🧘 Core`).
- **Native A2UI Renderer**: Lightweight client-side renderer that displays rich agent cards, columns, rows, images, and videos directly in the chat dialogue.

---

## 📁 Repository Structure

```
fitcoach-ai/
├── app/
│   ├── agent.py               # Core ADK agent, tools, callbacks, and A2UI instruction
│   └── fast_api_app.py        # FastAPI server entrypoint
├── frontend/
│   ├── main.py                # FastAPI proxy server (A2A protocol bridge)
│   └── static/
│       └── index.html         # Custom chat web UI with A2UI renderer & category bar
├── demo.gif                   # Looping video demo of live agent
├── seed_firestore.py          # Firestore database seeding script
├── pyproject.toml             # Python dependencies (ADK, google-genai, google-cloud-firestore)
└── agents-cli-manifest.yaml   # Agent Engine deployment manifest
```

---

## 🛠️ Local Development & Setup Instructions

### Prerequisites
- Python 3.10+
- `uv` package manager (`pip install uv`)
- `google-agents-cli` (`uv tool install google-agents-cli`)
- Google Cloud SDK (`gcloud`) with authenticated GCP credentials (`gcloud auth application-default login`)

### 1. Install Dependencies
```bash
agents-cli install
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your API key:
```bash
cp .env.example .env
```
Ensure your `.env` contains:
```ini
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
GOOGLE_GENAI_USE_VERTEXAI=true
```

### 3. Seed Firestore Database
Populate the exercise library catalog:
```bash
uv run python seed_firestore.py
```

### 4. Run Agent Playground Locally
Start the ADK Web Playground to test tools and memory interactively:
```bash
uv run adk web . --port 8080 --reload_agents
```

### 5. Run the Custom Web Frontend
In a separate terminal, launch the FastAPI proxy web application:
```bash
uv run python frontend/main.py
```
Open your browser to the local port output by the server.

---

## 🚀 Deployment

### Deploying Agent to Agent Runtime
Deploy the agent to Google Cloud Agent Runtime via `agents-cli`:

```bash
GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_LOCATION=us-east1 agents-cli deploy \
  --project <YOUR_GCP_PROJECT_ID> \
  --service-name simple-agent \
  --update-env-vars GOOGLE_MAPS_API_KEY=<YOUR_KEY>,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_LOCATION=us-east1
```

### Deploying Frontend to Cloud Run
Deploy the FastAPI proxy frontend service:

```bash
gcloud run deploy fitcoach-frontend \
  --source ./frontend \
  --region us-east1 \
  --set-env-vars AGENT_ENGINE_RESOURCE_NAME=<YOUR_AGENT_ENGINE_RESOURCE_NAME>,AGENT_DIRECTORY=app \
  --allow-unauthenticated
```
