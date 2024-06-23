from flask import Flask, request, jsonify
from flask_cors import CORS
from rejson import Client, Path
from datetime import datetime
import pytz
import os
import random
import http
import jwt
import bcrypt

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
    

################
# Security
################
def set_env_var():
    global g
    if 'database_url' not in g:
        g['database_url'] = os.environ.get("DATABASE_URL", 'mongodb://localhost:27017/')
    if 'secret_key' not in g:
        g['secret_key'] = os.environ.get("SECRET_KEY", "my_precious_1869")
    if 'bcrypt_log_rounds' not in g:
        g['bcrypt_log_rounds'] = os.environ.get("BCRYPT_LOG_ROUNDS", 13)
    if 'access_token_expiration' not in g:
        g['access_token_expiration'] = os.environ.get("ACCESS_TOKEN_EXPIRATION", 900)
    if 'refresh_token_expiration' not in g:
        g['refresh_token_expiration'] = os.environ.get("REFRESH_TOKEN_EXPIRATION", 2592000)
    if 'users' not in g:
        users = os.environ.get("USERS", 'Elon Musk,Bill Gates,Jeff Bezos')
        print('users=', users)
        print('g.users=', list(users.split(',')))
        g['users'] = list(users.split(','))
        print('g.users=', g['users'])
    if 'passwords' not in g:
        passwords = os.environ.get("PASSWORDS", 'Tesla,Clippy,Blue Horizon')
        g['passwords'] = list(passwords.split(','))
        print("g['passwords']=", g['passwords'])
        # Once hashed, the value is irreversible. However in the case of 
        # validating logins a simple hashing of candidate password and 
        # subsequent comparison can be done in constant time. This helps 
        # prevent timing attacks.
        #g['password_hashes'] = list(map(lambda p: bcrypt.generate_password_hash(str(p), g['bcrypt_log_rounds']).decode('utf-8'), g['passwords']))
        g['password_hashes'] = []
        for p in g['passwords']:
            g['password_hashes'].append(bcrypt.generate_password_hash(p, 13).decode('utf-8'))
        print("g['password_hashes]=", g['password_hashes'])
        g['userids'] = list(range(0, len(g['users'])))
        print("g['userids]=", g['userids'])

def get_env_var(varname):
    #return g.pop(varname, None)
    global g
    return g[varname]

def encode_token(user_id, token_type):
    if token_type == "access":
        seconds = get_env_var("access_token_expiration")
    else:
        seconds = get_env_var("refresh_token_expiration")

    payload = {
        "exp": datetime.utcnow() + timedelta(seconds=seconds),
        "iat": datetime.utcnow(),
        "sub": user_id,
    }
    return jwt.encode(
        payload, get_env_var("secret_key"), algorithm="HS256"
    )

def decode_token(token):
    #payload = jwt.decode(token, get_env_var("secret_key"))
    payload = jwt.decode(token, get_env_var("secret_key"), algorithms=["HS256"])
    print("decode_token:", payload)
    return payload["sub"]


####################
# Security Endpoints

