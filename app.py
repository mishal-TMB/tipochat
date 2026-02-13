from flask import Flask, render_template, request
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import eventlet

eventlet.monkey_patch()  # Это важно для WebSocket на Render!

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='eventlet',  # Принудительно используем eventlet
    logger=True,  # Включим логи для отладки
    engineio_logger=True
)


# Модель сообщения
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    text = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.now)
    room = db.Column(db.String(50), default='general')


# Создаем базу данных
with app.app_context():
    db.create_all()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/room/<room_name>')
def room(room_name):
    return render_template('index.html', room=room_name)


@socketio.on('connect')
def handle_connect():
    print('Клиент подключился! SID:', request.sid)
    emit('connected', {'data': 'Connected'})


@socketio.on('disconnect')
def handle_disconnect():
    print('Клиент отключился! SID:', request.sid)


@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data.get('room', 'general')
    join_room(room)
    print(f'{username} присоединился к комнате {room}')

    # Отправляем историю сообщений
    messages = Message.query.filter_by(room=room).order_by(Message.timestamp.desc()).limit(50).all()
    for msg in reversed(messages):
        emit('new_message', {
            'username': msg.username,
            'text': msg.text,
            'timestamp': msg.timestamp.strftime('%H:%M:%S'),
            'room': msg.room
        }, room=request.sid)

    # Уведомление о новом пользователе
    emit('new_message', {
        'username': 'System',
        'text': f'{username} присоединился к чату',
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'room': room
    }, room=room)


@socketio.on('send_message')
def handle_message(data):
    print(f"Сообщение от {data['username']} в комнате {data.get('room', 'general')}: {data['text']}")

    # Сохраняем в базу
    new_message = Message(
        username=data['username'],
        text=data['text'],
        room=data.get('room', 'general')
    )
    db.session.add(new_message)
    db.session.commit()

    # Отправляем всем в комнате
    emit('new_message', {
        'username': data['username'],
        'text': data['text'],
        'timestamp': new_message.timestamp.strftime('%H:%M:%S'),
        'room': data.get('room', 'general')
    }, room=data.get('room', 'general'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)