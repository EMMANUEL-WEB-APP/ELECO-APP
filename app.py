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

# --- DATABASE CONFIG ---
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

def get_settings():
    settings = ElectionSettings.query.first()
    if not settings:
        settings = ElectionSettings(registration_open=False, voting_open=False)
        db.session.add(settings)
        db.session.commit()
    return settings

with app.app_context():
    db.create_all()
    # Auto-fix outdated vote_record table schema if missing 'position' column
    try:
        inspector = db.inspect(db.engine)
        if "vote_record" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("vote_record")]
            if "position" not in columns:
                VoteRecord.__table__.drop(db.engine)
                db.create_all()
    except Exception as e:
        print(f"Schema check note: {e}")
    get_settings()
    
VALID_VOTERS = [
    'UG/23/0533',
    'ADUN/24/007',
    'ADUN/24/009'
]

# --- ROUTES ---
@app.route('/')
def home():
    settings = get_settings()
    return render_template('index.html', settings=settings)

@app.route('/admin/clear-votes', methods=['POST'])
def clear_votes():
    if not session.get('admin_logged_in'): 
        return redirect(url_for('admin_login'))
    
    VoteRecord.query.delete()
    RegisteredVoter.query.update({RegisteredVoter.has_voted: False})
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete/<int:voter_id>', methods=['POST'])
def delete_voter(voter_id):
    if not session.get('admin_logged_in'): 
        return redirect(url_for('admin_login'))
    
    voter = RegisteredVoter.query.get_or_404(voter_id)
    db.session.delete(voter)
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/register', methods=['POST'])
def register():
    settings = get_settings()
    if not settings.registration_open:
        return "<h3>❌ Registration is currently CLOSED.</h3><br><a href='/'>Go Home</a>"

    matric_no_input = request.form.get('matric_no')
    if not matric_no_input:
        return "<h3>❌ Error: Matric number cannot be empty.</h3><br><a href='/'>Go Back</a>"
        
    matric_no_input = matric_no_input.strip().upper()
    email_input = request.form.get('email', '').strip()
    
    if matric_no_input not in VALID_VOTERS:
        return f"<h3>❌ Error: {matric_no_input} is not on the approved departmental list.</h3><br><a href='/'>Go Back</a>"

    existing_voter = RegisteredVoter.query.filter_by(matric_no=matric_no_input).first()
    if existing_voter:
        return f"<h3>❌ Error: Matric Number {matric_no_input} is already registered!</h3><br><a href='/'>Go Back</a>"

    credential = "VOTER-" + str(uuid.uuid4())[:8].upper()

    new_voter = RegisteredVoter(
        matric_no=matric_no_input, 
        email=email_input, 
        voter_credential=credential
    )
    db.session.add(new_voter)
    db.session.commit()
    
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
    settings = get_settings()
    if not settings.voting_open:
        return "<h3>❌ Voting is currently CLOSED.</h3><br><a href='/'>Go Home</a>"

    if request.method == 'POST':
        cred = request.form.get('credential')
        if not cred:
            return "<h3>❌ Credential cannot be empty!</h3><br><a href='/vote'>Try Again</a>"
            
        cred = cred.strip().upper()
        voter = RegisteredVoter.query.filter_by(voter_credential=cred).first()
        if not voter: return "<h3>❌ Invalid credential!</h3><br><a href='/vote'>Try Again</a>"
        if voter.has_voted: return "<h3>❌ Error: Already voted!</h3><br><a href='/'>Home</a>"
        session['voting_credential'] = cred
        return redirect('/ballot')
    return render_template('vote_login.html')

@app.route('/ballot', methods=['GET', 'POST'])
def ballot():
    try:
        cred = session.get('voting_credential')
        if not cred:
            return redirect('/vote')
            
        voter = RegisteredVoter.query.filter_by(voter_credential=cred).first()
        if not voter or voter.has_voted: 
            return redirect('/vote')

        if request.method == 'POST':
            for position in ELECTION_POSITIONS.keys():
                selected_candidate = request.form.get(position)
                if selected_candidate:
                    db.session.add(VoteRecord(position=position, candidate=selected_candidate))
            
            voter.has_voted = True
            db.session.commit()
            session.pop('voting_credential', None)
            return "<h3>🎉 All votes successfully cast! Your ballot has been recorded anonymously.</h3><br><a href='/'>Return Home</a>"

        return render_template('ballot.html', positions=ELECTION_POSITIONS)
    except Exception as e:
        return f"<h3>⚠️ Ballot Error: {str(e)}</h3><br><a href='/vote'>Try Again</a>"

@app.route('/admin')
def admin_panel():
    if not session.get('admin_logged_in'): 
        return redirect(url_for('admin_login'))
        
    voters = RegisteredVoter.query.all()
    settings = get_settings()
    
    position_results = {}
    for position, candidates in ELECTION_POSITIONS.items():
        candidates_data = []
        try:
            total_pos_votes = sum(db.session.query(VoteRecord).filter_by(position=position, candidate=c).count() for c in candidates)
        except Exception:
            total_pos_votes = 0
        
        for candidate in candidates:
            try:
                count = db.session.query(VoteRecord).filter_by(position=position, candidate=candidate).count()
            except Exception:
                count = 0
                
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
def admin_toggle():
    if not session.get('admin_logged_in'): 
        return redirect(url_for('admin_login'))
    
    settings = get_settings()
    settings.registration_open = True if request.form.get('registration') else False
    settings.voting_open = True if request.form.get('voting') else False
    db.session.commit()
    return redirect(url_for('admin_panel'))

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