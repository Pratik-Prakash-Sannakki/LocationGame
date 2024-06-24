from flask import Flask, request, jsonify, g
from flask_cors import CORS
from rejson import Client, Path
from datetime import datetime, timedelta
import pytz
import os
import random
import http
import jwt
from flask_bcrypt import Bcrypt
from flask_api import status

# Redis client setup
redis_host = os.getenv('REDIS_HOST', 'localhost')  # Default to 'localhost' if 'REDIS_HOST' is not set
rj = Client(host=redis_host, port=6379, decode_responses=True)
push_to_redis = True
rj_host = 'localhost'

# Hard-coded time zone. Required for correct ObjectId comparisons!
local_zone = pytz.timezone('US/Eastern')

app = Flask(__name__)
CORS(app)
bcrypt = Bcrypt(app)

def tryexcept(requesto, key, default):
    """Helper function to handle missing keys in request JSON."""
    try:
        return requesto.json[key]
    except:
        return default

@app.before_request
def set_env_var():
    if 'secret_key' not in g:
        g.secret_key = os.environ.get("SECRET_KEY", "my_precious_1869")
    if 'bcrypt_log_rounds' not in g:
        g.bcrypt_log_rounds = int(os.environ.get("BCRYPT_LOG_ROUNDS", 13))
    if 'access_token_expiration' not in g:
        g.access_token_expiration = int(os.environ.get("ACCESS_TOKEN_EXPIRATION", 900))
    if 'refresh_token_expiration' not in g:
        g.refresh_token_expiration = int(os.environ.get("REFRESH_TOKEN_EXPIRATION", 2592000))
    if 'users' not in g:
        users = os.environ.get("USERS", 'user1,user2,user3')
        g.users = users.split(',')
    if 'passwords' not in g:
        passwords = os.environ.get("PASSWORDS", 'Tesla,Clippy,Blue')
        g.passwords = passwords.split(',')
        g.password_hashes = [bcrypt.generate_password_hash(p).decode('utf-8') for p in g.passwords]
        g.userids = list(range(len(g.users)))

@app.route("/")
def home():
    """Documentation endpoint."""
    if rj_host == 'localhost':
        return """twtr backend endpoints:<br />
            <br />
            From collections:<br/>
            /enqueue-get<br />
            /collections-from-redis-cache<br />
            /purge-redis-cache<br />
            /set-location<br />
            /get-location/<user_id>"""
    else:
        return """Remote mock:<br />
            <br />
            From collections:<br/>
            /users<br />
            /collections-from-redis-cache<br />
            /purge-redis-cache<br />
            /set-location<br />
            /get-location/<user_id>"""

@app.route('/collections-from-redis-cache')
def collections_from_redis_cache():
    """Returns all items from Redis."""
    data = dict()
    try:
        for key in rj.keys('*'):
            data[key] = rj.jsonget(key, Path.rootPath())
    except:
        print("*** redisjson is dead!")
        return jsonify({"Queue inaccessible.": http.HTTPStatus.INTERNAL_SERVER_ERROR})
    return jsonify(data)

@app.route('/purge-redis-cache')
def purge_redis_cache():
    """Purges all items from Redis."""
    data = dict()
    try:
        for key in rj.keys('*'):
            data[key] = rj.jsonget(key, Path.rootPath())
            rj.delete(key)
    except:
        print("*** purge_redis_cache(): redisjson is dead!")
    return jsonify(data)

@app.route("/enqueue", methods=["POST"])
def enqueue():
    """Enqueues data into Redis."""
    key = tryexcept(request, 'key', None)
    path = tryexcept(request, 'path', None)
    record = tryexcept(request, 'record', None)

    if push_to_redis:
        if rjjsonsetwrapper(key, path, record):
            print("Enqueued.")
            return jsonify("Enqueued.", http.HTTPStatus.OK)
        else:
            print("Not enqueued!")
            return jsonify("Not enqueued.", http.HTTPStatus.INTERNAL_SERVER_ERROR)
    else:
        print("Dropped.")
        return jsonify("Dropped.", http.HTTPStatus.OK)

