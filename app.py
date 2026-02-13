from flask import Flask, render_template, request
from flask_socketio import SocketIO, send, emit
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")


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

# Словарь для хранения комнат пользователей (в памяти, но можно и в БД)
user_rooms = {}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/room/<room_name>')
def room(room_name):
    return render_template('index.html', room=room_name)


# Получить историю сообщений для комнаты
@socketio.on('get_history')
def get_history(data):
    room = data.get('room', 'general')
    messages = Message.query.filter_by(room=room).order_by(Message.timestamp.desc()).limit(50).all()
    messages = reversed(messages)  # Переворачиваем, чтобы первые были сверху

    for msg in messages:
        emit('new_message', {
            'username': msg.username,
            'text': msg.text,
            'timestamp': msg.timestamp.strftime('%H:%M:%S'),
            'room': msg.room
        })


@socketio.on('send_message')
def handle_message(data):
    print(f"Сообщение: {data}")

    # Сохраняем в базу данных
    new_message = Message(
        username=data['username'],
        text=data['text'],
        room=data.get('room', 'general')
    )
    db.session.add(new_message)
    db.session.commit()

    # Отправляем всем в этой комнате
    message_data = {
        'username': data['username'],
        'text': data['text'],
        'timestamp': new_message.timestamp.strftime('%H:%M:%S'),
        'room': data.get('room', 'general')
    }

    # Отправляем в конкретную комнату
    socketio.emit('new_message', message_data, room=data.get('room', 'general'))


# Присоединение к комнате
@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data.get('room', 'general')

    # Запоминаем комнату пользователя
    user_rooms[request.sid] = room

    # Присоединяем сокет к комнате
    join_room(room)

    # Уведомляем остальных
    socketio.emit('new_message', {
        'username': 'Система',
        'text': f'{username} присоединился к чату',
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'room': room
    }, room=room)


# Выход из комнаты
@socketio.on('leave')
def on_leave(data):
    username = data['username']
    room = user_rooms.get(request.sid, 'general')

    leave_room(room)

    socketio.emit('new_message', {
        'username': 'Система',
        'text': f'{username} покинул чат',
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'room': room
    }, room=room)


@socketio.on('connect')
def handle_connect():
    print('Клиент подключился')


@socketio.on('disconnect')
def handle_disconnect():
    # Очищаем комнату пользователя при отключении
    if request.sid in user_rooms:
        del user_rooms[request.sid]
    print('Клиент отключился')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)