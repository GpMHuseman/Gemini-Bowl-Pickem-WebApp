
# main.py
from flask import Flask, render_template, request, redirect, url_for, session
import firebase_admin
from firebase_admin import credentials, firestore
import uuid
import random
import json
import os

app = Flask(__name__)

def get_value_from_json(json_file, key, sub_key):
   try:
       with open(json_file) as f:
           data = json.load(f)
           return data[key][sub_key]
   except Exception as e:
       print("Error reading JSON file: ", e)
       
# --- Securely load secret key from file ---
def load_secret_key():
    try:
        with open('flask-secret-key.json') as f:
            secret_data = json.load(f)
            print("Successfully loaded secret key from file.")
            return secret_data['secret_key']
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        print(f"--- CRITICAL ERROR ---")
        print(f"Could not load secret key : {e}")
        print("Falling back to a temporary, insecure key.")
        # In a real production environment, you might want the app to fail here
        return "temporary_insecure_key_for_development"

app.secret_key = load_secret_key()
# ------------------------------------------

# Global Firebase variables, initialized on app startup.
db = None
firebase_app = None
app_id = None

def get_collection_path(collection_name):
    if app_id:
        return f"artifacts/{app_id}/public/data/{collection_name}"
    return collection_name # Fallback for local testing

# def _backfill_matchup_sort_order(db_client):
#     """
#     Finds any matchups that are missing a 'sortOrder' field and assigns them one.
#     This is a data migration that runs on startup to ensure data integrity.
#     """
#     print("Running startup data migration for matchup sortOrder...")
#     try:
#         matchups_ref = db_client.collection(get_collection_path('matchups'))
#         all_docs = list(matchups_ref.stream())
        
#         docs_to_update = []
#         docs_with_order = []
#         for doc in all_docs:
#             doc_data = doc.to_dict()
#             # Check for missing key or if the value is None
#             if 'sortOrder' not in doc_data or doc_data.get('sortOrder') is None:
#                 docs_to_update.append(doc)
#             else:
#                 docs_with_order.append(doc_data)

#         if docs_to_update:
#             print(f"Found {len(docs_to_update)} matchups missing sortOrder. Backfilling now...")
#             next_sort_order = 1
#             if docs_with_order:
#                 # Find the max sort order, safely handling None and non-numeric values
#                 max_order = 0
#                 for d in docs_with_order:
#                     order = d.get('sortOrder')
#                     if isinstance(order, (int, float)):
#                         if order > max_order:
#                             max_order = order
#                 next_sort_order = int(max_order) + 1
            
#             batch = db_client.batch()
#             # Sort by ID for a consistent order before assigning new sort values
#             docs_to_update.sort(key=lambda d: d.id)
#             for doc in docs_to_update:
#                 batch.update(doc.reference, {'sortOrder': next_sort_order})
#                 next_sort_order += 1
#             batch.commit()
#             print("Successfully backfilled sortOrder for all missing matchups.")
#         else:
#             print("All matchups have a valid sortOrder. No migration needed.")
#     except Exception as e:
#         print(f"--- CRITICAL ERROR during sortOrder backfill migration: {e} ---")

# Function to initialize Firebase Admin SDK.

def initialize_firebase():
    global db, firebase_app, app_id
    if firebase_app is None: # Ensure Firebase is initialized only once
        try:
            cred = credentials.Certificate("private/web-bowl-pickem-firebase-admin-v1.json")
            firebase_app = firebase_admin.initialize_app()
            db = firestore.client()
            print("Firebase initialized successfully.")
            # Run the data migration for sortOrder after db is initialized
            _backfill_matchup_sort_order(db)
        except Exception as e:
            print(f"Error initializing Firebase: {e}")

initialize_firebase()

# --- Flask Routes ---

@app.route('/')
def index():
    return render_template('index.html')

    
