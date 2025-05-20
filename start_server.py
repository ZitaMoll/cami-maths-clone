from app import app, db
with app.app_context():
    db.drop_all()
    db.create_all()
    print("✅ Database reset")

# Start the Flask app after resetting DB
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)