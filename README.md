# MutualArt Article Generator AI Service

This project is a FastAPI-based backend service that automatically generates sophisticated editorial articles about specific artists. It fetches an artist's top auction records, artwork details, and volume turnover data from the MutualArt GraphQL API, and then uses the `xai_sdk` (Grok) to synthesize a narrative article analyzing their market legacy.

## Features
- **FastAPI Backend:** Clean, high-performance API endpoint structure.
- **RESTful Endpoints:** Generate articles simultaneously using standard HTTP requests.
- **Auto-generated Documentation:** Built-in interactive Swagger UI to explore and test the API.
- **Safe Networking Optimization:** Uses `requests.Session()` to reuse TCP connections, dramatically decreasing latency and overhead when connecting to the MutualArt GraphQL API.

## Project Structure
```text
Project/
│
├── main.py                  # The FastAPI entry point housing the API endpoints
├── services/
│   ├── __init__.py          
│   ├── prompt_builder.py    # Handles all GraphQL requests & prompt string creation
│   └── grok_client.py       # Handles the xAI/Grok LLM integration wrapper
├── chart_data_formatter.py  # Utility for formatting charts (untouched legacy)
├── requirements.txt         # Project dependencies
└── README.md                # This file
```

## Prerequisites

- **Python 3.8+**
- **XAI API Key:** You must have an active API key to access Grok models via the `xai_sdk`. 

## Setup Instructions

### 1. Create a Virtual Environment (Recommended)

To isolate dependencies, it is highly recommended to use a virtual environment:

```bash
# On Windows
python -m venv venv
.\venv\Scripts\activate

# On Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

Ensure your virtual environment is active, then install the necessary packages using the `requirements.txt` file we generated:

```bash
pip install -r requirements.txt
```

*(Note: The core dependencies are `fastapi`, `uvicorn`, `requests`, `python-dotenv`, and `xai_sdk`.)*

### 3. Environment Variables

Create a `.env` file at the root of the project directory (in `C:\Users\Dell\Desktop\Project\`) and add your Grok API key:

```env
# .env file content
XAI_API_KEY=your_actual_api_key_here
```

*Note on MutualArt Auth: The MutualArt authentication token (`AUTH_TOKEN`) currently resides inside `services/prompt_builder.py`. In a future iteration, this should also be moved securely into this `.env` file.*

## Running the Service

Start the FastAPI application by using `uvicorn` as the ASGI web server. Run the following command from the root of the project directory:

```bash
uvicorn main:app --reload
```
*The `--reload` flag automatically unloads and reloads the server if you make any changes to the code while it is running.*

The server will start up on `http://127.0.0.1:8000`.

## Using the API

### 1. Interactive documentation (Easiest way to test)
FastAPI automatically builds an interactive Swagger UI. Once the server is running, open a browser and go to:
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

From here, you can click on the `GET /generate-article/{artist_id}` route, click **"Try it out"**, fill in an artist ID (e.g., `68EFD50CBA356F91`), and execute the request directly from the UI.

### 2. Direct HTTP Requests 
You can integrate this service into your front-end apps or make requests via cURL, Postman, or Thunder Client:

```bash
# Example cURL request
curl -X 'GET' \
  'http://127.0.0.1:8000/generate-article/68EFD50CBA356F91' \
  -H 'accept: application/json'
```

### Example Output
The API will return a JSON object populated with the generated article:
```json
{
  "artist_id": "68EFD50CBA356F91",
  "article": "MutualArt | [Current Date]\n\nEdward Munch’s 5 Most Expensive Works...\n..."
}
```

## Troubleshooting
- **Missing `XAI_API_KEY`:** If you see an `HTTP 500 Internal Server Error` stating the key is missing from `.env`, double check that you created the `.env` file and correctly named the variable inside.
- **GraphQL Errors:** If you see `An error occurred: GraphQL Errors: ...`, MutualArt may have invalidated the hardcoded authorization token inside `prompt_builder.py` or updated their schema.
