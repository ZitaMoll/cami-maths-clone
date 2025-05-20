from app import app, db
with app.app_context():
    db.drop_all()   # This clears the broken DB
    db.create_all() # This rebuilds the tables
    print("Database reset and tables created.")