from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from reportlab.pdfgen import canvas
from flask import send_file
import io
from datetime import datetime
import os
from openai import OpenAI
import uuid

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# OpenRouter API
client = OpenAI(
    api_key='Enter Api Keys',
    base_url='https://openrouter.ai/api/v1'
)

# DB Setup
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class ChatSession(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    title = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(36), db.ForeignKey('chat_session.id'))
    sender = db.Column(db.String(10))
    content = db.Column(db.Text)

with app.app_context():
    db.create_all()

# Routes
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if form_type == 'register':
            if User.query.filter_by(email=email).first():
                return "Email already registered."
            new_user = User(username=username, email=email, password=password)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('index'))

        elif form_type == 'login':
            user = User.query.filter_by(email=email, password=password).first()
            if user:
                session['username'] = user.username
                session['user_id'] = user.id
                return redirect(url_for('home'))
            return "Invalid login. <a href='/'>Try again</a>"

    return render_template('login_signup.html')

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('index'))

    user_id = session['user_id']
    sessions = ChatSession.query.filter_by(user_id=user_id).order_by(ChatSession.created_at.desc()).all()
    current_session_id = request.args.get('session_id')

    if not current_session_id:
        if sessions:
            current_session_id = sessions[0].id
        else:
            new_session = ChatSession(id=str(uuid.uuid4()), user_id=user_id, title="New Chat")
            db.session.add(new_session)
            db.session.commit()
            return redirect(url_for('home', session_id=new_session.id))

    messages = ChatMessage.query.filter_by(session_id=current_session_id).all()
    return render_template('hom.html',
                           username=session['username'],
                           messages=messages,
                           sessions=sessions,
                           current_session_id=current_session_id)

@app.route('/chat', methods=['POST'])
def chat():
    if 'username' not in session:
        return jsonify({'reply': 'You are not logged in.'})

    message = request.form.get('message')
    session_id = request.form.get('session_id')
    user_id = session.get('user_id')

    if not message or not session_id:
        return jsonify({'reply': 'Missing message or session ID.'})

    try:
        db.session.add(ChatMessage(session_id=session_id, sender='user', content=message))
        db.session.commit()

        response = client.chat.completions.create(
            model='deepseek/deepseek-r1-0528:free',
            messages=[
                {"role": "system",
                 "content": "You are a helpful assistant. Respond with formatted markdown, wrap code in triple backticks and use correct language tags like ```java, ```python, etc."},
                {"role": "user", "content": message}
            ]
        )

        bot_reply = response.choices[0].message.content.strip()

        session_obj = ChatSession.query.get(session_id)
        if session_obj.title == "New Chat":
            session_obj.title = message[:30]
            db.session.commit()

        db.session.add(ChatMessage(session_id=session_id, sender='bot', content=bot_reply))
        db.session.commit()

        return jsonify({'reply': bot_reply})
    except Exception as e:
        return jsonify({'reply': f"Error: {str(e)}"})

@app.route('/new_session', methods=['POST'])
def new_session():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    new_chat = ChatSession(id=str(uuid.uuid4()), user_id=session['user_id'], title="New Chat")
    db.session.add(new_chat)
    db.session.commit()
    return redirect(url_for('home', session_id=new_chat.id))

@app.route('/clear_chat/<session_id>', methods=['POST'])
def clear_chat(session_id):
    if 'username' not in session:
        return redirect(url_for('index'))

    ChatMessage.query.filter_by(session_id=session_id).delete()
    db.session.commit()
    return redirect(url_for('home', session_id=session_id))

@app.route('/delete_session/<session_id>', methods=['POST'])
def delete_session(session_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    ChatMessage.query.filter_by(session_id=session_id).delete()
    ChatSession.query.filter_by(id=session_id, user_id=session['user_id']).delete()
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))
@app.route('/export_pdf/<session_id>')
@app.route('/export_pdf/<session_id>')
def export_pdf(session_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    session_obj = ChatSession.query.filter_by(id=session_id, user_id=session['user_id']).first()
    if not session_obj:
        return "Session not found", 404

    messages = ChatMessage.query.filter_by(session_id=session_id).all()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.setTitle(f"ChatSession-{session_id}")

    y = 800
    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, y, f"Chat Export - {session_obj.title or 'Untitled'}")
    y -= 30

    for msg in messages:
        sender = "You" if msg.sender == 'user' else "Bot"
        lines = [f"{sender}: {line}" for line in msg.content.split('\n')]
        for line in lines:
            if y <= 40:
                pdf.showPage()
                y = 800
            pdf.drawString(50, y, line.strip())
            y -= 20

    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="chat_session.pdf", mimetype='application/pdf')


if __name__ == '__main__':
    app.run(debug=True)
