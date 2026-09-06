#----------------------------------------------------------------------------
# This Database class provides an interface to the database
# It's therefore easier to simply inherit the code..
# Created by Brad Nielsen 2019
#-----------------------------------------------------------------------#
import sqlite3
import logging

 # Create the database by DATABASE = DatabaseInterface("test.sqlite")
class Database:

    #location is the sqlitedatabase file
    def __init__(self, location="", log=None):
        self.location = location
        self.logger = log or logging.getLogger(__name__)

    # Returns a handle to the Database connection
    def connect(self):
        # A small timeout prevents "database is locked" errors when two local
        # browser requests arrive at nearly the same time.
        connection = sqlite3.connect(self.location, timeout=10)
        # SQLite enforces foreign keys per connection, not globally per file.
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.row_factory = sqlite3.Row #configures database queries to return a list of dictionaries (each row/record) [{"field1":value1,"field2":value2...},{etc},{} ]
        return connection

    # A helper function to save time and also log sql errors
    # Write your Select Query, and pass in a Tuple (a,b,c etc) representing any parameters
    # If you only have one param, you still need to use a Tuple .e.g (userid,)
    def ViewQuery(self, query, params=None):
        connection = self.connect()
        try:
            cursor = connection.execute(query, params or ())
            result = cursor.fetchall()
            return [dict(row) for row in result] if result else False
        except sqlite3.Error as error:
            self.logger.exception("Database read failed: %s | SQL: %s", error, query)
            return False
        finally:
            connection.close()

    # Created a helper function so to save time and also log results
    # Write your DELETE, INSERT, UPDATE Query, and pass in a Tuple(a,b,c etc ) representing any parameters
    def ModifyQuery(self, query, params=None):
        connection = self.connect()
        try:
            with connection:
                connection.execute(query, params or ())
            return True
        except sqlite3.Error as error:
            self.logger.exception("Database write failed: %s | SQL: %s", error, query)
            return False
        finally:
            connection.close()

    def ModifyMany(self, statements):
        """Run related writes as one all-or-nothing database transaction.

        ``statements`` is an iterable of ``(sql, parameters)`` pairs.  This is
        used for actions such as creating a rental and marking its tool busy.
        """
        connection = self.connect()
        try:
            with connection:
                for query, params in statements:
                    connection.execute(query, params or ())
            return True
        except sqlite3.Error as error:
            self.logger.exception("Database transaction failed: %s", error)
            return False
        finally:
            connection.close()

    def log(self, message):
        self.logger.info(message)
        return

    def log_error(self, error):
        self.logger.error(error)
        return
