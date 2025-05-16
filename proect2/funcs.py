import os
import logging
import sqlite3
from werkzeug.utils import secure_filename
import requests
from flask import Flask

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Константы
DATABASE = 'baze.db'
UPLOAD_FOLDER = 'static/avatars'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp3', 'wav'}
STEAM_API_KEY = "8337B627A76CD0F2447464B6F59CFCE4" # Замените на ваш API Key

# Создаем папку для аватарок, если она не существует
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)



def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_users(sort_by='name', age_filter=None, search_query=None, game_type_filter=None, platform_filter=None, region_filter=None):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Возвращает результаты в виде словарей
    cursor = conn.cursor()
    query = "SELECT id, name, age, game_type, avatar, username, steam_profile_url, steam_games FROM users"  # Добавляем username
    parameters = []
    conditions = []

    if age_filter:
        conditions.append("age >= ?")
        parameters.append(age_filter)

    if search_query:
        conditions.append("name LIKE ?")
        parameters.append(f"%{search_query}%")

    if game_type_filter:
        conditions.append("game_type = ?")
        parameters.append(game_type_filter)

    # Добавляем фильтры по платформе и региону
    if platform_filter:
        conditions.append("platform = ?")
        parameters.append(platform_filter)

    if region_filter:
        conditions.append("region = ?")
        parameters.append(region_filter)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += f" ORDER BY {sort_by}"
    cursor.execute(query, parameters)
    users = cursor.fetchall()
    conn.close()
    return users

def get_user_by_username(username):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Возвращает результаты в виде словарей
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, age, game_type, avatar, username, description, steam_profile_url, steam_games FROM users WHERE username = ?",
                   (username,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_profile(user_id):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Возвращает результаты в виде словарей
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, age, game_type, avatar, username, description, steam_profile_url, steam_games FROM users WHERE id = ?",
                   (user_id,))
    profile = cursor.fetchone()
    conn.close()
    return profile

def get_reviews(user_id):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Возвращает результаты в виде словарей
    cursor = conn.cursor()
    cursor.execute(
        "SELECT review_text, created_at, user_id, reviewer_username FROM reviews WHERE user_id = ?", (user_id,))
    reviews = cursor.fetchall()
    conn.close()
    return reviews

def add_review(user_id, review_text, reviewer_username):
    conn = sqlite3.connect('baze.db')
    conn.row_factory = sqlite3.Row  # Возвращает результаты в виде словарей
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO reviews (user_id, review_text, reviewer_username) VALUES (?, ?, ?)",
                       (user_id, review_text, reviewer_username))
        conn.commit()
    except Exception as e:
        logger.error(f"Ошибка при добавлении отзыва: {e}")
        conn.rollback()
    finally:
        conn.close()

def edit_profile_data(user_id, new_age, new_description, new_game_type, steam_profile_url, steam_games_str):
    conn = sqlite3.connect('baze.db')
    conn.row_factory = sqlite3.Row  # Возвращает результаты в виде словарей
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET age=?, description=?, game_type=?, steam_profile_url=?, steam_games=? WHERE id=?",
                       (new_age, new_description, new_game_type, steam_profile_url, steam_games_str, user_id))
        conn.commit()
        return True  # Успех
    except Exception as e:
        logger.error(f"Ошибка при обновлении профиля: {e}")
        conn.rollback()
        return False  # Ошибка
    finally:
        conn.close()

# Функция для получения списка игр пользователя из Steam
def get_steam_games(steam_id):
    """
    Получает список игр пользователя Steam по его SteamID.
    """
    if not steam_id or not STEAM_API_KEY:
        return []

    url = f"http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key={STEAM_API_KEY}&steamid={steam_id}&include_appinfo=1&format=json"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Проверка на ошибки HTTP
        data = response.json()
        if 'response' in data and 'games' in data['response']:
            games = data['response']['games']
            return games  # Возвращаем список игр
        else:
            return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к Steam API: {e}")
        return []

