from flask import Flask, request, jsonify
from flask_cors import CORS
from .v0 import v0_blueprint
from .v1 import v1_blueprint

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["https://sneakyowl.net", "https://www.sneakyowl.net"]}})

# Register blueprints
app.register_blueprint(v0_blueprint)
app.register_blueprint(v1_blueprint)

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
