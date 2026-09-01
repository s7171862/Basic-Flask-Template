from flask import *
import sys, os, uuid
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
TOOL_UPLOAD_FOLDER = 'toolphotos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['TOOL_UPLOAD_FOLDER'] = TOOL_UPLOAD_FOLDER
app.config['SECRET_KEY'] = "Type in secret line of text"
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.after_request
def disable_development_cache(response):
    """Always serve the newest pages and styles while developing locally."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

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

def migrate_database():
    """Create feature tables for existing local databases as well."""
    import sqlite3
    with open("database/createscript.txt", "r") as f:
        schema = f.read()
    conn = sqlite3.connect("database/test.db")
    for statement in schema.split(';'):
        if statement.strip().upper().startswith('CREATE TABLE'):
            statement = statement.replace('CREATE TABLE', 'CREATE TABLE IF NOT EXISTS', 1)
            conn.execute(statement)
    tool_columns = {column[1] for column in conn.execute("PRAGMA table_info(tools)").fetchall()}
    if 'toolphoto' not in tool_columns:
        conn.execute("ALTER TABLE tools ADD COLUMN toolphoto TEXT NOT NULL DEFAULT ''")
    if 'city' not in tool_columns:
        conn.execute("ALTER TABLE tools ADD COLUMN city TEXT NOT NULL DEFAULT ''")
    if 'suburb' not in tool_columns:
        conn.execute("ALTER TABLE tools ADD COLUMN suburb TEXT NOT NULL DEFAULT ''")
    if 'location' not in tool_columns:
        # Kept for compatibility with earlier local database versions.
        conn.execute("ALTER TABLE tools ADD COLUMN location TEXT NOT NULL DEFAULT ''")
    conn.commit()
    conn.close()

    os.makedirs(TOOL_UPLOAD_FOLDER, exist_ok=True)

init_database()
migrate_database()
DATABASE = Database("database/test.db", app.logger)

#---VIEW FUNCTIONS----------------------------------------------------
@app.route('/')
def landing():
    app.logger.info("Landing page")
    # Treat the landing page as a fresh starting point for every visit.
    # This prevents an old browser session from automatically reopening a dashboard.
    session.clear()
    return render_template("landing.html")


@app.route('/logout')
def logout():
    app.logger.info("Log out")
    session.clear()
    return redirect('./')

@app.route('/begin-registration/<role>')
def begin_registration(role):
    """Allow a registration form to be opened only from the landing page."""
    registration_routes = {
        'renter': 'register_renter',
        'provider': 'register_provider'
    }
    if role not in registration_routes:
        return redirect('./')

    session.clear()
    session['registration_access_role'] = role
    return redirect(url_for(registration_routes[role], access='1'))

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
    
    # Each user role has its own dashboard; there is no standalone home page.
    home_templates = {
        'User (Renter)': 'home_renter.html',
        'User (Tool Provider)': 'home_provider.html'
    }
    template = home_templates.get(session.get('permission'))
    if template:
        return render_template(template)

    flash('Your account does not have a valid dashboard role. Please log in again.')
    return redirect('./logout')

def provider_only():
    """Keep provider tools separate from renter accounts."""
    return 'userid' in session and session.get('permission') == 'User (Tool Provider)'

@app.route('/provider/listings', methods=['GET', 'POST'])
def provider_listings():
    if not provider_only():
        return redirect('./')
    if request.method == 'POST':
        title = request.form['title'].strip()
        description = request.form['description'].strip()
        try:
            daily_rate = float(request.form['daily_rate'])
        except ValueError:
            daily_rate = 0
        city = request.form['city'].strip()
        suburb = request.form['suburb'].strip()
        tool_type = request.form['tool_type'].strip()
        brand = request.form['brand'].strip()
        tool_condition = request.form['tool_condition'].strip()
        available_from = request.form['available_from']
        available_until = request.form['available_until']
        tool_photo = request.files.get('toolphoto')
        photo_is_valid = tool_photo and tool_photo.filename and allowed_file(tool_photo.filename)
        if not all([title, description, city, suburb, tool_type, brand, tool_condition, available_from, available_until]) or daily_rate <= 0 or available_until < available_from:
            flash('Complete every tool field, use a valid daily rate, and choose valid availability dates.')
        elif not photo_is_valid:
            flash('A tool photo is required. Please upload a PNG, JPG, JPEG, or GIF image.')
        else:
            extension = secure_filename(tool_photo.filename).rsplit('.', 1)[1].lower()
            photo_filename = f"tool_{session['userid']}_{uuid.uuid4().hex}.{extension}"
            tool_photo_path = os.path.join(app.config['TOOL_UPLOAD_FOLDER'], photo_filename)
            tool_photo.save(tool_photo_path)
            DATABASE.ModifyQuery(
                """INSERT INTO tools (providerid, title, description, daily_rate, city, suburb, location, tool_type, brand, tool_condition, toolphoto, available_from, available_until)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session['userid'], title, description, daily_rate, city, suburb, f"{suburb}, {city}", tool_type, brand, tool_condition, tool_photo_path, available_from, available_until)
            )
            flash('Your tool has been added to the Toolly marketplace.')
            return redirect('/provider/listings')
    tools = DATABASE.ViewQuery("SELECT * FROM tools WHERE providerid = ? ORDER BY toolid DESC", (session['userid'],)) or []
    return render_template('provider_listings.html', tools=tools)