@app.route("/enqueue-get", methods=["GET"])
def enqueue_get():
    """Enqueues a test record into Redis."""
    key = str(random.randint(1000000000, 2000000000))
    path = "."
    record = "no_mr_bond_I_want_you_to_die"

    if push_to_redis:
        rjjsonsetwrapper(key, path, record)
        print("Enqueued.")
        return jsonify("Enqueued.", http.HTTPStatus.OK)
    else:
        print("Dropped.")
        return jsonify("Dropped.", http.HTTPStatus.OK)

@app.route("/set-location", methods=["POST"])
def set_location():
    """Sets user location in Redis."""
    user_id = tryexcept(request, 'user_id', None)
    latitude = tryexcept(request, 'latitude', None)
    longitude = tryexcept(request, 'longitude', None)
    heading = tryexcept(request, 'heading', None)
    speed = tryexcept(request, 'speed', None)

    if user_id is None or latitude is None or longitude is None:
        return jsonify("Missing data.", http.HTTPStatus.BAD_REQUEST)

    key = f"user:{user_id}:location"
    record = {
        "latitude": latitude,
        "longitude": longitude,
        "heading": heading,
        "speed": speed
    }

    if push_to_redis:
        if rjjsonsetwrapper(key, Path.rootPath(), record):
            print(f"Location for user {user_id} enqueued.")
            return jsonify(f"Location for user {user_id} enqueued.", http.HTTPStatus.OK)
        else:
            print(f"Location for user {user_id} not enqueued!")
            return jsonify(f"Location for user {user_id} not enqueued.", http.HTTPStatus.INTERNAL_SERVER_ERROR)
    else:
        print("Dropped.")
        return jsonify("Dropped.", http.HTTPStatus.OK)

@app.route("/get-location/<user_id>", methods=["GET"])
def get_location(user_id):
    """Gets user location from Redis."""
    key = f"user:{user_id}:location"

    try:
        data = rj.jsonget(key, Path.rootPath())
        if data:
            return jsonify(data)
        else:
            return jsonify(f"No location data for user {user_id}.", http.HTTPStatus.NOT_FOUND)
    except:
        print("*** get_location(): redisjson is dead!")
        return jsonify(f"Error retrieving data for user {user_id}.", http.HTTPStatus.INTERNAL_SERVER_ERROR)

def rjjsonsetwrapper(key, path, record):
    """Wrapper to add data to Redis."""
    try:
        rj.jsonset(key, path, record)
        return True
    except Exception as e:
        print('rjjsonsetwrapper() error:', str(e))
        print("*** redis is dead!")
        return False

################
# Security
################
def encode_token(user_id, token_type):
    if token_type == "access":
        seconds = g.access_token_expiration
    else:
        seconds = g.refresh_token_expiration

    payload = {
        "exp": datetime.utcnow() + timedelta(seconds=seconds),
        "iat": datetime.utcnow(),
        "sub": user_id,
    }
    return jwt.encode(
        payload, g.secret_key, algorithm="HS256"
    )

def decode_token(token):
    payload = jwt.decode(token, g.secret_key, algorithms=["HS256"])
    return payload["sub"]

####################
# Security Endpoints
####################
# @app.route("/login", methods=["POST"])
# def login():
#     try:
#         user = request.json['name']
#         password = request.json['password']
#         if not user or not password:
#             return jsonify(("Authentication is required and has failed!", status.HTTP_401_UNAUTHORIZED))
#         elif user not in g.users:
#             return jsonify(("Unknown user!", status.HTTP_401_UNAUTHORIZED))
#         else:
#             password_hash = g.password_hashes[g.users.index(user)]
#             if not bcrypt.check_password_hash(password_hash, password):
#                 return jsonify(("Authentication is required and has failed!", status.HTTP_401_UNAUTHORIZED))

#             userid = g.userids[g.users.index(user)]
#             access_token = encode_token(userid, "access")
#             refresh_token = encode_token(userid, "refresh")

