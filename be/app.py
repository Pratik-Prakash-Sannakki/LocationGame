from flask import Flask, request, jsonify
from flask_cors import CORS
from rejson import Client, Path
from datetime import datetime
import pytz
import os
import random
import http

# Redis client setup
#rj = Client(host='127.0.0.1', port=6379, decode_responses=True)
redis_host = os.getenv('REDIS_HOST', 'localhost')  # Default to 'localhost' if 'REDIS_HOST' is not set
rj = Client(host=redis_host, port=6379, decode_responses=True)
push_to_redis = True
rj_host = 'localhost'

# Hard-coded time zone. Required for correct ObjectId comparisons!
local_zone = pytz.timezone('US/Eastern')

app = Flask(__name__)
CORS(app)

def tryexcept(requesto, key, default):
    """Helper function to handle missing keys in request JSON."""
    try:
        return requesto.json[key]
    except:
        return default

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
