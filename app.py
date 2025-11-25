
# app.py
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
       print("Error: ", e)
       
print(get_value_from_json("web-bowl-pickem-firebase-adminsdk-fbsvc-abe019eb85.json", "db", "host")) # prints localhost
# A secret key is required for Flask sessions to work.
# In a production environment, this should be a strong, randomly generated key
# loaded from an environment variable or secure configuration.
app.secret_key = get_value_from_json("flask-secret-key.json", "flask-key", "host")

# Global Firebase variables, initialized on app startup.
# These will be populated from the Canvas environment's global variables.
db = None
firebase_app = None
auth_client = None # Not directly used for user auth in this admin-style app, but good practice
app_id = None

# Function to initialize Firebase Admin SDK.
# This function attempts to use the __firebase_config and __app_id global variables
# provided by the Canvas environment.
def initialize_firebase():
    global db, firebase_app, app_id
    if firebase_app is None: # Ensure Firebase is initialized only once
        try:
            # Retrieve Firebase configuration and app ID from global variables.
            # These are expected to be provided by the Canvas environment.
            ##firebase_config_str = globals().get('__firebase_config', '{}')
            ##firebase_config = json.loads(firebase_config_str)
            ##app_id = globals().get('__app_id', 'default-app-id')

            # Initialize Firebase Admin SDK using the provided credentials.
            cred = credentials.Certificate("private/web-bowl-pickem-firebase-adminsdk-fbsvc-abe019eb85.json")
            firebase_app = firebase_admin.initialize_app(cred)
            db = firestore.client()
            print("Firebase initialized successfully.")
        except Exception as e:
            # Print an error if Firebase initialization fails.
            # This is crucial for debugging in the Canvas environment.
            print(f"Error initializing Firebase: {e}")
            # If config is missing, run without database persistence.
            ##if not firebase_config:
                ##print("Firebase config not found. Running without Firebase persistence.")
                ##db = None # Set db to None to indicate no database connection

# Call the initialization function when the Flask app starts.
initialize_firebase()

# Helper function to construct Firestore collection paths.
# This ensures data is stored correctly within the Canvas environment's
# artifact structure (e.g., artifacts/{appId}/public/data/{collection_name}).
def get_collection_path(collection_name):
    if app_id:
        return f"artifacts/{app_id}/public/data/{collection_name}"
    return collection_name # Fallback for local testing without app_id

# --- Flask Routes ---

@app.route('/')
def index():
    """Renders the main index page with navigation links."""
    return render_template('index.html')