@app.route('/user', methods=['GET', 'POST'])
def user_area():
   
    managers = []
    all_matchups = []

    if db:
        try:
            managers_ref = db.collection(get_collection_path('managers'))
            managers = [doc.to_dict() for doc in managers_ref.stream()]
            managers.sort(key=lambda x: x.get('name', '').lower())

            matchups_ref = db.collection(get_collection_path('matchups')).order_by("sortOrder")
            all_matchups = [doc.to_dict() for doc in matchups_ref.stream()]
            #all_matchups.sort(key=lambda x: x.get('team1Name', '').lower())
        except Exception as e:
            print("--- ERROR FETCHING FROM FIRESTORE ---")
            print(f"An exception occurred: {e}")
            print("-------------------------------------")
            # Return an error page or message
            return f"<h1>Error connecting to database</h1><p>Details: {e}</p>", 500

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create_manager':
            manager_name = request.form.get('manager_name')
            if manager_name and db:
                manager_id = str(uuid.uuid4())
                db.collection(get_collection_path('managers')).document(manager_id).set({
                    'id': manager_id,
                    'name': manager_name,
                    'totalScore': 0
                })
        elif action == 'delete_manager':
              manager_id_to_delete = request.form.get('manager_id') # Corrected from 'manager_id'
              if manager_id_to_delete and db:
                db.collection(get_collection_path('managers')).document(manager_id_to_delete).delete()
                picks_ref = db.collection(get_collection_path('picks')).where('managerId', '==', manager_id_to_delete)
                for pick_doc in picks_ref.stream():
                    pick_doc.reference.delete()
        elif action == 'select_manager':
            manager_id = request.form.get('manager_id_select')
            if manager_id:
                session['selected_manager_id'] = manager_id
                return redirect(url_for('user_area_manager_picks', manager_id=manager_id))
        elif action == 'create_matchup':
            team1_name = request.form.get('team1_name')
            team2_name = request.form.get('team2_name')
            if team1_name and team2_name and db:
                matchups_ref = db.collection(get_collection_path('matchups'))
                # Get the highest sortOrder and add 1
                last_matchups = matchups_ref.order_by("sortOrder", direction=firestore.Query.DESCENDING).limit(1).get()
                new_sort_order = 1
                if last_matchups:
                    new_sort_order = last_matchups[0].to_dict()['sortOrder'] + 1
                
                matchup_id = str(uuid.uuid4())
                db.collection(get_collection_path('matchups')).document(matchup_id).set({
                    'id': matchup_id,
                    'team1Name': team1_name,
                    'team2Name': team2_name,
                    'team1Id': str(uuid.uuid4()),
                    'team2Id': str(uuid.uuid4()),
                    'winnerTeamId': None,
                    'sortOrder': new_sort_order
                })
        elif action == 'delete_matchup':
            matchup_id = request.form.get('matchup_id_delete')
            if matchup_id and db:
                db.collection(get_collection_path('matchups')).document(matchup_id).delete()
                picks_ref = db.collection(get_collection_path('picks')).where('matchupId', '==', matchup_id)
                for pick_doc in picks_ref.stream():
                    pick_doc.reference.delete()

        return redirect(url_for('user_area'))

    return render_template('user.html', managers=managers, all_matchups=all_matchups)


