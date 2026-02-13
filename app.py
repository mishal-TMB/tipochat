from flask import Flask, render_template, request
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Определяем окружение
is_render = os.environ.get('RENDER') or os.environ.get('IS_RENDER')

if is_render:
    print("🚀 Запуск на Render с WebSocket настройками")
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode='eventlet',
        logger=True,
        engineio_logger=True,
        ping_timeout=60,
        ping_interval=25
    )
else:
    print("💻 Локальный запуск")
    socketio = SocketIO(app, cors_allowed_origins="*", logger=True)


# Модель сообщения
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    text = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.now)
    room = db.Column(db.String(50), default='general')


with app.app_context():
    db.create_all()
    print("✅ База данных создана")


@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('connect')
def handle_connect():
    print(f'✅ Клиент подключился! SID: {request.sid}')
    emit('connected', {'data': 'Connected'})


@socketio.on('disconnect')
def handle_disconnect():
    print(f'❌ Клиент отключился! SID: {request.sid}')


@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data.get('room', 'general')
    join_room(room)
    print(f'👤 {username} присоединился к комнате {room}')

    # Отправляем приветственное сообщение
    emit('new_message', {
        'username': 'System',
        'text': f'{username} присоединился к чату',
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'room': room
    }, room=room)


@socketio.on('get_history')
def handle_get_history(data):
    room = data.get('room', 'general')
    print(f'📜 Запрос истории для комнаты {room}')
    messages = Message.query.filter_by(room=room).order_by(Message.timestamp.desc()).limit(50).all()
    for msg in reversed(messages):
        emit('new_message', {
            'username': msg.username,
            'text': msg.text,
            'timestamp': msg.timestamp.strftime('%H:%M:%S'),
            'room': msg.room
        })


@socketio.on('send_message')
def handle_message(data):
    print(f'💬 Сообщение от {data["username"]} в {data.get("room", "general")}: {data["text"]}')

    new_message = Message(
        username=data['username'],
        text=data['text'],
        room=data.get('room', 'general')
    )
    db.session.add(new_message)
    db.session.commit()

    emit('new_message', {
        'username': data['username'],
        'text': data['text'],
        'timestamp': new_message.timestamp.strftime('%H:%M:%S'),
        'room': data.get('room', 'general')
    }, room=data.get('room', 'general'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)