@app.route('/provider/listings/<int:tool_id>/edit', methods=['GET', 'POST'])
def provider_edit_listing(tool_id):
    if not provider_only():
        return redirect('./')
    tool_result = DATABASE.ViewQuery("SELECT * FROM tools WHERE toolid = ? AND providerid = ?", (tool_id, session['userid']))
    if not tool_result:
        return redirect('/provider/listings')
    tool = tool_result[0]

    if request.method == 'POST':
        title = request.form['title'].strip()
        description = request.form['description'].strip()
        city = request.form['city'].strip()
        suburb = request.form['suburb'].strip()
        tool_type = request.form['tool_type'].strip()
        brand = request.form['brand'].strip()
        tool_condition = request.form['tool_condition'].strip()
        available_from = request.form['available_from']
        available_until = request.form['available_until']
        try:
            daily_rate = float(request.form['daily_rate'])
        except ValueError:
            daily_rate = 0
        if not all([title, description, city, suburb, tool_type, brand, tool_condition, available_from, available_until]) or daily_rate <= 0 or available_until < available_from:
            flash('Complete every tool field, use a valid daily rate, and choose valid availability dates.')
            return render_template('provider_edit_listing.html', tool=tool)

        tool_photo_path = tool['toolphoto']
        tool_photo = request.files.get('toolphoto')
        if tool_photo and tool_photo.filename:
            if not allowed_file(tool_photo.filename):
                flash('Tool photos must be PNG, JPG, JPEG, or GIF files.')
                return render_template('provider_edit_listing.html', tool=tool)
            extension = secure_filename(tool_photo.filename).rsplit('.', 1)[1].lower()
            photo_filename = f"tool_{session['userid']}_{uuid.uuid4().hex}.{extension}"
            tool_photo_path = os.path.join(app.config['TOOL_UPLOAD_FOLDER'], photo_filename)
            tool_photo.save(tool_photo_path)

        DATABASE.ModifyQuery(
            """UPDATE tools SET title = ?, description = ?, daily_rate = ?, city = ?, suburb = ?, location = ?, tool_type = ?, brand = ?, tool_condition = ?, toolphoto = ?, available_from = ?, available_until = ?
               WHERE toolid = ? AND providerid = ?""",
            (title, description, daily_rate, city, suburb, f"{suburb}, {city}", tool_type, brand, tool_condition, tool_photo_path, available_from, available_until, tool_id, session['userid'])
        )
        flash('Your tool listing has been updated.')
        return redirect('/provider/listings')

    return render_template('provider_edit_listing.html', tool=tool)

