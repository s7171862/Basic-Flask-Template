from flask import Flask, render_template, request, redirect, session, flash
import sys, os

app = Flask(__name__)
app.config['SECRET_KEY'] = "test"

@app.route('/')
def home():
    return "Hello World"

if __name__ == '__main__':
    print("Starting test app...")
    app.run(host='0.0.0.0', port=5000, debug=False)
