import os
import uuid 
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
import threading

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            print(f"Email error: {e}")

app = Flask(__name__)
app.secret_key = 'eleco-secret-key-2026a'

# --- DATABASE CONFIG (Absolute path for Render & local compatibility) ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'election.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- EMAIL CONFIGURATION ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'ndubuechi8@gmail.com' 
app.config['MAIL_PASSWORD'] = 'kendtyuzntfazetp'     
mail = Mail(app)

# --- DATABASE TABLES ---
class RegisteredVoter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    matric_no = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), nullable=False)
    voter_credential = db.Column(db.String(50), unique=True, nullable=False)
    has_voted = db.Column(db.Boolean, default=False)

# --- UPDATE VOTE RECORD MODEL ---
class VoteRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.String(100), nullable=False)
    candidate = db.Column(db.String(100), nullable=False)

# --- 11 ELECTION POSITIONS & CANDIDATES ---
ELECTION_POSITIONS = {
    "1. President": ["Candidate A (Progressive Party)", "Candidate B (Unity Alliance)"],
    "2. Vice President": ["Candidate C (Progressive Party)", "Candidate D (Unity Alliance)"],
    "3. Director of Social": ["Candidate E", "Candidate F"],
    "4. P.R.O. (Public Relations Officer)": ["Candidate G", "Candidate H"],
    "5. Treasurer": ["Candidate I", "Candidate J"],
    "6. Financial Secretary": ["Candidate K", "Candidate L"],
    "7. Director of Games": ["Candidate M", "Candidate N"],
    "8. General Secretary": ["Candidate O", "Candidate P"],
    "9. Assistant General Secretary": ["Candidate Q", "Candidate R"],
    "10. Provost": ["Candidate S", "Candidate T"],
    "11. Director of Welfare": ["Candidate U", "Candidate V"]
}

class ElectionSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registration_open = db.Column(db.Boolean, default=False)
    voting_open = db.Column(db.Boolean, default=False)

# --- INITIALIZE DATABASE TABLES & DEFAULT SETTINGS ---
with app.app_context():
    db.drop_all()  # Clears the old broken table structure
    db.create_all() # Rebuilds everything with the correct columns for all 11 positions
    if not ElectionSettings.query.first():
        db.session.add(ElectionSettings(registration_open=False, voting_open=False))
        db.session.commit()

# --- MASTER LIST (Add all approved student matric numbers here) ---
VALID_VOTERS = [
    'UG/23/0533',
    'ADUN/24/007',
    'ADUN/24/009'  # Add the exact matric number you are testing here
]
# --- ROUTES ---
@app.route('/')
def home():
    settings = ElectionSettings.query.first()
    return render_template('index.html', settings=settings)

@app.route('/admin/clear-votes', methods=['POST'])
def clear_votes():
    if not session.get('admin_logged_in'): 
        return redirect(url_for('admin_login'))
    
    VoteRecord.query.delete()
    db.session.commit()
    return redirect('/admin')

@app.route('/admin/delete/<int:voter_id>', methods=['POST'])
def delete_voter(voter_id):
    if not session.get('admin_logged_in'): 
        return redirect(url_for('admin_login'))
    
    voter = RegisteredVoter.query.get_or_404(voter_id)
    db.session.delete(voter)
    db.session.commit()
    return redirect('/admin')

