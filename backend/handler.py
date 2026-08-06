"""AWS Lambda handler — wraps the FastAPI app with Mangum for ASGI/Lambda compatibility."""

from mangum import Mangum

try:
    from backend.main import app
except ImportError:
    from main import app

handler = Mangum(app)