# Returns an encoded userid as jwt access and a refresh tokens. Requires username 
# and password. Refresh token not used. Only meant to be used with token issuer,
# but here the token issuer and the be are one and the same.
@app.route("/login", methods=["POST"])
def login():
    try:
        user = request.json['name']
        password = request.json['password']
        print('user:', user)
        print('password:', password)
        print('users:', get_env_var('users'))
        if not user or not password:
            print('not user or not password!')
            return jsonify(("Authentication is required and has failed!", status.HTTP_401_UNAUTHORIZED))
        elif not user in get_env_var('users'):
            print('unknown user!')
            return jsonify(("Unknown user!", status.HTTP_401_UNAUTHORIZED))
        else:
            # presumably we only store password hashes and compare passed pwd
            # with our stored hash. For simplicity, we store the full password
            # and the hash, which we retrieve here
            print('password_hashes:', get_env_var('password_hashes'))
            print("get_env_var('users').index(user):", get_env_var('users').index(user))
            password_hash = get_env_var('password_hashes')[get_env_var('users').index(user)]
            print('password_hash:', password_hash)
            a = datetime.now()
            if not bcrypt.check_password_hash(password_hash, password):
                print('bcrypt.check_password_hash(password_hash, password) returned False!')
                return jsonify(("Authentication is required and has failed!", status.HTTP_401_UNAUTHORIZED))
            b = datetime.now()
            print('check_password took:', b - a)
            # debugging
            #print('password:', password)
            #print('type(password):', type(password))
            #for i in range(3):
            #    password_hash2 = bcrypt.generate_password_hash(password, 13).decode('utf-8')
            #    print('password_hash2:', password_hash2)
            #    if not bcrypt.check_password_hash(password_hash2, password):
            #        print('bcrypt.check_password_hash(password_hash, password) returned False!')
            #        return jsonify(("Authentication is required and has failed!", status.HTTP_401_UNAUTHORIZED))

            # create access and refresh token for the user to save.
            # User needs to pass access token for all secured APIs.
            userid = get_env_var('userids')[get_env_var('users').index(user)]
            access_token = encode_token(userid, "access")
            refresh_token = encode_token(userid, "refresh")
            print('type(access_token):', type(access_token))
            #response_object = {
            #    "access_token": access_token.decode(),
            #    "refresh_token": refresh_token.decode(),
            #}
            response_object = {
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
            #return response_object, 200
            #return response_object
            return jsonify((response_object, status.HTTP_200_OK))
    except Exception as e:
        print('exception:', e)
        return jsonify(("Authentication is required and has failed!", status.HTTP_401_UNAUTHORIZED))


# Returns an encoded userid. Requires both tokens. If access token expired 
# returns status.HTTP_401_UNAUTHORIZED, and user needs to fast login. If refresh 
# token expired returns status.HTTP_401_UNAUTHORIZED, and user needs to login
# with username and password. Tokens are usually passed in authorization headers 
# (auth_header = request.headers.get("Authorization")). For simplicity, I just 
# pass access token as an extra parameter in secured API calls.
@app.route("/fastlogin", methods=["POST"])
def fastlogin():
    try:
        access_token = request.json['access-token']
        refresh_token = request.json['refresh-token']

        if not access_token or not refresh_token:
            return jsonify(("Missing token(s)!", status.HTTP_401_UNAUTHORIZED))
        else:
            try:
                # first, with access token:
                userid = decode_token(access_token)

                if not userid or not userid in get_env_var('userids'):
                    return jsonify(("User unknown, please login with username and password.", status.HTTP_401_UNAUTHORIZED))

                try:
                    # second, with refresh token
                    userid2 = decode_token(refresh_token)

                    if not userid2 or userid2 != userid:
                        return jsonify(("User unknown, please login with username and password.", status.HTTP_401_UNAUTHORIZED))

                    # issue a new access token, keep the same refresh token
                    access_token = encode_token(userid, "access")
                    response_object = {
                        "access_token": access_token.decode(),
                        "refresh_token": refresh_token,
                    }
                    return jsonify((response_object, status.HTTP_200_OK))

                # refresh token failure: Need username/pwd login
                except jwt.ExpiredSignatureError:
                    return jsonify(("Lease expired. Please log in with username and password.", status.HTTP_401_UNAUTHORIZED))
                
                except jwt.InvalidTokenError:
                    return jsonify(("Invalid token. Please log in with username and password.", status.HTTP_401_UNAUTHORIZED))

            # access token failure: Need at least fast login
            except jwt.ExpiredSignatureError:
                return jsonify(("Signature expired. Please fast log in.", status.HTTP_401_UNAUTHORIZED))
            
            except jwt.InvalidTokenError:
                return jsonify(("Invalid token. Please fast log in.", status.HTTP_401_UNAUTHORIZED))

    except:
        return jsonify(("Missing token or other error. Please log in with username and password.", status.HTTP_401_UNAUTHORIZED))


def verify_token(token):
    try:
        userid = decode_token(token)
        print("verify_token():", token, userid)
        print("verify_token():", get_env_var('userids'))
        print("verify_token():", userid in get_env_var('userids'))

        if userid is None or not userid in get_env_var('userids'):
            print("verify_token() returning False")
            return False, jsonify(("User unknown!", status.HTTP_401_UNAUTHORIZED))
        else:
            print("verify_token() returning True")
            return True, userid

    except jwt.ExpiredSignatureError:
        return False, jsonify(("Signature expired. Please log in.", status.HTTP_401_UNAUTHORIZED))

    except jwt.InvalidTokenError:
        return False, jsonify(("Invalid token. Please log in.", status.HTTP_401_UNAUTHORIZED))



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
