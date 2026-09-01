from flask import *
import sys, os
import logging
from interfaces.databaseinterface import Database
from interfaces.hashing import *
from werkzeug.utils import secure_filename

#---CONFIGURE APP---------------------------------------------------
app = Flask(__name__)
logging.basicConfig(filename='logs/flask.log', level=logging.INFO)
sys.tracebacklimit = 10

# Configure the upload folder and allowed file extensions
UPLOAD_FOLDER = 'profilephotos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = "Type in secret line of text"

# Function to check the file extension
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize database with schema if it doesn't exist
def init_database():
    import sqlite3
    db_path = "database/test.db"
    # Create database if it doesn't exist
    if not os.path.exists(db_path):
        with open("database/createscript.txt", "r") as f:
            schema = f.read()
        conn = sqlite3.connect(db_path)
        conn.executescript(schema)
        conn.commit()
        conn.close()

init_database()
DATABASE = Database("database/test.db", app.logger)

#---VIEW FUNCTIONS----------------------------------------------------
@app.route('/')
def landing():
    app.logger.info("Landing page")
    if 'permission' in session:
        if session['permission'] == 'admin':
            return redirect('./admin')
        return redirect('./home')
    return render_template("landing.html")


@app.route('/logout')
def logout():
    app.logger.info("Log out")
    session.clear()
    return redirect('./')

@app.route('/admin', methods=["GET","POST"])
def admin():

    if 'permission' not in session:
        return redirect("./")
    else:
        if session['permission'] != 'admin':
            return redirect("./")

    results = DATABASE.ViewQuery("SELECT * FROM users")

    if request.method == "POST":
        selectedusers = request.form.getlist("selectedusers")
        for userid in selectedusers:
            if int(userid) != 1:
                DATABASE.ModifyQuery("DELETE FROM users WHERE userid = ?", (userid,))
        return redirect("./admin")

    app.logger.info("Admin")
    return render_template("admin.html", results=results)

@app.route('/home')
def home():

    if 'userid' not in session:
        return redirect('./')

    app.logger.info("Home")
    
    # Render different home page based on user permission
    if session['permission'] == 'User (Renter)':
        return render_template("home_renter.html")
    elif session['permission'] == 'User (Tool Provider)':
        return render_template("home_provider.html")
    else:
        return render_template("home.html")

@app.route('/login', methods=["GET","POST"])
def login():
    app.logger.info("Login")

    if 'permission' in session:
        if session['permission'] == 'admin':
            return redirect("./admin")
        else:
            return redirect("./home")

    message = "Please login"
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']
        results = DATABASE.ViewQuery("SELECT * FROM users WHERE email = ?", (email,))
        if results:
            userdetails = results[0] #row in the user table (Python Dictionary)
            if check_password(userdetails['password'], password):
                if ':' not in userdetails['password']:
                    DATABASE.ModifyQuery("UPDATE users SET password = ? WHERE userid = ?", (hash_password(password), userdetails['userid']))

                message = "Login Successful"

                session['permission'] = userdetails['permission']
                session['userid'] = userdetails['userid']
                session['name'] = userdetails['firstname'] + " " + userdetails['lastname']
                session['profilephoto'] = userdetails['profilephoto']

                if session['permission'] == 'admin':
                    return redirect('./admin')
                else:
                    return redirect('./home')
            else: 
                message = "Password incorrect"
        else:
            message = "User does not exist, email is incorrect!!"

    return render_template("login.html", message=message)

@app.route('/register/renter', methods=['GET','POST'])
def register_renter():
    app.logger.info("Register Renter")
    message = "Please register as a Renter"
    if request.method == "POST":

        firstname = request.form['fname']
        lastname = request.form['lname']
        password = request.form['password']
        passwordconfirm = request.form['passwordconfirm']
        email = request.form['email']

        if password != passwordconfirm:
            message = "Error, passwords do not match"
        else:
            results = DATABASE.ViewQuery("SELECT * FROM users WHERE email = ?", (email,))
            if results:
                message = "Error, user already exists"
            else:

                #UPLOAD A FILE
                filepath = ''
                app.logger.info(request.files)
                if 'file' in request.files:
                    
                    file = request.files['file']
                    if file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)
                        flash("File uploaded successfully")
                    else:
                        flash("Problem with file upload")
                else:
                    flash("File not found")

                password = hash_password(password)
                permission = "User (Renter)"
                DATABASE.ModifyQuery("INSERT INTO users (firstname, lastname, email, password, profilephoto, permission) VALUES (?,?,?,?,?,?)", (firstname, lastname, email, password, filepath, permission))
                message = "Success, user has been added"
                
                # Log the user in automatically after registration
                user_data = DATABASE.ViewQuery("SELECT * FROM users WHERE email = ?", (email,))[0]
                session['permission'] = user_data['permission']
                session['userid'] = user_data['userid']
                session['name'] = user_data['firstname'] + " " + user_data['lastname']
                session['profilephoto'] = user_data['profilephoto']
                
                return redirect('/home')

    return render_template("register_renter.html", message=message)

@app.route('/register/provider', methods=['GET','POST'])
def register_provider():
    app.logger.info("Register Provider")
    message = "Please register as a Tool Provider"
    if request.method == "POST":

        firstname = request.form['fname']
        lastname = request.form['lname']
        password = request.form['password']
        passwordconfirm = request.form['passwordconfirm']
        email = request.form['email']

        if password != passwordconfirm:
            message = "Error, passwords do not match"
        else:
            results = DATABASE.ViewQuery("SELECT * FROM users WHERE email = ?", (email,))
            if results:
                message = "Error, user already exists"
            else:

                #UPLOAD A FILE
                filepath = ''
                app.logger.info(request.files)
                if 'file' in request.files:
                    
                    file = request.files['file']
                    if file and allowed_file(file.filename):
                        filename = secure_filename(file.filename)
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        file.save(filepath)
                        flash("File uploaded successfully")
                    else:
                        flash("Problem with file upload")
                else:
                    flash("File not found")

                password = hash_password(password)
                permission = "User (Tool Provider)"
                DATABASE.ModifyQuery("INSERT INTO users (firstname, lastname, email, password, profilephoto, permission) VALUES (?,?,?,?,?,?)", (firstname, lastname, email, password, filepath, permission))
                message = "Success, user has been added"
                
                # Log the user in automatically after registration
                user_data = DATABASE.ViewQuery("SELECT * FROM users WHERE email = ?", (email,))[0]
                session['permission'] = user_data['permission']
                session['userid'] = user_data['userid']
                session['name'] = user_data['firstname'] + " " + user_data['lastname']
                session['profilephoto'] = user_data['profilephoto']
                
                return redirect('/home')

    return render_template("register_provider.html", message=message)

#return a profile photo
@app.route('/profilephotos/<filename>')
def serve_file(filename):
    if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)): # Ensure the file exists
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    else:
        abort(404) # If the file does not exist, return a 404 error

#main method called web server application
if __name__ == '__main__':
    print("About to start Flask app...")
    sys.stdout.flush()
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_debugger=False, use_reloader=False, threaded=True) #runs a local server on port 5000
    except Exception as e:
        print(f"Error: {e}")
        sys.stderr.write(f"Stderr: {e}\n")
        import traceback
        traceback.print_exc()
