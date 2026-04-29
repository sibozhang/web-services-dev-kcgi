from flask import Flask
from flask import request
app = Flask(__name__)


@app.route("/")
def hello():
    return {"message": "Hello from Flask"}

@app.route("/hello", methods=["GET"])
def hello_user():
    user_id = request.args.get("user")
    if user_id:
        return f"Hello, {user_id}!"
    else:
        return "Hello, anonymous visitor!"
    
@app.route("/hello/<user>", methods=["GET"])
def clean_hello(user):
    if len(user):
        return f"Hello, {user}!"



@app.route ("/upload" , methods =[ "POST" ])
def create_user ():
    data = request.json
    return {"received" : data }, 201

app.run(port=1963)