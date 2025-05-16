from flask import Flask, render_template, request, redirect, url_for, session
import os
import sqlite3
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import logging
import requests  # Добавим requests
from funcs import (allowed_file, get_users, get_profile, get_reviews, edit_profile_data, get_user_by_username, add_review, get_steam_games)

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)ngbf

# Константы
DATABASE = 'baze.db'
UPLOAD_FOLDER = 'static/avatars'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB



def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']
        age = request.form['age']
        description = request.form['description']
        game_type = request.form['game_type']
        avatar = request.files['avatar']
        steam_profile_url = request.form.get('steam_profile_url', '')

        if avatar and allowed_file(avatar.filename):
            filename = secure_filename(avatar.filename)
            avatar_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                avatar.save(avatar_path)
                logger.info(f"Аватар сохранен: {avatar_path}")
            except Exception as e:
                logger.error(f"Ошибка сохранения аватара: {e}")
                return render_template('register.html', message=f"Ошибка сохранения аватара: {e}")
        else:
            return render_template('register.html', message="Недопустимый тип файла.")

        db = get_db_connection()
        cursor = db.cursor()
        try:
            cursor.execute("""
                SELECT * FROM users WHERE username=?
            """, (username,))
            if cursor.fetchone():
                return render_template('register.html', message='Пользователь с таким именем уже существует')
            hashed_password = generate_password_hash(password)
            cursor.execute("""
                INSERT INTO users (name, username, password, age, description, game_type, avatar, steam_profile_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, username, hashed_password, age, description, game_type, avatar_path, steam_profile_url))
            db.commit()
            logger.info(f"Новый пользователь зарегистрирован: {username}")
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при добавлении данных в БД: {e}")
            return render_template('register.html', message=f"Ошибка при добавлении данных в БД: {e}")
        finally:
            db.close()

        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT password FROM users WHERE username=?", (username,))
        user = cursor.fetchone()
        db.close()

        if user and check_password_hash(user['password'], password):
            session['username'] = username
            return redirect(url_for('index'))
        else:
            return render_template('login.html', message="Неверное имя пользователя или пароль.")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))


@app.route('/')
def index():
    sort_by = request.args.get('sort', 'name')
    age_filter = request.args.get('age', type=int)
    search_query = request.args.get('search')
    game_type_filter = request.args.get('game_type')
    platform_filter = request.args.get('platform')
    region_filter = request.args.get('region')
    users = get_users(sort_by, age_filter, search_query, game_type_filter, platform_filter, region_filter)
    return render_template('index.html', users=users, age_filter=age_filter, search_query=search_query,
                           game_type_filter=game_type_filter, platform_filter=platform_filter,
                           region_filter=region_filter,
                           logged_in=session.get('username'))


@app.route('/profile/<username>')
def profile(username):
    user = get_user_by_username(username)
    if not user:
        return "Пользователь не найден", 404
    user_id = user['id']
    reviews = get_reviews(user_id)
    steam_games = []
    if user['steam_profile_url']:
        steam_id = user['steam_profile_url'].split('/')[-1]
        steam_games = get_steam_games(steam_id)

    return render_template('profile.html', user=user, reviews=reviews, logged_in=session.get('username'),
                           steam_games=steam_games)


@app.route('/add_review/<user_id>', methods=['POST'])
def add_review_route(user_id):
    if 'username' not in session:
        logger.warning("Пользователь не авторизован")
        return redirect(url_for('login'))

    try:
        user_id = int(user_id)
    except ValueError:
        logger.error(f"Неверный user_id: {user_id}")
        return "Неверный user_id", 400

    review_text = request.form['review']
    reviewer_username = session['username']
    logger.debug(
        f"add_review: user_id={user_id}, review_text={review_text}, reviewer_username={reviewer_username}")
    add_review(user_id, review_text, reviewer_username)
    profile = get_profile(user_id)
    if profile:
        return redirect(url_for('profile', username=profile['username']))
    else:
        logger.error(f"Пользователь с user_id {user_id} не найден")
        return "Пользователь не найден", 404

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    user = get_user_by_username(username)

    if request.method == 'POST':
        user_id = user['id']
        new_age = request.form['age']
        new_description = request.form['description']
        new_game_type = request.form['game_type']
        steam_profile_url = request.form.get('steam_profile_url', '')
        steam_games = []
        steam_games_str = ""
        if steam_profile_url:
            steam_id = steam_profile_url.split('/')[-1]
            steam_games = get_steam_games(steam_id)
            steam_games_str = ",".join([str(game['appid']) for game in steam_games])

        db = get_db_connection()
        cursor = db.cursor()
        try:
            cursor.execute("UPDATE users SET age=?, description=?, game_type=?, steam_profile_url=?, steam_games=? WHERE id=?",
                           (new_age, new_description, new_game_type, steam_profile_url, steam_games_str, user_id))
            db.commit()
            return redirect(url_for('profile', username=username))
        except Exception as e:
            db.rollback()
            return render_template('edit_profile.html', user=user, message="Ошибка при обновлении профиля.",
                                   logged_in=session.get('username'))
        finally:
            db.close()

    return render_template('edit_profile.html', user=user, logged_in=session.get('username'))


if __name__ == '__main__':
    app.run(debug=True)