@app.route('/user/manager/<manager_id>', methods=['GET', 'POST'])
def user_area_manager_picks(manager_id):
    if not db:
        return "Database not initialized.", 500

    manager_doc = db.collection(get_collection_path('managers')).document(manager_id).get()
    if not manager_doc.exists:
        return "Manager not found.", 404
    manager = manager_doc.to_dict()

    matchups_ref = db.collection(get_collection_path('matchups')).order_by("sortOrder")
    all_matchups = [doc.to_dict() for doc in matchups_ref.stream()]
    #all_matchups.sort(key=lambda x: x.get('team1Name', '').lower())

    picks_ref = db.collection(get_collection_path('picks')).where('managerId', '==', manager_id)
    existing_picks = {pick.get('matchupId'): pick for pick in [doc.to_dict() for doc in picks_ref.stream()]}

    num_matchups = len(all_matchups)
    all_possible_points = set(range(1, num_matchups + 1))
    used_points = {pick['points'] for pick in existing_picks.values()}
    available_points = sorted(list(all_possible_points - used_points))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'save_pick':
            tie_breaker_score_str = request.form.get('tie_breaker_score')
            if tie_breaker_score_str and tie_breaker_score_str.isdigit():
                tie_breaker_score = int(tie_breaker_score_str)
                db.collection(get_collection_path('managers')).document(manager_id).set({
                    'id': manager_id,
                    'name': manager.get('name'),
                    'totalScore': 0,
                    'tieBreakerScore': tie_breaker_score
                })
            matchup_ids = request.form.getlist('matchup_id')
            for matchup_id_pick in matchup_ids:
                picked_team_id = request.form.get(f'pick_matchup_{matchup_id_pick}')
                points_str = request.form.get(f'points_matchup_{matchup_id_pick}')
                if not all([matchup_id_pick, picked_team_id, points_str]): continue
                try: points = int(points_str)
                except ValueError: continue
                pick_doc_id = f"{manager_id}_{matchup_id_pick}"
                db.collection(get_collection_path('picks')).document(pick_doc_id).set({
                    'managerId': manager_id, 'matchupId': matchup_id_pick, 'pickedTeamId': picked_team_id, 'points': points
                })
            return redirect(url_for('user_area_manager_picks', manager_id=manager_id))

        elif action == 'create_matchup':
            team1_name = request.form.get('team1_name')
            team2_name = request.form.get('team2_name')
            if team1_name and team2_name and db:
                matchup_id_new = str(uuid.uuid4())
                db.collection(get_collection_path('matchups')).document(matchup_id_new).set({
                    'id': matchup_id_new, 'team1Name': team1_name, 'team2Name': team2_name,
                    'team1Id': str(uuid.uuid4()), 'team2Id': str(uuid.uuid4()), 'winnerTeamId': None
                })
        elif action == 'delete_matchup':
            matchup_id_to_delete = request.form.get('matchup_id_delete')
            if matchup_id_to_delete and db:
                db.collection(get_collection_path('matchups')).document(matchup_id_to_delete).delete()
                picks_ref_del = db.collection(get_collection_path('picks')).where('matchupId', '==', matchup_id_to_delete)
                for pick_doc in picks_ref_del.stream(): pick_doc.reference.delete()
        
        return redirect(url_for('user_area_manager_picks', manager_id=manager_id))

    return render_template('user_manager_picks.html', manager=manager, all_matchups=all_matchups, existing_picks=existing_picks, available_points=available_points)

@app.route('/edit-matchup/<matchup_id>', methods=['GET', 'POST'])
def edit_matchup_page(matchup_id):
    if not db: return "Database not initialized.", 500
    matchup_ref = db.collection(get_collection_path('matchups')).document(matchup_id)
    matchup_doc = matchup_ref.get()
    if not matchup_doc.exists: return "Matchup not found.", 404

    if request.method == 'POST':
        new_team1_name = request.form.get('new_team1_name')
        new_team2_name = request.form.get('new_team2_name')
        if new_team1_name and new_team2_name:
            matchup_ref.update({'team1Name': new_team1_name, 'team2Name': new_team2_name})
            next_url = request.args.get('next') or url_for('user_area')
            return redirect(next_url)
        else: return "Missing form data.", 400
    
    return render_template('edit_matchup.html', matchup=matchup_doc.to_dict())

