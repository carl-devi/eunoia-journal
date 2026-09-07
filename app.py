import os
import json
from flask import Flask, render_template, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth
from google.cloud import secretmanager
from google import genai

app = Flask(__name__)

if os.path.exists('serviceAccountKey.json'):
    cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred)
else:
    # Explicitly tell Cloud Run which project to use for token verification
    firebase_admin.initialize_app(options={'projectId': 'gemini-journal-14b2a'})
    
db = firestore.client()

def get_gemini_key():
    client = secretmanager.SecretManagerServiceClient()
    project_id = "gemini-journal-14b2a"
    name = f"projects/{project_id}/secrets/GEMINI_API_KEY/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

os.environ["GEMINI_API_KEY"] = get_gemini_key()
gemini_client = genai.Client()

def verify_token(req):
    auth_header = req.headers.get('Authorization')
    if not auth_header:
        raise Exception('No auth header')
    id_token = auth_header.split('Bearer ')[1]
    return firebase_auth.verify_id_token(id_token)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/api/journal', methods=['POST'])
def journal_entry():
    try:
        decoded_token = verify_token(request)
        uid = decoded_token['uid']
    except Exception:
        return jsonify({'error': 'Unauthorized access'}), 401
        
    data = request.json
    user_prompt = data.get('prompt')
    mood = data.get('mood')

    if not user_prompt or not isinstance(user_prompt, str):
        return jsonify({'error': 'Invalid input'}), 400

    try:
        response = gemini_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=f"Act as a journaling assistant. Reflect on this entry and provide a brief, insightful summary: {user_prompt}"
        )
        ai_reply = response.text

        doc_ref = db.collection('users').document(uid).collection('entries').document()
        doc_ref.set({
            'prompt': user_prompt,
            'summary': ai_reply,
            'mood': mood,
            'timestamp': firestore.SERVER_TIMESTAMP
        })

        return jsonify({'summary': ai_reply, 'prompt': user_prompt, 'mood': mood})
    except Exception as e:
        print(f"Server Error: {e}") 
        return jsonify({'error': 'An internal error occurred.'}), 500

@app.route('/api/journal/history', methods=['GET'])
def get_history():
    try:
        decoded_token = verify_token(request)
        uid = decoded_token['uid']
    except Exception:
        return jsonify({'error': 'Unauthorized access'}), 401

    try:
        entries_ref = db.collection('users').document(uid).collection('entries').order_by('timestamp', direction=firestore.Query.DESCENDING)
        docs = entries_ref.stream()
        history = []
        for doc in docs:
            data = doc.to_dict()
            time_val = data.get('timestamp')
            time_str = time_val.strftime('%B %d, %Y - %I:%M %p') if time_val else "Just now"
            history.append({
                'id': doc.id,
                'prompt': data.get('prompt', ''),
                'summary': data.get('summary', ''),
                'mood': data.get('mood'),
                'date': time_str
            })
        return jsonify({'history': history})
    except Exception as e:
        return jsonify({'error': 'Failed to load history.'}), 500

@app.route('/api/journal/patterns', methods=['GET'])
def get_patterns():
    try:
        decoded_token = verify_token(request)
        uid = decoded_token['uid']
    except Exception:
        return jsonify({'error': 'Unauthorized access'}), 401

    try:
        patterns_ref = db.collection('users').document(uid).collection('patterns').order_by('createdAt', direction=firestore.Query.DESCENDING).limit(10)
        docs = patterns_ref.stream()
        patterns = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            patterns.append(data)
        return jsonify({'patterns': patterns})
    except Exception as e:
        return jsonify({'error': 'Failed to load patterns.'}), 500

@app.route('/api/journal/patterns/generate', methods=['POST'])
def generate_patterns():
    try:
        decoded_token = verify_token(request)
        uid = decoded_token['uid']
    except Exception:
        return jsonify({'error': 'Unauthorized access'}), 401

    try:
        # Fetch last 30 entries for analysis
        entries_ref = db.collection('users').document(uid).collection('entries').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(30)
        docs = entries_ref.stream()
        entries_text = ""
        entry_count = 0
        
        for doc in docs:
            data = doc.to_dict()
            time_val = data.get('timestamp')
            date_str = time_val.strftime('%Y-%m-%d') if time_val else "Unknown Date"
            entries_text += f"Date: {date_str} | Mood: {data.get('mood', 'None')} | Entry: {data.get('prompt', '')}\n---\n"
            entry_count += 1

        if entry_count < 3:
            return jsonify({'error': 'Not enough entries to generate patterns. Write a few more first!'}), 400

        prompt = f"""
        Act as an empathetic psychological analyst. Analyze the following journal entries.
        Identify meaningful recurring patterns, trends, or connections (e.g., mood, stress, habits).
        Output ONLY a valid JSON array of objects. Do not include markdown formatting like ```json.
        Each object must have exactly these keys:
        - "type": Category (e.g., "Recurring Pattern", "Positive Trend", "Habit Connection", "Personal Growth", "Recurring Thought")
        - "title": A short summary (e.g., "Stress around deadlines")
        - "description": Detailed explanation. Use language like "You may be noticing...", "There seems to be a pattern...", "Your entries suggest...". Never state as absolute objective fact.
        - "evidence": Specific reasoning based on the texts.
        - "relatedDates": Array of date strings where this pattern appeared.
        
        Entries:
        {entries_text}
        """

        response = gemini_client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt
        )
        
        # Clean potential markdown from Gemini response
        raw_json = response.text.replace('```json', '').replace('```', '').strip()
        new_patterns = json.loads(raw_json)

        saved_patterns = []
        batch = db.batch()
        for p in new_patterns:
            doc_ref = db.collection('users').document(uid).collection('patterns').document()
            p['createdAt'] = firestore.SERVER_TIMESTAMP
            batch.set(doc_ref, p)
            # Make JSON serializable for immediate frontend response
            p['createdAt'] = 'Just now'
            p['id'] = doc_ref.id
            saved_patterns.append(p)
            
        batch.commit()

        return jsonify({'patterns': saved_patterns})

    except Exception as e:
        print(f"Pattern Gen Error: {e}")
        return jsonify({'error': 'Failed to generate patterns.'}), 500

@app.route('/api/journal/patterns/<pattern_id>', methods=['DELETE'])
def delete_pattern(pattern_id):
    try:
        decoded_token = verify_token(request)
        uid = decoded_token['uid']
        db.collection('users').document(uid).collection('patterns').document(pattern_id).delete()
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': 'Failed to delete pattern.'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)