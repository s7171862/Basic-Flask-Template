from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, session, url_for
import sys, os, uuid
from datetime import date
import logging
from interfaces.databaseinterface import Database
from interfaces.hashing import check_password, hash_password
from werkzeug.utils import secure_filename

#---CONFIGURE APP---------------------------------------------------
os.makedirs('logs', exist_ok=True)
app = Flask(__name__)
logging.basicConfig(filename='logs/flask.log', level=logging.INFO)
sys.tracebacklimit = 10

# Configure the upload folder and allowed file extensions
UPLOAD_FOLDER = 'profilephotos'
TOOL_UPLOAD_FOLDER = 'toolphotos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['TOOL_UPLOAD_FOLDER'] = TOOL_UPLOAD_FOLDER
# Set TOOLLY_SECRET_KEY in the environment before deploying.  The fallback
# keeps this school-project copy easy to run locally.
app.config['SECRET_KEY'] = os.environ.get('TOOLLY_SECRET_KEY', 'toolly-local-development-key')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB image upload limit
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


@app.errorhandler(413)
def upload_too_large(error):
    """Show a useful page message when an image exceeds the upload limit."""
    flash('Images must be 5 MB or smaller.')
    return redirect(url_for('home') if 'userid' in session else url_for('landing'))

# Function to check the file extension
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_image(upload, folder, prefix):
    """Validate and save one image, returning its web path or ``None``.

    Keeping filename creation in one place prevents duplicate file-handling
    code and avoids users overwriting one another's uploads.
    """
    if not upload or not upload.filename or not allowed_file(upload.filename):
        return None
    extension = secure_filename(upload.filename).rsplit('.', 1)[1].lower()
    filename = f"{prefix}_{uuid.uuid4().hex}.{extension}"
    upload.save(os.path.join(folder, filename))
    return os.path.join(folder, filename).replace('\\', '/')


def read_tool_form():
    """Return validated tool form data, or an error message for the user."""
    fields = {name: request.form.get(name, '').strip() for name in
              ('title', 'description', 'city', 'suburb', 'tool_type', 'brand', 'tool_condition')}
    try:
        daily_rate = float(request.form.get('daily_rate', ''))
        original_value = float(request.form.get('original_value', ''))
        available_from = date.fromisoformat(request.form.get('available_from', ''))
        available_until = date.fromisoformat(request.form.get('available_until', ''))
    except (TypeError, ValueError):
        return None, 'Enter valid prices and availability dates.'

    if not all(fields.values()) or daily_rate <= 0 or original_value <= 0 or available_until < available_from:
        return None, 'Complete every tool field, use positive prices, and choose valid availability dates.'

    fields.update({
        'daily_rate': daily_rate,
        'original_value': original_value,
        'available_from': available_from.isoformat(),
        'available_until': available_until.isoformat(),
        'location': f"{fields['suburb']}, {fields['city']}"
    })
    return fields, None