@app.route('/provider/active-rentals', methods=['GET', 'POST'])
def provider_active_rentals():
    if not provider_only():
        return redirect('./')
    if request.method == 'POST':
        rental_id = request.form.get('rentalid', type=int)
        rental = DATABASE.ViewQuery("SELECT toolid FROM tool_rentals WHERE rentalid = ? AND providerid = ? AND status = 'active'", (rental_id, session['userid']))
        DATABASE.ModifyQuery(
            "UPDATE tool_rentals SET status = 'completed', completed_at = datetime('now','localtime') WHERE rentalid = ? AND providerid = ? AND status = 'active'",
            (rental_id, session['userid'])
        )
        if rental:
            DATABASE.ModifyQuery("UPDATE tools SET is_available = 1 WHERE toolid = ?", (rental[0]['toolid'],))
        flash('Rental marked as completed.')
        return redirect('/provider/active-rentals')
    rentals = DATABASE.ViewQuery("""SELECT tool_rentals.*, tools.title, users.firstname || ' ' || users.lastname AS renter_name
                                  FROM tool_rentals JOIN tools ON tools.toolid = tool_rentals.toolid
                                  JOIN users ON users.userid = tool_rentals.renterid
                                  WHERE tool_rentals.providerid = ? AND tool_rentals.status = 'active' ORDER BY tool_rentals.rentalid DESC""", (session['userid'],)) or []
    return render_template('provider_rentals.html', rentals=rentals)

@app.route('/provider/earnings')
def provider_earnings():
    if not provider_only():
        return redirect('./')
    summary = DATABASE.ViewQuery("SELECT COUNT(*) AS completed_rentals, COALESCE(SUM(total), 0) AS total FROM tool_rentals WHERE providerid = ? AND status = 'completed'", (session['userid'],))[0]
    return render_template('provider_earnings.html', summary=summary)

@app.route('/provider/past-rentals', methods=['GET', 'POST'])
def provider_past_rentals():
    if not provider_only():
        return redirect('./')
    if request.method == 'POST':
        rental_id = request.form.get('rentalid', type=int)
        rental = DATABASE.ViewQuery("SELECT * FROM tool_rentals WHERE rentalid = ? AND providerid = ? AND status = 'completed'", (rental_id, session['userid']))
        if not rental:
            return redirect('/provider/past-rentals')
        if request.form.get('action') == 'rate':
            rating = request.form.get('rating', type=int)
            comment = request.form.get('comment', '').strip()
            if rating and 1 <= rating <= 5:
                DATABASE.ModifyQuery("INSERT OR REPLACE INTO ratings (rentalid, providerid, renterid, rating, comment) VALUES (?, ?, ?, ?, ?)", (rental_id, session['userid'], rental[0]['renterid'], rating, comment))
                flash('Customer rating saved.')
        elif request.form.get('action') == 'claim':
            description = request.form.get('description', '').strip()
            if description:
                DATABASE.ModifyQuery("INSERT INTO claims (rentalid, providerid, description) VALUES (?, ?, ?)", (rental_id, session['userid'], description))
                flash('Your claim has been submitted.')
        return redirect('/provider/past-rentals')
    rentals = DATABASE.ViewQuery("""SELECT tool_rentals.*, tools.title, users.firstname || ' ' || users.lastname AS renter_name
                                  FROM tool_rentals JOIN tools ON tools.toolid = tool_rentals.toolid
                                  JOIN users ON users.userid = tool_rentals.renterid
                                  WHERE tool_rentals.providerid = ? AND tool_rentals.status = 'completed' ORDER BY tool_rentals.completed_at DESC""", (session['userid'],)) or []
    return render_template('provider_past_rentals.html', rentals=rentals)

def renter_only():
    return 'userid' in session and session.get('permission') == 'User (Renter)'