@app.route('/user', methods=['GET', 'POST'])
def user_area():
    """
    Handles manager creation, deletion, and selection in the User Area.
    Also displays a global list of matchups for reference.
    """
    managers = []
    all_matchups = [] # To display global matchups for reference

    if db:
        # Fetch all managers
        managers_ref = db.collection(get_collection_path('managers'))
        managers = [doc.to_dict() for doc in managers_ref.stream()]
        managers.sort(key=lambda x: x.get('name', '').lower()) # Sort managers alphabetically

        # Fetch all matchups (for global display in user area)
        matchups_ref = db.collection(get_collection_path('matchups'))
        all_matchups = [doc.to_dict() for doc in matchups_ref.stream()]
        all_matchups.sort(key=lambda x: x.get('team1Name', '').lower()) # Sort matchups

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create_manager':
            manager_name = request.form.get('manager_name')
            if manager_name and db:
                manager_id = str(uuid.uuid4()) # Generate a unique ID for the new manager
                db.collection(get_collection_path('managers')).document(manager_id).set({
                    'id': manager_id,
                    'name': manager_name,
                    'totalScore': 0 # Initialize total score to 0
                })
                print(f"Manager '{manager_name}' created.")
        elif action == 'delete_manager':
            manager_id = request.form.get('manager_id')
            if manager_id and db:
                # Delete the manager document
                db.collection(get_collection_path('managers')).document(manager_id).delete()
                # Also delete all picks associated with this manager to maintain data integrity
                picks_ref = db.collection(get_collection_path('picks')).where('managerId', '==', manager_id)
                for pick_doc in picks_ref.stream():
                    pick_doc.reference.delete()
                print(f"Manager '{manager_id}' and their picks deleted.")
        elif action == 'select_manager':
            manager_id = request.form.get('manager_id_select')
            if manager_id:
                # Store selected manager ID in session for persistence across requests
                session['selected_manager_id'] = manager_id
                # Redirect to the specific manager's picks page
                return redirect(url_for('user_area_manager_picks', manager_id=manager_id))
        elif action == 'create_matchup':
            # This action is also handled in user_area_manager_picks, but included here for completeness
            # if a user creates a matchup before selecting a manager.
            team1_name = request.form.get('team1_name')
            team2_name = request.form.get('team2_name')
            if team1_name and team2_name and db:
                matchup_id = str(uuid.uuid4())
                team1_id = str(uuid.uuid4()) # Unique ID for Team 1
                team2_id = str(uuid.uuid4()) # Unique ID for Team 2
                db.collection(get_collection_path('matchups')).document(matchup_id).set({
                    'id': matchup_id,
                    'team1Name': team1_name,
                    'team2Name': team2_name,
                    'team1Id': team1_id,
                    'team2Id': team2_id,
                    'winnerTeamId': None # Winner is initially not set
                })
                print(f"Matchup '{team1_name}' vs '{team2_name}' created.")
        elif action == 'edit_matchup':
            matchup_id = request.form.get('matchup_id_edit')
            new_team1_name = request.form.get('new_team1_name')
            new_team2_name = request.form.get('new_team2_name')
            if matchup_id and new_team1_name and new_team2_name and db:
                db.collection(get_collection_path('matchups')).document(matchup_id).update({
                    'team1Name': new_team1_name,
                    'team2Name': new_team2_name
                })
                print(f"Matchup '{matchup_id}' updated.")
        elif action == 'delete_matchup':
            matchup_id = request.form.get('matchup_id_delete')
            if matchup_id and db:
                db.collection(get_collection_path('matchups')).document(matchup_id).delete()
                # Delete all picks associated with this matchup
                picks_ref = db.collection(get_collection_path('picks')).where('matchupId', '==', matchup_id)
                for pick_doc in picks_ref.stream():
                    pick_doc.reference.delete()
                print(f"Matchup '{matchup_id}' and associated picks deleted.")

        return redirect(url_for('user_area')) # Redirect to refresh the page after POST

    return render_template('user.html', managers=managers, all_matchups=all_matchups)