def create_account(permission):
    """Validate, create, and sign in a renter or provider account."""
    firstname = request.form.get('fname', '').strip()
    lastname = request.form.get('lname', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    password_confirm = request.form.get('passwordconfirm', '')
    if not all((firstname, lastname, email, password)):
        return 'Complete all required fields.'
    if password != password_confirm:
        return 'Error, passwords do not match.'
    if DATABASE.ViewQuery("SELECT userid FROM users WHERE email = ?", (email,)):
        return 'Error, a user with that email already exists.'

    profile_photo = ''
    upload = request.files.get('file')
    if upload and upload.filename:
        profile_photo = save_uploaded_image(upload, UPLOAD_FOLDER, 'profile')
        if not profile_photo:
            return 'Profile photos must be PNG, JPG, JPEG, or GIF files.'

    if not DATABASE.ModifyQuery(
        "INSERT INTO users (firstname, lastname, email, password, profilephoto, permission) VALUES (?, ?, ?, ?, ?, ?)",
        (firstname, lastname, email, hash_password(password), profile_photo, permission)
    ):
        return 'Your account could not be created. Please try again.'

    user = DATABASE.ViewQuery("SELECT userid, firstname, lastname, profilephoto, permission FROM users WHERE email = ?", (email,))[0]
    session['permission'] = user['permission']
    session['userid'] = user['userid']
    session['name'] = f"{user['firstname']} {user['lastname']}"
    session['profilephoto'] = user['profilephoto']
    return None

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
    """Create feature tables for existing local databases as well.

    Maintenance note: whenever database/createscript.txt changes, review this
    function too. The schema file builds new databases; this function keeps an
    existing database/test.db compatible without deleting its data.
    """
    import sqlite3
    with open("database/createscript.txt", "r") as f:
        schema = f.read()
    conn = sqlite3.connect("database/test.db")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    index_statements = []
    for statement in schema.split(';'):
        # Ignore SQL comments before testing a statement, so the maintenance
        # note at the top of createscript.txt does not hide CREATE TABLE users.
        statement = '\n'.join(line for line in statement.splitlines() if not line.lstrip().startswith('--')).strip()
        normalized = statement.upper()
        if normalized.startswith('CREATE TABLE'):
            statement = statement.replace('CREATE TABLE', 'CREATE TABLE IF NOT EXISTS', 1)
            conn.execute(statement)
        elif normalized.startswith('CREATE INDEX'):
            # Some existing databases need new columns before their message
            # indexes can be created, so run indexes after all migrations.
            index_statements.append(statement.replace('CREATE INDEX', 'CREATE INDEX IF NOT EXISTS', 1))
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
    if 'original_value' not in tool_columns:
        conn.execute("ALTER TABLE tools ADD COLUMN original_value REAL NOT NULL DEFAULT 0")
    rental_columns = {column[1] for column in conn.execute("PRAGMA table_info(tool_rentals)").fetchall()}
    for column, definition in {
        'start_date': "DATE NOT NULL DEFAULT ''", 'end_date': "DATE NOT NULL DEFAULT ''",
        'rental_days': 'INTEGER NOT NULL DEFAULT 1', 'rental_cost': 'REAL NOT NULL DEFAULT 0',
        'security_deposit': 'REAL NOT NULL DEFAULT 0', 'insurance_selected': 'INTEGER NOT NULL DEFAULT 0',
        'insurance_cost': 'REAL NOT NULL DEFAULT 0'
    }.items():
        if column not in rental_columns:
            conn.execute(f"ALTER TABLE tool_rentals ADD COLUMN {column} {definition}")
    message_columns = {column[1] for column in conn.execute("PRAGMA table_info(messages)").fetchall()}
    for column, definition in {
        'conversationid': 'INTEGER',
        'authorid': 'INTEGER',
        'created_at': "DATE NOT NULL DEFAULT ''"
    }.items():
        if column not in message_columns:
            conn.execute(f"ALTER TABLE messages ADD COLUMN {column} {definition}")
    if 'author' in message_columns:
        conn.execute("UPDATE messages SET authorid = author WHERE authorid IS NULL")
    # Existing databases cannot add NOT NULL or FOREIGN KEY constraints with
    # ALTER TABLE. Apply the rules that SQLite can safely add in place.
    conn.execute("UPDATE users SET permission = 'user' WHERE permission IS NULL")
    conn.execute("UPDATE users SET lastaccess = datetime('now','localtime') WHERE lastaccess IS NULL")
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email)")
    except sqlite3.IntegrityError:
        app.logger.warning("Could not enforce unique users.email: duplicate emails exist in database/test.db.")
    for statement in index_statements:
        conn.execute(statement)
    conn.commit()
    conn.close()

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
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
    if session.get('permission') != 'admin':
        return redirect("./")

    if request.method == "POST":
        selected_users = [userid for userid in request.form.getlist("selectedusers")
                          if userid.isdigit() and int(userid) not in (1, session['userid'])]
        if selected_users:
            placeholders = ', '.join('?' for _ in selected_users)
            DATABASE.ModifyQuery(f"DELETE FROM users WHERE userid IN ({placeholders})", tuple(selected_users))
            flash(f"Deleted {len(selected_users)} selected account(s).")
        return redirect("./admin")

    summary = DATABASE.ViewQuery("""SELECT
        (SELECT COUNT(*) FROM users) AS users_count,
        (SELECT COUNT(*) FROM users WHERE permission = 'User (Renter)') AS renters_count,
        (SELECT COUNT(*) FROM users WHERE permission = 'User (Tool Provider)') AS providers_count,
        (SELECT COUNT(*) FROM tools) AS tools_count,
        (SELECT COUNT(*) FROM tools WHERE is_available = 1) AS available_tools_count,
        (SELECT COUNT(*) FROM tool_rentals WHERE status = 'active') AS active_rentals_count,
        (SELECT COUNT(*) FROM tool_rentals WHERE status = 'completed') AS completed_rentals_count,
        (SELECT COUNT(*) FROM claims WHERE status = 'open') AS open_claims_count,
        (SELECT COUNT(*) FROM conversations) AS conversations_count""")[0]
    results = DATABASE.ViewQuery("""SELECT users.userid, users.firstname, users.lastname, users.email,
        users.permission, users.status, users.profilephoto, users.lastaccess,
        (SELECT COUNT(*) FROM tools WHERE tools.providerid = users.userid) AS listing_count,
        (SELECT COUNT(*) FROM tool_rentals WHERE tool_rentals.renterid = users.userid) AS renter_rental_count,
        (SELECT COUNT(*) FROM tool_rentals WHERE tool_rentals.providerid = users.userid) AS provider_rental_count
        FROM users ORDER BY users.userid ASC""") or []
    active_rentals = DATABASE.ViewQuery("""SELECT tool_rentals.rentalid, tool_rentals.status, tool_rentals.total,
        tool_rentals.start_date, tool_rentals.end_date, tools.title,
        renter.firstname || ' ' || renter.lastname AS renter_name,
        provider.firstname || ' ' || provider.lastname AS provider_name
        FROM tool_rentals JOIN tools ON tools.toolid = tool_rentals.toolid
        JOIN users AS renter ON renter.userid = tool_rentals.renterid
        JOIN users AS provider ON provider.userid = tool_rentals.providerid
        WHERE tool_rentals.status = 'active' ORDER BY tool_rentals.created_at DESC LIMIT 8""") or []
    open_claims = DATABASE.ViewQuery("""SELECT claims.claimid, claims.description, claims.created_at, claims.status,
        tools.title, users.firstname || ' ' || users.lastname AS provider_name
        FROM claims JOIN tool_rentals ON tool_rentals.rentalid = claims.rentalid
        JOIN tools ON tools.toolid = tool_rentals.toolid
        JOIN users ON users.userid = claims.providerid
        WHERE claims.status = 'open' ORDER BY claims.created_at DESC LIMIT 8""") or []
    app.logger.info("Admin")
    return render_template("admin.html", summary=summary, results=results, active_rentals=active_rentals, open_claims=open_claims)