@app.route('/admin', methods=['GET', 'POST'])
def admin_area():
    if not db: return "Database not initialized.", 500

    matchups_ref = db.collection(get_collection_path('matchups')).order_by("sortOrder")
    all_matchups = [doc.to_dict() for doc in matchups_ref.stream()]
    #all_matchups.sort(key=lambda x: x.get('team1Name', '').lower())

    if request.method == 'POST':
        matchup_ids = request.form.getlist('matchup_id')
        for matchup_id in matchup_ids:
            winner_team_id = request.form.get(f'winner_matchup_{matchup_id}')
            if matchup_id and winner_team_id:
                db.collection(get_collection_path('matchups')).document(matchup_id).update({'winnerTeamId': winner_team_id})
        
        # Recalculate scores for all managers
        managers_ref = db.collection(get_collection_path('managers'))
        all_managers = [doc.to_dict() for doc in managers_ref.stream()]
        for manager in all_managers:
            current_score = 0
            picks_ref = db.collection(get_collection_path('picks')).where('managerId', '==', manager['id'])
            manager_picks = [doc.to_dict() for doc in picks_ref.stream()]
            for pick in manager_picks:
                matchup_doc = db.collection(get_collection_path('matchups')).document(pick['matchupId']).get()
                if matchup_doc.exists:
                    matchup_data = matchup_doc.to_dict()
                    if matchup_data.get('winnerTeamId') == pick.get('pickedTeamId'):
                        current_score += pick.get('points', 0)
            db.collection(get_collection_path('managers')).document(manager['id']).update({'totalScore': current_score})
        return redirect(url_for('admin_area'))
        
    return render_template('admin.html', all_matchups=all_matchups)

# @app.route('/admin/backfill_sort_order', methods=['POST'])
# def backfill_sort_order():
#     """
#     Finds any matchups that are missing a 'sortOrder' field and assigns them one.
#     This is useful for migrating data created before the reordering feature was added.
#     """
#     if not db:
#         return "Database not initialized.", 500

#     matchups_ref = db.collection(get_collection_path('matchups'))
#     all_docs = list(matchups_ref.stream())
    
#     docs_to_update = []
#     docs_with_order = []
#     for doc in all_docs:
#         doc_data = doc.to_dict()
#         if 'sortOrder' not in doc_data or doc_data.get('sortOrder') is None:
#             docs_to_update.append(doc)
#         else:
#             docs_with_order.append(doc_data)

#     if docs_to_update:
#         next_sort_order = 1
#         if docs_with_order:
#             # Find the max sort order, safely handling None values
#             max_order = max(d.get('sortOrder', 0) for d in docs_with_order if d.get('sortOrder') is not None)
#             next_sort_order = max_order + 1
            
#         batch = db.batch()
#         # Sort by ID for a consistent order before assigning new sort values
#         docs_to_update.sort(key=lambda d: d.id)
#         for doc in docs_to_update:
#             batch.update(doc.reference, {'sortOrder': next_sort_order})
#             next_sort_order += 1
#         batch.commit()

#     return redirect(url_for('admin_area'))

@app.route('/move-matchup/<matchup_id>/<direction>', methods=['POST'])
def move_matchup(matchup_id, direction):
    if not db: return "Database not initialized.", 500
    
    matchups_ref = db.collection(get_collection_path('matchups'))
    
    # Get all matchups, sorted
    all_matchups = [doc for doc in matchups_ref.order_by("sortOrder").stream()]
    
    # Find the index of the matchup to move
    doc_to_move_index = -1
    for i, doc in enumerate(all_matchups):
        if doc.id == matchup_id:
            doc_to_move_index = i
            break

    if doc_to_move_index == -1:
        return "Matchup not found", 404

    # Determine the swap index
    if direction == 'up' and doc_to_move_index > 0:
        swap_index = doc_to_move_index - 1
    elif direction == 'down' and doc_to_move_index < len(all_matchups) - 1:
        swap_index = doc_to_move_index + 1
    else:
        return redirect(url_for('user_area')) # No move needed

    # Get the two documents to swap
    doc1 = all_matchups[doc_to_move_index]
    doc2 = all_matchups[swap_index]

    # Swap their sortOrder values
    sort_order_1 = doc1.to_dict()['sortOrder']
    sort_order_2 = doc2.to_dict()['sortOrder']
    
    # Perform the swap in a transaction
    @firestore.transactional
    def swap_order(transaction, ref1, ref2):
        transaction.update(ref1, {'sortOrder': sort_order_2})
        transaction.update(ref2, {'sortOrder': sort_order_1})

    transaction = db.transaction()
    swap_order(transaction, doc1.reference, doc2.reference)

    return redirect(url_for('user_area'))

