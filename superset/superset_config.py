import os
SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "oil_superset_secret_key_change_me")
SQLALCHEMY_DATABASE_URI = "sqlite:////app/superset_home/superset.db"
FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": True,
}
