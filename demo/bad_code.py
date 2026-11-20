import sqlite3

   from flask import Flask, request

   app = Flask(__name__)


   @app.route("/user")
   def user():
       name = request.args.get("name")
       cur = sqlite3.connect("app.db").cursor()
       cur.execute("SELECT * FROM users WHERE name = '" + name + "'")
       return str(cur.fetchone())


   @app.route("/calc")
   def calc():
       return str(eval(request.args["expr"]))


   @app.route("/hello")
   def hello():
       return f"<h1>Hello {request.args.get('name', '')}</h1>"