@app.route('/standings')
def standings_area():
    if not db: return "Database not initialized.", 500
    managers_ref = db.collection(get_collection_path('managers'))
    all_managers = [doc.to_dict() for doc in managers_ref.stream()]
    matchups_ref = db.collection(get_collection_path('matchups'))
    all_matchups = {m['id']: m for m in [doc.to_dict() for doc in matchups_ref.stream()]}
    picks_ref = db.collection(get_collection_path('picks'))
    all_picks_raw = [doc.to_dict() for doc in picks_ref.stream()]
    all_manager_picks = {}
    for pick in all_picks_raw:
        manager_id = pick['managerId']
        if manager_id not in all_manager_picks: all_manager_picks[manager_id] = {}
        all_manager_picks[manager_id][pick['matchupId']] = pick

    standings_data = []
    for manager in all_managers:
        manager_id = manager['id']
        total_score = manager.get('totalScore', 0)
        max_possible_score = total_score
        manager_picks = all_manager_picks.get(manager_id, {})
        for matchup_id, pick_data in manager_picks.items():
            matchup = all_matchups.get(matchup_id)
            if matchup and matchup.get('winnerTeamId') is None:
                max_possible_score += pick_data.get('points', 0)
        standings_data.append({
            'name': manager['name'], 'totalScore': total_score, 'maxPossibleScore': max_possible_score
        })
    standings_data.sort(key=lambda x: x['totalScore'], reverse=True)
    return render_template('standings.html', standings=standings_data)

@app.route('/projections')
def projections_area():
    if not db: return "Database not initialized.", 500
    managers_ref = db.collection(get_collection_path('managers'))
    all_managers = [doc.to_dict() for doc in managers_ref.stream()]
    matchups_ref = db.collection(get_collection_path('matchups'))
    all_matchups = {m['id']: m for m in [doc.to_dict() for doc in matchups_ref.stream()]}
    picks_ref = db.collection(get_collection_path('picks'))
    all_picks_raw = [doc.to_dict() for doc in picks_ref.stream()]
    all_manager_picks = {}
    for pick in all_picks_raw:
        manager_id = pick['managerId']
        if manager_id not in all_manager_picks: all_manager_picks[manager_id] = {}
        all_manager_picks[manager_id][pick['matchupId']] = pick

    remaining_matchups = [m for m in all_matchups.values() if m.get('winnerTeamId') is None]
    num_simulations = 10000
    manager_win_counts = {manager['id']: 0 for manager in all_managers}

    for _ in range(num_simulations):
        simulated_scores = {manager['id']: manager.get('totalScore', 0) for manager in all_managers}
        for r_matchup in remaining_matchups:
            winner_team_id = random.choice([r_matchup['team1Id'], r_matchup['team2Id']])
            for manager in all_managers:
                manager_id = manager['id']
                manager_pick = all_manager_picks.get(manager_id, {}).get(r_matchup['id'])
                if manager_pick and manager_pick['pickedTeamId'] == winner_team_id:
                    simulated_scores[manager_id] += manager_pick['points']
        if not simulated_scores: continue
        max_score = max(simulated_scores.values())
        winning_managers_in_sim = [mid for mid, score in simulated_scores.items() if score == max_score]
        for winner_id in winning_managers_in_sim:
            manager_win_counts[winner_id] += 1

    projections = []
    for manager in all_managers:
        manager_id = manager['id']
        probability = (manager_win_counts[manager_id] / num_simulations) * 100 if num_simulations > 0 else 0
        projections.append({'name': manager['name'], 'probability': f"{probability:.2f}%"})
    projections.sort(key=lambda x: float(x['probability'].strip('%')), reverse=True)
    return render_template('projections.html', projections=projections)

#if __name__ == '__main__':
    #app.run(debug=False, use_reloader=False, host='0.0.0.0', port=5000)