@app.route('/user/manager/<manager_id>', methods=['GET', 'POST'])
def user_area_manager_picks(manager_id):
    """
    Allows a selected manager to make and manage their picks for each matchup.
    Also includes global matchup management (create, edit, delete) for convenience.
    """
    if not db:
        return "Database not initialized. Please check Firebase configuration.", 500

    # Fetch the selected manager's details
    manager_doc = db.collection(get_collection_path('managers')).document(manager_id).get()
    if not manager_doc.exists:
        return "Manager not found.", 404
    manager = manager_doc.to_dict()

    # Fetch all matchups to display for picking
    matchups_ref = db.collection(get_collection_path('matchups'))
    all_matchups = [doc.to_dict() for doc in matchups_ref.stream()]
    all_matchups.sort(key=lambda x: x.get('team1Name', '').lower())

    # Fetch existing picks for the current manager
    picks_ref = db.collection(get_collection_path('picks')).where('managerId', '==', manager_id)
    existing_picks = {pick.get('matchupId'): pick for pick in [doc.to_dict() for doc in picks_ref.stream()]}

    # Determine available point values for this manager.
    # Points must be unique per manager across all their picks.
    num_matchups = len(all_matchups)
    all_possible_points = set(range(1, num_matchups + 1)) # Points from 1 to total number of matchups
    used_points = {pick['points'] for pick in existing_picks.values()}
    available_points = sorted(list(all_possible_points - used_points))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'save_pick':
            matchup_ids = request.form.getlist('matchup_id')

            for matchup_id in matchup_ids:
                picked_team_id = request.form.get(f'pick_matchup_{matchup_id}')
                points_str = request.form.get(f'points_matchup_{matchup_id}')
                if not matchup_id or not picked_team_id or not points_str:
                    print("Missing pick data for saving.")
                    return redirect(url_for('user_area_manager_picks', manager_id=manager_id))

                try:
                    points = int(points_str)
                except ValueError:
                    print("Invalid points value received.")
                    return redirect(url_for('user_area_manager_picks', manager_id=manager_id))

                # Check if the points value is already used by this manager for a *different* matchup.
                # If the points are for the current matchup being updated, it's allowed.
                existing_pick_for_matchup = existing_picks.get(matchup_id)
                if existing_pick_for_matchup and existing_pick_for_matchup['points'] == points:
                    # Points are the same for this matchup, no conflict.
                    pass
                elif points in used_points:
                    # Points are used by this manager for another matchup.
                    print(f"Points {points} already used by manager {manager['name']} for another pick.")
                    # In a real app, you'd show a user-friendly error message.
                    return redirect(url_for('user_area_manager_picks', manager_id=manager_id))

                # Construct a unique document ID for the pick (managerId_matchupId)
                pick_doc_id = f"{manager_id}_{matchup_id}"
                db.collection(get_collection_path('picks')).document(pick_doc_id).set({
                    'managerId': manager_id,
                    'matchupId': matchup_id,
                    'pickedTeamId': picked_team_id,
                    'points': points
                })
                print(f"Pick saved for manager {manager['name']}, matchup {matchup_id}, team {picked_team_id}, points {points}")
            return redirect(url_for('user_area_manager_picks', manager_id=manager_id))

        elif action == 'create_matchup':
            team1_name = request.form.get('team1_name')
            team2_name = request.form.get('team2_name')
            if team1_name and team2_name and db:
                matchup_id = str(uuid.uuid4())
                team1_id = str(uuid.uuid4())
                team2_id = str(uuid.uuid4())
                db.collection(get_collection_path('matchups')).document(matchup_id).set({
                    'id': matchup_id,
                    'team1Name': team1_name,
                    'team2Name': team2_name,
                    'team1Id': team1_id,
                    'team2Id': team2_id,
                    'winnerTeamId': None
                })
                print(f"Matchup '{team1_name}' vs '{team2_name}' created.")
        elif action == 'edit_matchup':
            matchup_id = request.form.get('matchup_id_edit')
            new_team1_name = request.form.get('new_team1_name')
            new_team2_name = request.form.get('new_team2_name')
            if matchup_id and new_team1_name and new_team2_name and db:
                db.collection(get_collection_path('matchups')).document(matchup_id).update({
                    'team1Name': new_team1_name,
                    'team2Name': new_team2_name
                })
                print(f"Matchup '{matchup_id}' updated.")
        elif action == 'delete_matchup':
            matchup_id = request.form.get('matchup_id_delete')
            if matchup_id and db:
                db.collection(get_collection_path('matchups')).document(matchup_id).delete()
                picks_ref = db.collection(get_collection_path('picks')).where('matchupId', '==', matchup_id)
                for pick_doc in picks_ref.stream():
                    pick_doc.reference.delete()
                print(f"Matchup '{matchup_id}' and associated picks deleted.")
        return redirect(url_for('user_area_manager_picks', manager_id=manager_id))

    return render_template('user_manager_picks.html',
                           manager=manager,
                           all_matchups=all_matchups,
                           existing_picks=existing_picks,
                           available_points=available_points)