@app.route('/renter/browse', methods=['GET', 'POST'])
def renter_browse():
    if not renter_only():
        return redirect('./')
    if request.method == 'POST':
        tool_id = request.form.get('toolid', type=int)
        tool = DATABASE.ViewQuery("SELECT * FROM tools WHERE toolid = ? AND is_available = 1", (tool_id,))
        if tool and request.form.get('action') == 'wishlist':
            DATABASE.ModifyQuery("INSERT OR IGNORE INTO tool_wishlists (renterid, toolid) VALUES (?, ?)", (session['userid'], tool_id))
            flash('Tool added to your wishlist.')
        elif tool and request.form.get('action') == 'rent':
            DATABASE.ModifyQuery("INSERT INTO tool_rentals (toolid, renterid, providerid, total) VALUES (?, ?, ?, ?)", (tool_id, session['userid'], tool[0]['providerid'], tool[0]['daily_rate']))
            DATABASE.ModifyQuery("UPDATE tools SET is_available = 0 WHERE toolid = ?", (tool_id,))
            flash('Rental started. It is now in My Rentals.')
        return redirect('/renter/browse')
    filters = {key: request.args.get(key, '').strip() for key in ('city', 'suburb', 'tool_type', 'brand', 'tool_condition', 'available_on')}
    max_price = request.args.get('max_price', '').strip()
    show_unavailable = request.args.get('show_unavailable') == '1'
    query = "SELECT tools.*, users.firstname || ' ' || users.lastname AS provider_name FROM tools JOIN users ON users.userid = tools.providerid WHERE 1 = 1"
    params = []
    for field in ('city', 'suburb', 'tool_type', 'brand', 'tool_condition'):
        if filters[field]:
            query += f" AND lower(tools.{field}) LIKE ?"
            params.append('%' + filters[field].lower() + '%')
    if max_price:
        try:
            query += " AND tools.daily_rate <= ?"
            params.append(float(max_price))
        except ValueError:
            flash('Maximum price must be a number.')
    if filters['available_on']:
        query += " AND tools.available_from <= ? AND tools.available_until >= ?"
        params.extend([filters['available_on'], filters['available_on']])
    if not show_unavailable:
        query += " AND tools.is_available = 1"
    query += " ORDER BY tools.toolid DESC"
    tools = DATABASE.ViewQuery(query, tuple(params)) or []
    return render_template('renter_browse.html', tools=tools, filters=filters, max_price=max_price, show_unavailable=show_unavailable)

@app.route('/renter/rentals')
def renter_rentals():
    if not renter_only():
        return redirect('./')
    rentals = DATABASE.ViewQuery("""SELECT tool_rentals.*, tools.title, users.firstname || ' ' || users.lastname AS provider_name
                                  FROM tool_rentals JOIN tools ON tools.toolid = tool_rentals.toolid JOIN users ON users.userid = tool_rentals.providerid
                                  WHERE tool_rentals.renterid = ? AND tool_rentals.status = 'active' ORDER BY tool_rentals.rentalid DESC""", (session['userid'],)) or []
    return render_template('renter_rentals.html', rentals=rentals, title='My Rentals')

@app.route('/renter/wishlist', methods=['GET', 'POST'])
def renter_wishlist():
    if not renter_only():
        return redirect('./')
    if request.method == 'POST':
        DATABASE.ModifyQuery("DELETE FROM tool_wishlists WHERE wishlistid = ? AND renterid = ?", (request.form.get('wishlistid', type=int), session['userid']))
        flash('Tool removed from your wishlist.')
        return redirect('/renter/wishlist')
    tools = DATABASE.ViewQuery("""SELECT tool_wishlists.wishlistid, tools.*, users.firstname || ' ' || users.lastname AS provider_name
                                FROM tool_wishlists JOIN tools ON tools.toolid = tool_wishlists.toolid JOIN users ON users.userid = tools.providerid
                                WHERE tool_wishlists.renterid = ? ORDER BY tool_wishlists.wishlistid DESC""", (session['userid'],)) or []
    return render_template('renter_wishlist.html', tools=tools)