@app.route('/register', methods=['POST'])
def register():
    settings = ElectionSettings.query.first()
    if not settings.registration_open:
        return "<h3>❌ Registration is currently CLOSED.</h3><br><a href='/'>Go Home</a>"

    matric_no_input = request.form.get('matric_no').strip().upper()
    email_input = request.form.get('email').strip()
    
    if matric_no_input not in VALID_VOTERS:
        return f"<h3>❌ Error: {matric_no_input} is not on the approved departmental list.</h3><br><a href='/'>Go Back</a>"

    existing_voter = RegisteredVoter.query.filter_by(matric_no=matric_no_input).first()
    if existing_voter:
        return f"<h3>❌ Error: Matric Number {matric_no_input} is already registered!</h3><br><a href='/'>Go Back</a>"

    # Generate unique credential
    credential = "VOTER-" + str(uuid.uuid4())[:8].upper()

    new_voter = RegisteredVoter(
        matric_no=matric_no_input, 
        email=email_input, 
        voter_credential=credential
    )
    db.session.add(new_voter)
    db.session.commit()
    
    # --- SEND EMAIL VIA BACKGROUND THREAD (Prevents 500 Worker Timeout) ---
    try:
        msg = Message("Your ELECO Voting Credential", sender=app.config['MAIL_USERNAME'], recipients=[email_input])
        msg.body = f"Hello {matric_no_input},\n\nYour secret voting credential for the election is: {credential}\n\nPlease keep this safe and do not share it with anyone."
        
        thread = threading.Thread(target=send_async_email, args=(app, msg))
        thread.start()
    except Exception as e:
        return f"<h3>⚠️ Registered successfully, but failed to start email thread: {e}</h3><br><a href='/'>Go Home</a>"
    
    return "<h3>✅ Success! Your unique voting credential has been sent to your email address.</h3><br><a href='/'>Go Home</a>"

@app.route('/vote', methods=['GET', 'POST'])
def vote_login():
    settings = ElectionSettings.query.first()
    if not settings.voting_open:
        return "<h3>❌ Voting is currently CLOSED.</h3><br><a href='/'>Go Home</a>"

    if request.method == 'POST':
        cred = request.form.get('credential').strip().upper()
        voter = RegisteredVoter.query.filter_by(voter_credential=cred).first()
        if not voter: return "<h3>❌ Invalid credential!</h3><br><a href='/vote'>Try Again</a>"
        if voter.has_voted: return "<h3>❌ Error: Already voted!</h3><br><a href='/'>Home</a>"
        session['voting_credential'] = cred
        return redirect('/ballot')
    return render_template('vote_login.html')

@app.route('/ballot', methods=['GET', 'POST'])
def ballot():
    cred = session.get('voting_credential')
    voter = RegisteredVoter.query.filter_by(voter_credential=cred).first()
    if not voter or voter.has_voted: return redirect('/vote')

    if request.method == 'POST':
        selected_candidate = request.form.get('candidate')
        voter.has_voted = True
        db.session.add(VoteRecord(candidate=selected_candidate))
        db.session.commit()
        session.pop('voting_credential', None)
        return "<h3>🎉 Vote successfully cast! Your ballot has been recorded anonymously.</h3><br><a href='/'>Return Home</a>"

    return render_template('ballot.html', candidates=["Candidate A (Progressive Party)", "Candidate B (Unity Alliance)", "Candidate C (Reform Coalition)"])

@app.route('/admin')
def admin_panel():
    if not session.get('admin_logged_in'): 
        return redirect(url_for('admin_login'))
        
    voters = RegisteredVoter.query.all()
    settings = ElectionSettings.query.first()
    
    position_results = {}
    for position, candidates in ELECTION_POSITIONS.items():
        candidates_data = []
        # Calculate total votes cast specifically for this position
        total_pos_votes = sum(VoteRecord.query.filter_by(position=position, candidate=c).count() for c in candidates)
        
        for candidate in candidates:
            count = VoteRecord.query.filter_by(position=position, candidate=candidate).count()
            percentage = (count / total_pos_votes * 100) if total_pos_votes > 0 else 0
            candidates_data.append({
                'name': candidate, 
                'votes': count,
                'percentage': round(percentage, 1)
            })
        position_results[position] = candidates_data

    return render_template(
        'admin.html', 
        voters=voters, 
        settings=settings, 
        position_results=position_results
    )

@app.route('/admin/toggle', methods=['POST'])
def toggle_settings():
    settings = ElectionSettings.query.first()
    settings.registration_open = True if request.form.get('registration') == 'on' else False
    settings.voting_open = True if request.form.get('voting') == 'on' else False
    db.session.commit()
    return redirect('/admin')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST' and request.form.get('password') == 'eleco2026':
        session['admin_logged_in'] = True
        return redirect('/admin')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin/login')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)