@app.route('/admin', methods=['GET', 'POST'])
def admin_area():
    """
    Allows administrators to set the winning team for each matchup and triggers
    a recalculation of all managers' scores.
    """
    if not db:
        return "Database not initialized. Please check Firebase configuration.", 500

    col_path = get_collection_path('matchups')
    print(f"Collection path '{col_path}'")
    matchups_ref = db.collection(col_path)
    all_matchups = [doc.to_dict() for doc in matchups_ref.stream()]
    all_matchups.sort(key=lambda x: x.get('team1Name', '').lower())

    if request.method == 'POST':
            matchup_ids = request.form.getlist('matchup_id')
            # In here the managers score, managers, and matchups will get queried each time which is very expensive and time consuming. Need to fix that.
            for matchup_id in matchup_ids:
                winner_team_id = request.form.get(f'winner_matchup_{matchup_id}')

                if matchup_id and winner_team_id:
                    # Update the winner for the selected matchup
                    db.collection(get_collection_path('matchups')).document(matchup_id).update({
                        'winnerTeamId': winner_team_id
                    })
                               
                    print(f"Winner set for matchup {matchup_id} to {winner_team_id}.")
                    
            # Recalculate the scores
            # Recalculate scores for ALL managers after a winner is set
            managers_ref = db.collection(get_collection_path('managers'))
            all_managers = [doc.to_dict() for doc in managers_ref.stream()]

            for manager in all_managers:
                current_score = 0
                # Fetch all picks for the current manager
                picks_ref = db.collection(get_collection_path('picks')).where('managerId', '==', manager['id'])
                manager_picks = {pick.get('matchupId'): pick for pick in [doc.to_dict() for doc in picks_ref.stream()]}

                for pick_matchup_id, pick_data in manager_picks.items():
                    # Get the matchup details for this specific pick
                    matchup_doc = db.collection(get_collection_path('matchups')).document(pick_matchup_id).get()
                    if matchup_doc.exists:
                        matchup_data = matchup_doc.to_dict()
                        # If the matchup has a winner and the manager's pick matches the winner, add points
                        if matchup_data.get('winnerTeamId') == pick_data.get('pickedTeamId'):
                            current_score += pick_data.get('points', 0)
                
                # Update the manager's total score in Firestore
                db.collection(get_collection_path('managers')).document(manager['id']).update({
                    'totalScore': current_score
                })
            return redirect(url_for('admin_area'))
    return render_template('admin.html', all_matchups=all_matchups)

@app.route('/standings')
def standings_area():
    """
    Displays the current standings, including each manager's total score
    and their maximum possible score.
    """
    if not db:
        return "Database not initialized. Please check Firebase configuration.", 500

    managers_ref = db.collection(get_collection_path('managers'))
    all_managers = [doc.to_dict() for doc in managers_ref.stream()]

    matchups_ref = db.collection(get_collection_path('matchups'))
    all_matchups = {m['id']: m for m in [doc.to_dict() for doc in matchups_ref.stream()]}

    picks_ref = db.collection(get_collection_path('picks'))
    all_picks_raw = [doc.to_dict() for doc in picks_ref.stream()]

    # Organize picks by manager for efficient lookup
    all_manager_picks = {}
    for pick in all_picks_raw:
        manager_id = pick['managerId']
        if manager_id not in all_manager_picks:
            all_manager_picks[manager_id] = {}
        all_manager_picks[manager_id][pick['matchupId']] = pick

    standings_data = []
    for manager in all_managers:
        manager_id = manager['id']
        total_score = manager.get('totalScore', 0)
        max_possible_score = total_score # Start max possible score with current total

        # Calculate maximum possible score
        # This assumes the manager correctly picked winners for all remaining matchups
        manager_picks = all_manager_picks.get(manager_id, {})
        for matchup_id, pick_data in manager_picks.items():
            matchup = all_matchups.get(matchup_id)
            # If the matchup exists and its winner has not been set yet
            if matchup and matchup.get('winnerTeamId') is None:
                # Add the points for this pick to max_possible_score, assuming it's a correct pick
                # We only need to check if they made a pick for this matchup, not if it's the 'right' team,
                # as the max possible score assumes their pick *would* be the winner.
                max_possible_score += pick_data.get('points', 0)

        standings_data.append({
            'name': manager['name'],
            'totalScore': total_score,
            'maxPossibleScore': max_possible_score
        })

    # Sort standings by total score in descending order
    standings_data.sort(key=lambda x: x['totalScore'], reverse=True)

    return render_template('standings.html', standings=standings_data)