#             response_object = {
#                 "access_token": access_token,
#                 "refresh_token": refresh_token,
#                 "name": user 
#             }
#             return jsonify((response_object, status.HTTP_200_OK))
#     except Exception as e:
#         return jsonify(("Authentication is required and has failed!", status.HTTP_401_UNAUTHORIZED))

# @app.route("/login", methods=["POST"])
# def login():
#     try:
#         user = request.json['name']
#         password = request.json['password']
#         if not user or not password:
#             return jsonify(("Authentication is required and has failed!", status.HTTP_401_UNAUTHORIZED))
#         elif user not in g.users:
#             return jsonify(("Unknown user!", status.HTTP_401_UNAUTHORIZED))
#         else:
#             password_hash = g.password_hashes[g.users.index(user)]
#             if not bcrypt.check_password_hash(password_hash, password):
#                 return jsonify(("Authentication is required and has failed!", status.HTTP_401_UNAUTHORIZED))

#             # Update user's name and password in Redis
#             user_id = g.userids[g.users.index(user)]
#             user_key = f"users:{user_id}"
#             user_record = {
#                 "name": user,
#                 "password": password
#             }
#             rjjsonsetwrapper(user_key, Path.rootPath(), user_record)

#             # Generate tokens
#             access_token = encode_token(user_id, "access")
#             refresh_token = encode_token(user_id, "refresh")

#             response_object = {
#                 "access_token": access_token,
#                 "refresh_token": refresh_token,
#                 "name": user 
#             }
#             return jsonify((response_object, status.HTTP_200_OK))
#     except Exception as e:
#         return jsonify(("Authentication is required and has failed!", status.HTTP_401_UNAUTHORIZED))

@app.route("/login", methods=["POST"])
def login():
    try:
        user = request.json['name']
        password = request.json['password']
        if not user or not password:
            return jsonify(("Authentication is required and has failed!", status.HTTP_401_UNAUTHORIZED))
        else:
            # Update user1's name and password in Redis
            user_id = g.userids[g.users.index(user)]
            user_key = "currentUser"
            user_record = {
                "name": user,
                "password": password
            }
            rjjsonsetwrapper(user_key, Path.rootPath(), user_record)

            # Generate tokens
            access_token = encode_token(user_id, "access")
            refresh_token = encode_token(user_id, "refresh")

            response_object = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "name": user 
            }
            return jsonify((response_object, status.HTTP_200_OK))
    except Exception as e:
        return jsonify(("Authentication is required and has failed!", status.HTTP_401_UNAUTHORIZED))



@app.route("/fastlogin", methods=["POST"])
def fastlogin():
    try:
        access_token = request.json['access-token']
        refresh_token = request.json['refresh-token']

        if not access_token or not refresh_token:
            return jsonify(("Missing token(s)!", status.HTTP_401_UNAUTHORIZED))
        else:
            try:
                userid = decode_token(access_token)
                if userid not in g.userids:
                    raise Exception
            except:
                try:
                    userid = decode_token(refresh_token)
                    if userid not in g.userids:
                        raise Exception
                except:
                    return jsonify(("Invalid token(s)!", status.HTTP_401_UNAUTHORIZED))

            access_token = encode_token(userid, "access")
            refresh_token = encode_token(userid, "refresh")

            response_object = {
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
            return jsonify((response_object, status.HTTP_200_OK))
    except Exception as e:
        return jsonify(("Authentication is required and has failed!", status.HTTP_401_UNAUTHORIZED))


@app.route("/get-user1-data", methods=["GET"])
def get_user1_data():
    user_key = "currentUser"  # Updated to fetch user1's data
    try:
        data = rj.jsonget(user_key, Path.rootPath())
        if data:
            return jsonify(data)
        else:
            return jsonify("No data found for user1.", http.HTTPStatus.NOT_FOUND)
    except:
        print("*** Error retrieving data for user1.")
        return jsonify("Error retrieving data for user1.", http.HTTPStatus.INTERNAL_SERVER_ERROR)




if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
