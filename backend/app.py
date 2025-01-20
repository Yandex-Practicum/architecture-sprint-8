import json
from flask import Flask, jsonify, request
from flask_cors import CORS
import jwt
from jwt.exceptions import InvalidTokenError
from functools import wraps

# Создание Flask приложения
app = Flask(__name__)
CORS(app)

SECRET_KEY = "oNwoLQdvJAvRcL89SydqCWCe5ry1jMgq"

# Декоратор для проверки роли пользователя
def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            token = request.headers.get("Authorization")
            if not token:
                return jsonify({"error": "Missing token"}), 401

            token = token.split(" ")[1]  # Убираем "Bearer " из токена

            try:
                # Декодинг токен с использованием секретного ключа
                decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["S256"])
                user_roles = decoded_token.get("realm_access", {}).get("roles", [])
                if role not in user_roles:
                    return jsonify({"error": "Insufficient permissions"}), 403
            except InvalidTokenError:
                return jsonify({"error": "Invalid token"}), 401

            return f(*args, **kwargs)

        return wrapper
    return decorator

# Эндпоинт для получения отчётов
@app.route('/reports', methods=['GET'])
@role_required('prothetic_user')  # Требуется роль prothetic_user
def get_reports():
    # Генерация произвольных данных отчета
    report_data = {
        "report_id": 1,
        "name": "Prothetic User Report",
        "data": [ {"item": "item1", "value": 100}, {"item": "item2", "value": 200}]
    }
    return jsonify(report_data)

# @app.route('/reports/test', methods=['GET'])
# # @role_required('prothetic_user')  # Требуется роль prothetic_user
# def get_reports_test():
#     # Генерация произвольных данных отчета
#     report_data_test = {
#         "report_id": 1,
#         "name": "Prothetic User Report",
#         "data": [ {"item": "item1", "value": 100}, {"item": "item2", "value": 200}]
#     }
#     return jsonify(report_data_test)

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=8000)
