# Eunoia - AI Companion Journal

Eunoia is a privacy-first, AI-powered personal journal that helps users uncover meaningful patterns in their daily lives. Built for the Google Cloud Run AI Challenge.

## Features
*   **Empathetic Reflections:** Gemini provides immediate, supportive feedback on daily entries.
*   **Life Pattern Radar:** Analyzes batch history to identify trends in mood, stress, and habits.
*   **Inkwell Design System:** A responsive, typography-focused UI with persistent Light/Dark mode.
*   **Secure Isolation:** Firebase Auth and Firestore rules ensure absolute data privacy per user.

## Tech Stack
*   **Frontend:** HTML/Tailwind CSS, Firebase Auth (Web SDK)
*   **Backend:** Python Flask, Google GenAI SDK (Gemini 3.6-flash)
*   **Infrastructure:** Google Cloud Run, Cloud Secret Manager, Firestore

## Local Deployment Steps
1. Clone the repository.
2. Install requirements: `pip install -r requirements.txt`
3. Place your Firebase Admin `serviceAccountKey.json` in the root directory.
4. Update the `index.html` Firebase configuration block with your web client keys.
5. Run the server: `python app.py`
6. Open `http://127.0.0.1:5000`

## Cloud Run Deployment Steps
1. Authenticate with Google Cloud CLI: `gcloud auth login`
2. Ensure Secret Manager holds your `GEMINI_API_KEY` and the Cloud Run service account has the `SecretAccessor` role.
3. Deploy the container with the required challenge label:
   ```bash
   gcloud run deploy gemini-journal \
     --source . \
     --region asia-southeast1 \
     --allow-unauthenticated \
     --update-labels dev-tutorial=cloud-run-ai-challenge
