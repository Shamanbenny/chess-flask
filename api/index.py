from flask import Flask, request, jsonify
from flask_cors import CORS
from .endpoint import endpoint_blueprint

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["https://sneakyowl.net", "https://www.sneakyowl.net"]}})

app.register_blueprint(endpoint_blueprint)

@app.route('/')
def home():
    return 'Why are you here? 0.0'

@app.route('/test', methods=['POST'])
def test():
    try:
        data = request.get_json()
        print(data)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