@app.route('/admin/users/<int:user_id>', methods=['GET', 'POST'])
def admin_user_edit(user_id):
    """Let an administrator safely view and update a member account."""
    if session.get('permission') != 'admin':
        return redirect('./')

    user_result = DATABASE.ViewQuery(
        "SELECT userid, firstname, lastname, email, permission, status, profilephoto, lastaccess FROM users WHERE userid = ?",
        (user_id,)
    )
    if not user_result:
        flash('That user account no longer exists.')
        return redirect('/admin')
    user = user_result[0]

    if request.method == 'POST':
        firstname = request.form.get('firstname', '').strip()
        lastname = request.form.get('lastname', '').strip()
        email = request.form.get('email', '').strip().lower()
        permission = request.form.get('permission', '')
        status = request.form.get('status', '').strip()[:120]
        allowed_permissions = {'admin', 'User (Renter)', 'User (Tool Provider)'}

        if not all((firstname, lastname, email)) or permission not in allowed_permissions:
            flash('Enter a first name, last name, email, and valid account role.')
            user.update({'firstname': firstname, 'lastname': lastname, 'email': email, 'permission': permission, 'status': status})
            return render_template('admin_user_edit.html', user=user)
        if user_id == session['userid'] and permission != 'admin':
            flash('You cannot remove your own administrator access.')
            return render_template('admin_user_edit.html', user=user)
        if DATABASE.ViewQuery("SELECT userid FROM users WHERE email = ? AND userid != ?", (email, user_id)):
            flash('That email address is already used by another account.')
            return render_template('admin_user_edit.html', user=user)

        updated = DATABASE.ModifyQuery(
            "UPDATE users SET firstname = ?, lastname = ?, email = ?, permission = ?, status = ? WHERE userid = ?",
            (firstname, lastname, email, permission, status or None, user_id)
        )
        flash('User account updated.' if updated else 'User account could not be updated.')
        return redirect(url_for('admin_user_edit', user_id=user_id))

    return render_template('admin_user_edit.html', user=user)

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
        tool_data, error = read_tool_form()
        if error:
            flash(error)
        else:
            tool_photo_path = save_uploaded_image(request.files.get('toolphoto'), TOOL_UPLOAD_FOLDER, f"tool_{session['userid']}")
            if not tool_photo_path:
                flash('A tool photo is required. Please upload a PNG, JPG, JPEG, or GIF image.')
                tools = DATABASE.ViewQuery("SELECT * FROM tools WHERE providerid = ? ORDER BY toolid DESC", (session['userid'],)) or []
                return render_template('provider_listings.html', tools=tools)
            created = DATABASE.ModifyQuery(
                """INSERT INTO tools (providerid, title, description, daily_rate, original_value, city, suburb, location, tool_type, brand, tool_condition, toolphoto, available_from, available_until)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session['userid'], tool_data['title'], tool_data['description'], tool_data['daily_rate'], tool_data['original_value'], tool_data['city'], tool_data['suburb'], tool_data['location'], tool_data['tool_type'], tool_data['brand'], tool_data['tool_condition'], tool_photo_path, tool_data['available_from'], tool_data['available_until'])
            )
            if not created:
                os.remove(tool_photo_path)
                flash('Your tool could not be added. Please try again.')
                return redirect('/provider/listings')
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
        tool_data, error = read_tool_form()
        if error:
            flash(error)
            return render_template('provider_edit_listing.html', tool=tool)

        tool_photo_path = tool['toolphoto']
        tool_photo = request.files.get('toolphoto')
        if tool_photo and tool_photo.filename:
            tool_photo_path = save_uploaded_image(tool_photo, TOOL_UPLOAD_FOLDER, f"tool_{session['userid']}")
            if not tool_photo_path:
                flash('Tool photos must be PNG, JPG, JPEG, or GIF files.')
                return render_template('provider_edit_listing.html', tool=tool)

        DATABASE.ModifyQuery(
            """UPDATE tools SET title = ?, description = ?, daily_rate = ?, original_value = ?, city = ?, suburb = ?, location = ?, tool_type = ?, brand = ?, tool_condition = ?, toolphoto = ?, available_from = ?, available_until = ?
               WHERE toolid = ? AND providerid = ?""",
            (tool_data['title'], tool_data['description'], tool_data['daily_rate'], tool_data['original_value'], tool_data['city'], tool_data['suburb'], tool_data['location'], tool_data['tool_type'], tool_data['brand'], tool_data['tool_condition'], tool_photo_path, tool_data['available_from'], tool_data['available_until'], tool_id, session['userid'])
        )
        flash('Your tool listing has been updated.')
        return redirect('/provider/listings')

    return render_template('provider_edit_listing.html', tool=tool)

@app.route('/provider/listings/<int:tool_id>/remove', methods=['POST'])
def provider_remove_listing(tool_id):
    if not provider_only():
        return redirect('./')
    active_rental = DATABASE.ViewQuery(
        "SELECT rentalid FROM tool_rentals WHERE toolid = ? AND status = 'active'", (tool_id,)
    )
    if active_rental:
        flash('This listing cannot be taken down while it has an active rental.')
    else:
        DATABASE.ModifyQuery("DELETE FROM tools WHERE toolid = ? AND providerid = ?", (tool_id, session['userid']))
        flash('Your listing has been taken down.')
    return redirect('/provider/listings')

@app.route('/provider/active-rentals', methods=['GET', 'POST'])
def provider_active_rentals():
    if not provider_only():
        return redirect('./')
    if request.method == 'POST':
        rental_id = request.form.get('rentalid', type=int)
        rental = DATABASE.ViewQuery("SELECT toolid FROM tool_rentals WHERE rentalid = ? AND providerid = ? AND status = 'active'", (rental_id, session['userid']))
        if rental:
            completed = DATABASE.ModifyMany([
                ("UPDATE tool_rentals SET status = 'completed', completed_at = datetime('now','localtime') WHERE rentalid = ? AND providerid = ? AND status = 'active'", (rental_id, session['userid'])),
                ("UPDATE tools SET is_available = 1 WHERE toolid = ?", (rental[0]['toolid'],))
            ])
            flash('Rental marked as completed.' if completed else 'Could not complete that rental. Please try again.')
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


def member_only():
    """Return True for the two account types that can use Toolly messages."""
    return session.get('permission') in ('User (Renter)', 'User (Tool Provider)') and 'userid' in session


def open_conversation(tool_id, renter_id, provider_id):
    """Create one conversation per renter/provider/tool combination."""
    DATABASE.ModifyQuery(
        "INSERT OR IGNORE INTO conversations (toolid, renterid, providerid) VALUES (?, ?, ?)",
        (tool_id, renter_id, provider_id)
    )
    return DATABASE.ViewQuery(
        "SELECT conversationid FROM conversations WHERE toolid = ? AND renterid = ? AND providerid = ?",
        (tool_id, renter_id, provider_id)
    )


@app.route('/messages/start/tool/<int:tool_id>', methods=['POST'])
def start_tool_conversation(tool_id):
    """Let a renter contact the provider directly from a listing."""
    if not renter_only():
        return redirect('./')
    tool = DATABASE.ViewQuery("SELECT providerid FROM tools WHERE toolid = ?", (tool_id,))
    if not tool:
        flash('That tool listing is no longer available.')
        return redirect('/renter/browse')
    conversation = open_conversation(tool_id, session['userid'], tool[0]['providerid'])
    if conversation:
        return redirect(url_for('messages', conversation=conversation[0]['conversationid']))
    flash('Conversation could not be opened. Please try again.')
    return redirect('/renter/browse')


@app.route('/messages/start/rental/<int:rental_id>', methods=['POST'])
def start_rental_conversation(rental_id):
    """Allow either party in an active rental to contact the other."""
    if not member_only():
        return redirect('./')
    rental = DATABASE.ViewQuery(
        "SELECT toolid, renterid, providerid FROM tool_rentals WHERE rentalid = ? AND (renterid = ? OR providerid = ?)",
        (rental_id, session['userid'], session['userid'])
    )
    if not rental:
        flash('You do not have access to that rental conversation.')
        return redirect('/home')
    conversation = open_conversation(rental[0]['toolid'], rental[0]['renterid'], rental[0]['providerid'])
    if conversation:
        return redirect(url_for('messages', conversation=conversation[0]['conversationid']))
    flash('Conversation could not be opened. Please try again.')
    return redirect('/home')


@app.route('/messages', methods=['GET', 'POST'])
def messages():
    """Show the signed-in member's conversations and save their new messages."""
    if not member_only():
        return redirect('./')

    user_id = session['userid']
    conversations = DATABASE.ViewQuery(
        """SELECT conversations.*, tools.title,
                  CASE WHEN conversations.renterid = ?
                       THEN provider.firstname || ' ' || provider.lastname
                       ELSE renter.firstname || ' ' || renter.lastname END AS other_member
           FROM conversations
           JOIN tools ON tools.toolid = conversations.toolid
           JOIN users AS renter ON renter.userid = conversations.renterid
           JOIN users AS provider ON provider.userid = conversations.providerid
           WHERE conversations.renterid = ? OR conversations.providerid = ?
           ORDER BY conversations.last_message_at DESC, conversations.conversationid DESC""",
        (user_id, user_id, user_id)
    ) or []
    selected_id = request.values.get('conversation', type=int)
    if not selected_id and conversations:
        selected_id = conversations[0]['conversationid']
    selected = next((item for item in conversations if item['conversationid'] == selected_id), None)

    if request.method == 'POST':
        message_text = request.form.get('message_text', '').strip()
        if not selected:
            flash('Choose a conversation before sending a message.')
        elif not message_text or len(message_text) > 1000:
            flash('Messages must be between 1 and 1,000 characters.')
        else:
            saved = DATABASE.ModifyMany([
                ("INSERT INTO messages (conversationid, author, authorid, messagetext, created_at) VALUES (?, ?, ?, ?, datetime('now','localtime'))",
                 (selected_id, user_id, user_id, message_text)),
                ("UPDATE conversations SET last_message_at = datetime('now','localtime') WHERE conversationid = ?", (selected_id,))
            ])
            flash('Message sent.' if saved else 'Your message could not be sent. Please try again.')
        return redirect(url_for('messages', conversation=selected_id) if selected_id else url_for('messages'))

    chat_messages = []
    if selected:
        chat_messages = DATABASE.ViewQuery(
            """SELECT messages.*, users.firstname || ' ' || users.lastname AS author_name
               FROM messages JOIN users ON users.userid = messages.authorid
               WHERE messages.conversationid = ? ORDER BY messages.messageid ASC""",
            (selected_id,)
        ) or []
    return render_template('messages.html', conversations=conversations, selected=selected, chat_messages=chat_messages)

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
            return redirect(url_for('renter_book_tool', tool_id=tool_id))
        elif tool and request.form.get('action') == 'message':
            conversation = open_conversation(tool_id, session['userid'], tool[0]['providerid'])
            if conversation:
                return redirect(url_for('messages', conversation=conversation[0]['conversationid']))
            flash('Conversation could not be opened. Please try again.')
        return redirect('/renter/browse')
    filters = {key: request.args.get(key, '').strip() for key in ('city', 'suburb', 'tool_type', 'brand', 'tool_condition', 'available_on')}
    max_price = request.args.get('max_price', '').strip()
    show_unavailable = request.args.get('show_unavailable') == '1'
    query = "SELECT tools.*, users.firstname || ' ' || users.lastname AS provider_name FROM tools JOIN users ON users.userid = tools.providerid WHERE 1 = 1"
    params = []
    for field in ('city', 'suburb', 'tool_type', 'brand', 'tool_condition'):
        if filters[field]:
            if field in ('city', 'suburb', 'tool_condition'):
                # These are controlled dropdown values, so equality is faster
                # and lets SQLite use the location/filter indexes.
                query += f" AND tools.{field} = ?"
                params.append(filters[field])
            else:
                # Tool type and brand remain partial text searches.
                query += f" AND lower(tools.{field}) LIKE ?"
                params.append('%' + filters[field].lower() + '%')
    if max_price:
        try:
            query += " AND tools.daily_rate <= ?"
            params.append(float(max_price))
        except ValueError:
            flash('Maximum price must be a number.')
    if filters['available_on']:
        try:
            available_on = date.fromisoformat(filters['available_on']).isoformat()
            query += " AND tools.available_from <= ? AND tools.available_until >= ?"
            params.extend([available_on, available_on])
        except ValueError:
            flash('Availability date must be valid.')
    if not show_unavailable:
        query += " AND tools.is_available = 1"
    query += " ORDER BY tools.toolid DESC"
    tools = DATABASE.ViewQuery(query, tuple(params)) or []
    return render_template('renter_browse.html', tools=tools, filters=filters, max_price=max_price, show_unavailable=show_unavailable)

@app.route('/renter/tools/<int:tool_id>/book', methods=['GET', 'POST'])
def renter_book_tool(tool_id):
    if not renter_only():
        return redirect('./')
    tool_result = DATABASE.ViewQuery("SELECT * FROM tools WHERE toolid = ? AND is_available = 1", (tool_id,))
    if not tool_result:
        flash('This tool is no longer available.')
        return redirect('/renter/browse')
    tool = tool_result[0]
    if request.method == 'POST':
        try:
            start_date = date.fromisoformat(request.form['start_date'])
            end_date = date.fromisoformat(request.form['end_date'])
            available_from = date.fromisoformat(tool['available_from'])
            available_until = date.fromisoformat(tool['available_until'])
        except ValueError:
            flash('Choose valid rental dates.')
            return render_template('renter_booking.html', tool=tool)
        if start_date > end_date or start_date < available_from or end_date > available_until:
            flash('Choose dates within the provider’s available period.')
            return render_template('renter_booking.html', tool=tool)
        rental_days = (end_date - start_date).days + 1
        rental_cost = tool['daily_rate'] * rental_days
        security_deposit = tool['original_value'] * 0.10
        insurance_selected = 1 if request.form.get('insurance') else 0
        insurance_cost = (5 * (2 ** max(0, int((tool['original_value'] - 0.01) // 100)))) if insurance_selected else 0
        total = rental_cost + security_deposit + insurance_cost
        booked = DATABASE.ModifyMany([
            ("""INSERT INTO tool_rentals (toolid, renterid, providerid, total, start_date, end_date, rental_days, rental_cost, security_deposit, insurance_selected, insurance_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
             (tool_id, session['userid'], tool['providerid'], total, start_date.isoformat(), end_date.isoformat(), rental_days, rental_cost, security_deposit, insurance_selected, insurance_cost)),
            ("UPDATE tools SET is_available = 0 WHERE toolid = ?", (tool_id,))
        ])
        flash('Booking confirmed. Your simulated payment has been recorded.' if booked else 'Your booking could not be saved. Please try again.')
        if not booked:
            return render_template('renter_booking.html', tool=tool)
        return redirect('/renter/rentals')
    return render_template('renter_booking.html', tool=tool)

@app.route('/renter/rentals', methods=['GET', 'POST'])
def renter_rentals():
    if not renter_only():
        return redirect('./')
    if request.method == 'POST':
        rental_id = request.form.get('rentalid', type=int)
        rental = DATABASE.ViewQuery(
            "SELECT toolid FROM tool_rentals WHERE rentalid = ? AND renterid = ? AND status = 'active'",
            (rental_id, session['userid'])
        )
        if rental:
            cancelled = DATABASE.ModifyMany([
                ("DELETE FROM tool_rentals WHERE rentalid = ? AND renterid = ?", (rental_id, session['userid'])),
                ("UPDATE tools SET is_available = 1 WHERE toolid = ?", (rental[0]['toolid'],))
            ])
            flash('Your rental has been cancelled and the tool is available again.' if cancelled else 'Your rental could not be cancelled. Please try again.')
        return redirect('/renter/rentals')
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
        firstname = request.form.get('fname', '').strip()
        lastname = request.form.get('lname', '').strip()
        email = request.form.get('email', '').strip().lower()

        if not all((firstname, lastname, email)):
            flash('First name, last name, and email are required.')
            return render_template('profile.html', user=user)

        existing_email = DATABASE.ViewQuery(
            "SELECT userid FROM users WHERE email = ? AND userid != ?", (email, user_id)
        )
        if existing_email:
            flash('That email address is already in use.')
            return render_template('profile.html', user=user)

        filepath = user['profilephoto'] or ''
        file = request.files.get('file')
        if file and file.filename:
            filepath = save_uploaded_image(file, UPLOAD_FOLDER, 'profile')
            if not filepath:
                flash('Please upload a PNG, JPG, JPEG, or GIF image.')
                return render_template('profile.html', user=user)

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
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
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
        message = create_account("User (Renter)")
        if message is None:
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
        message = create_account("User (Tool Provider)")
        if message is None:
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
