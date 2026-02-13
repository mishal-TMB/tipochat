import eventlet
eventlet.monkey_patch()
from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey12345'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# Модель пользователя
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(100))
    avatar = db.Column(db.String(200), default='default.png')
    online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.now)


# Модель сообщения
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    username = db.Column(db.String(50))
    text = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.now)
    room = db.Column(db.String(50), default='general')


# Создание таблиц
with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Хранилище онлайн пользователей
online_users = {}
user_message_times = {}
MESSAGE_LIMIT = 5
MESSAGE_WINDOW = 10


@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('index.html')
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return redirect(url_for('index'))
        return 'Неверный логин или пароль'

    return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Вход в чат</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    margin: 0;
                }
                .login-box {
                    background: white;
                    padding: 40px;
                    border-radius: 20px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    width: 300px;
                }
                h2 {
                    text-align: center;
                    color: #333;
                    margin-bottom: 30px;
                }
                input {
                    width: 100%;
                    padding: 12px;
                    margin-bottom: 15px;
                    border: 2px solid #e0e0e0;
                    border-radius: 10px;
                    box-sizing: border-box;
                }
                button {
                    width: 100%;
                    padding: 12px;
                    background: #4a3f9c;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    cursor: pointer;
                    font-size: 16px;
                }
                button:hover {
                    background: #5a4fbc;
                }
                .links {
                    text-align: center;
                    margin-top: 20px;
                }
                .links a {
                    color: #4a3f9c;
                    text-decoration: none;
                }
            </style>
        </head>
        <body>
            <div class="login-box">
                <h2>🔐 Вход в чат</h2>
                <form method="post">
                    <input type="text" name="username" placeholder="Логин" required>
                    <input type="password" name="password" placeholder="Пароль" required>
                    <button type="submit">Войти</button>
                </form>
                <div class="links">
                    <a href="/register">Нет аккаунта? Регистрация</a>
                </div>
            </div>
        </body>
        </html>
    '''


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if User.query.filter_by(username=username).first():
            return 'Такой пользователь уже есть'

        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('index'))

    return '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Регистрация</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    margin: 0;
                }
                .register-box {
                    background: white;
                    padding: 40px;
                    border-radius: 20px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    width: 300px;
                }
                h2 {
                    text-align: center;
                    color: #333;
                    margin-bottom: 30px;
                }
                input {
                    width: 100%;
                    padding: 12px;
                    margin-bottom: 15px;
                    border: 2px solid #e0e0e0;
                    border-radius: 10px;
                    box-sizing: border-box;
                }
                button {
                    width: 100%;
                    padding: 12px;
                    background: #4a3f9c;
                    color: white;
                    border: none;
                    border-radius: 10px;
                    cursor: pointer;
                    font-size: 16px;
                }
                button:hover {
                    background: #5a4fbc;
                }
                .links {
                    text-align: center;
                    margin-top: 20px;
                }
                .links a {
                    color: #4a3f9c;
                    text-decoration: none;
                }
            </style>
        </head>
        <body>
            <div class="register-box">
                <h2>📝 Регистрация</h2>
                <form method="post">
                    <input type="text" name="username" placeholder="Придумайте логин" required>
                    <input type="password" name="password" placeholder="Придумайте пароль" required>
                    <button type="submit">Зарегистрироваться</button>
                </form>
                <div class="links">
                    <a href="/login">Уже есть аккаунт? Войти</a>
                </div>
            </div>
        </body>
        </html>
    '''


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ---------- SocketIO ----------
socketio = SocketIO(app, cors_allowed_origins="*", logger=True)


def get_online_users(room):
    users = []
    for sid, data in online_users.items():
        if data['room'] == room:
            users.append({
                'username': data['username'],
                'avatar': data.get('avatar', 'default.png')
            })
    return users


@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        print(f'✅ {current_user.username} подключился')

        current_user.online = True
        current_user.last_seen = datetime.now()
        db.session.commit()

        online_users[request.sid] = {
            'user_id': current_user.id,
            'username': current_user.username,
            'room': 'general',
            'avatar': current_user.avatar
        }

        emit('online_users', get_online_users('general'), broadcast=True)


@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in online_users:
        user_data = online_users[request.sid]
        print(f'❌ {user_data["username"]} отключился')

        room = user_data['room']
        del online_users[request.sid]

        user = User.query.get(user_data['user_id'])
        if user:
            user.online = False
            user.last_seen = datetime.now()
            db.session.commit()

        emit('online_users', get_online_users(room), room=room)


@socketio.on('join')
def on_join(data):
    if not current_user.is_authenticated:
        return

    room = data.get('room', 'general')

    if request.sid in online_users:
        online_users[request.sid]['room'] = room
    else:
        online_users[request.sid] = {
            'user_id': current_user.id,
            'username': current_user.username,
            'room': room,
            'avatar': current_user.avatar
        }

    join_room(room)
    print(f'👤 {current_user.username} присоединился к {room}')

    # История сообщений
    messages = Message.query.filter_by(room=room).order_by(Message.timestamp.desc()).limit(50).all()
    for msg in reversed(messages):
        emit('new_message', {
            'username': msg.username,
            'text': msg.text,
            'timestamp': msg.timestamp.strftime('%H:%M:%S'),
            'room': msg.room
        })

    # Список онлайн
    emit('online_users', get_online_users(room), room=room)

    # Приветствие
    emit('new_message', {
        'username': 'Система',
        'text': f'{current_user.username} присоединился к чату',
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'room': room
    }, room=room)


@socketio.on('send_message')
def handle_message(data):
    if not current_user.is_authenticated:
        return

    # Антиспам
    now = datetime.now()
    if request.sid in user_message_times:
        times = [t for t in user_message_times[request.sid]
                 if now - t < timedelta(seconds=MESSAGE_WINDOW)]

        if len(times) >= MESSAGE_LIMIT:
            emit('error_message', {'text': 'Слишком много сообщений! Подожди 10 секунд.'})
            return

        times.append(now)
        user_message_times[request.sid] = times
    else:
        user_message_times[request.sid] = [now]

    # Проверка на спам-слова
    bad_words = ['казино', 'casino', 'слоты', 'вулкан', 'игровые автоматы', 'порно', 'секс', 'xxx']
    text_lower = data['text'].lower()
    for word in bad_words:
        if word in text_lower:
            print(f"🚫 Спам от {current_user.username}: {data['text']}")
            emit('error_message', {'text': 'Сообщение содержит запрещенные слова!'})
            return

    # Сохраняем в БД
    new_message = Message(
        user_id=current_user.id,
        username=current_user.username,
        text=data['text'][:500],
        room=data.get('room', 'general')
    )
    db.session.add(new_message)
    db.session.commit()

    # Отправляем всем
    message_data = {
        'username': current_user.username,
        'text': data['text'],
        'timestamp': new_message.timestamp.strftime('%H:%M:%S'),
        'room': data.get('room', 'general')
    }

    # Если есть картинка, добавляем
    if 'image' in data:
        message_data['image'] = data['image']

    emit('new_message', message_data, room=data.get('room', 'general'))


@socketio.on('get_history')
def handle_get_history(data):
    room = data.get('room', 'general')
    messages = Message.query.filter_by(room=room).order_by(Message.timestamp.desc()).limit(50).all()

    for msg in reversed(messages):
        emit('new_message', {
            'username': msg.username,
            'text': msg.text,
            'timestamp': msg.timestamp.strftime('%H:%M:%S'),
            'room': msg.room
        })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)