@app.route('/projections')
def projections_area():
    """
    Calculates and displays each manager's probability of winning the pick 'em
    based on 10,000 simulations of the remaining matchups.
    """
    if not db:
        return "Database not initialized. Please check Firebase configuration.", 500

    managers_ref = db.collection(get_collection_path('managers'))
    all_managers = [doc.to_dict() for doc in managers_ref.stream()]

    matchups_ref = db.collection(get_collection_path('matchups'))
    all_matchups = {m['id']: m for m in [doc.to_dict() for doc in matchups_ref.stream()]}

    picks_ref = db.collection(get_collection_path('picks'))
    all_picks_raw = [doc.to_dict() for doc in picks_ref.stream()]

    # Organize picks by manager for efficient access during simulations
    all_manager_picks = {}
    for pick in all_picks_raw:
        manager_id = pick['managerId']
        if manager_id not in all_manager_picks:
            all_manager_picks[manager_id] = {}
        all_manager_picks[manager_id][pick['matchupId']] = pick

    # Identify matchups where the winner has not yet been set
    remaining_matchups = [m for m in all_matchups.values() if m.get('winnerTeamId') is None]

    num_simulations = 10000 # Number of simulations to run
    manager_win_counts = {manager['id']: 0 for manager in all_managers} # Track how many times each manager wins a simulation

    for _ in range(num_simulations):
        # Start each simulation with current total scores
        simulated_scores = {manager['id']: manager.get('totalScore', 0) for manager in all_managers}
        
        # Simulate the outcome of each remaining matchup
        for r_matchup in remaining_matchups:
            # Randomly select a winner between the two teams in the matchup
            winner_team_id = random.choice([r_matchup['team1Id'], r_matchup['team2Id']])
            
            # Apply points for this simulated winner to all managers' scores
            for manager in all_managers:
                manager_id = manager['id']
                # Check if this manager has a pick for this specific matchup
                manager_pick = all_manager_picks.get(manager_id, {}).get(r_matchup['id'])
                if manager_pick and manager_pick['pickedTeamId'] == winner_team_id:
                    # If their pick matches the simulated winner, add the assigned points
                    simulated_scores[manager_id] += manager_pick['points']
        
        # After all remaining matchups are simulated for this iteration, find the winner(s)
        if not simulated_scores:
            continue # No managers to simulate for

        # Find the maximum score achieved in this simulation
        max_score = max(simulated_scores.values())
        
        # Identify all managers who achieved the maximum score (handling ties)
        winning_managers_in_sim = [mid for mid, score in simulated_scores.items() if score == max_score]
        
        # Increment win counts for all managers who won this simulation
        for winner_id in winning_managers_in_sim:
            manager_win_counts[winner_id] += 1

    projections = []
    for manager in all_managers:
        manager_id = manager['id']
        # Calculate probability as a percentage
        probability = (manager_win_counts[manager_id] / num_simulations) * 100 if num_simulations > 0 else 0
        projections.append({
            'name': manager['name'],
            'probability': f"{probability:.2f}%" # Format to two decimal places
        })
    
    # Sort projections by probability in descending order
    projections.sort(key=lambda x: float(x['probability'].strip('%')), reverse=True)

    return render_template('projections.html', projections=projections)

# This block ensures the Flask app runs when the script is executed directly.
# In the Canvas environment, the app might be run differently, but this is standard practice.
if __name__ == '__main__':
    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=5000) # Run on 0.0.0.0 to be accessible externally