@app.route('/renter/past-rentals')
def renter_past_rentals():
    if not renter_only():
        return redirect('./')
    rentals = DATABASE.ViewQuery("""SELECT tool_rentals.*, tools.title, users.firstname || ' ' || users.lastname AS provider_name
                                  FROM tool_rentals JOIN tools ON tools.toolid = tool_rentals.toolid JOIN users ON users.userid = tool_rentals.providerid
                                  WHERE tool_rentals.renterid = ? AND tool_rentals.status = 'completed' ORDER BY tool_rentals.completed_at DESC""", (session['userid'],)) or []
    return render_template('renter_rentals.html', rentals=rentals, title='Past Rentals')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    """View and update the signed-in user's account details."""
    if 'userid' not in session:
        return redirect('./')

    user_id = session['userid']
    results = DATABASE.ViewQuery("SELECT * FROM users WHERE userid = ?", (user_id,))
    if not results:
        session.clear()
        return redirect('./')
    user = results[0]

    if request.method == 'POST':
        firstname = request.form['fname'].strip()
        lastname = request.form['lname'].strip()
        email = request.form['email'].strip().lower()

        existing_email = DATABASE.ViewQuery(
            "SELECT userid FROM users WHERE email = ? AND userid != ?", (email, user_id)
        )
        if existing_email:
            flash('That email address is already in use.')
            return render_template('profile.html', user=user)

        filepath = user['profilephoto'] or ''
        file = request.files.get('file')
        if file and file.filename:
            if not allowed_file(file.filename):
                flash('Please upload a PNG, JPG, JPEG, or GIF image.')
                return render_template('profile.html', user=user)
            extension = secure_filename(file.filename).rsplit('.', 1)[1].lower()
            filename = f"{user_id}_{uuid.uuid4().hex}.{extension}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

        DATABASE.ModifyQuery(
            "UPDATE users SET firstname = ?, lastname = ?, email = ?, profilephoto = ? WHERE userid = ?",
            (firstname, lastname, email, filepath, user_id)
        )
        session['name'] = firstname + ' ' + lastname
        session['profilephoto'] = filepath
        flash('Your profile has been updated.')
        return redirect('/profile')

    return render_template('profile.html', user=user)

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
    if request.method == 'GET':
        if request.args.get('access') != '1' or session.get('registration_access_role') != 'renter':
            return redirect('./')
        session.pop('registration_access_role', None)
        session['registration_form_role'] = 'renter'
    elif session.get('registration_form_role') != 'renter':
        return redirect('./')

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
                session.pop('registration_form_role', None)
                
                return redirect('/home')

    return render_template("register_renter.html", message=message)

@app.route('/register/provider', methods=['GET','POST'])
def register_provider():
    app.logger.info("Register Provider")
    if request.method == 'GET':
        if request.args.get('access') != '1' or session.get('registration_access_role') != 'provider':
            return redirect('./')
        session.pop('registration_access_role', None)
        session['registration_form_role'] = 'provider'
    elif session.get('registration_form_role') != 'provider':
        return redirect('./')

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
                session.pop('registration_form_role', None)
                
                return redirect('/home')

    return render_template("register_provider.html", message=message)

#return a profile photo
@app.route('/profilephotos/<filename>')
def serve_file(filename):
    if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)): # Ensure the file exists
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    else:
        abort(404) # If the file does not exist, return a 404 error

@app.route('/toolphotos/<filename>')
def serve_tool_photo(filename):
    return send_from_directory(app.config['TOOL_UPLOAD_FOLDER'], filename)

#main method called web server application
if __name__ == '__main__':
    print("About to start Flask app...")
    sys.stdout.flush()
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True) #templates and static files still refresh without Flask's debug error screen
    except Exception as e:
        print(f"Error: {e}")
        sys.stderr.write(f"Stderr: {e}\n")
        import traceback
        traceback.print_exc()
