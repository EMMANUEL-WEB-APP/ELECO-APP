import os
import uuid 
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message

app = Flask(__name__)

# --- DATABASE CONFIG (Absolute path for Render & local compatibility) ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'election.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- AUTOMATIC TABLE CREATION ON STARTUP (Required for Render/Gunicorn) ---
with app.app_context():
    db.create_all()
    if not ElectionSettings.query.first() if 'ElectionSettings' in globals() else True:
        pass # handled below safely or handled after models load

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

class VoteRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    candidate = db.Column(db.String(100), nullable=False)

class ElectionSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    registration_open = db.Column(db.Boolean, default=False)
    voting_open = db.Column(db.Boolean, default=False)

# --- INITIALIZE DATABASE TABLES & DEFAULT SETTINGS ---
with app.app_context():
    db.create_all()
    if not ElectionSettings.query.first():
        db.session.add(ElectionSettings(registration_open=False, voting_open=False))
        db.session.commit()

# --- MASTER LIST ---
VALID_VOTERS = ['ADUN/24/007', 'ADUN/24/008', 'ADUN/24/009', 'ADUN/24/010', 'ADUN/24/011', 'ADUN/24/012']

# --- ROUTES ---
@app.route('/')
def home():
    settings = ElectionSettings.query.first()
    return render_template('index.html', settings=settings)

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
    
    # Send the voting credential via Email
    try:
        msg = Message("Your ELECO Voting Credential", sender=app.config['MAIL_USERNAME'], recipients=[email_input])
        msg.body = f"Hello {matric_no_input},\n\nYour secret voting credential for the election is: {credential}\n\nPlease keep this safe and do not share it with anyone."
        mail.send(msg)
    except Exception as e:
        return f"<h3>⚠️ Registered successfully, but failed to send email: {e}</h3><br><a href='/'>Go Home</a>"
    
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
    all_votes = VoteRecord.query.all()
    total_votes = len(all_votes)
    settings = ElectionSettings.query.first()
    
    candidates_list = [
        "Candidate A (Progressive Party)", 
        "Candidate B (Unity Alliance)", 
        "Candidate C (Reform Coalition)"
    ]
    
    candidate_results = []
    max_votes = -1
    winner = "No votes cast yet"
    
    for candidate in candidates_list:
        count = VoteRecord.query.filter_by(candidate=candidate).count()
        percentage = (count / total_votes * 100) if total_votes > 0 else 0
        
        candidate_results.append({
            'name': candidate,
            'votes': count,
            'percentage': round(percentage, 1)
        })
        
        if count > max_votes:
            max_votes = count
            winner = candidate

    return render_template(
        'admin.html', 
        voters=voters, 
        total_votes=total_votes, 
        settings=settings, 
        results=candidate_results,
        winner=winner if total_votes > 0 else "Election in progress"
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
