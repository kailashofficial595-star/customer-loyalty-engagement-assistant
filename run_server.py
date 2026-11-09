import sys
import os
import uvicorn

# Ensure repository root is on sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"=================================================================")
    print(f" HCLTech Hackathon: Customer Loyalty and Engagement Assistant")
    print(f" Starting server at: http://{host}:{port}")
    print(f" Interactive Swagger API Docs at: http://{host}:{port}/docs")
    print(f"=================================================================")
    uvicorn.run("backend.main:app", host=host, port=port, reload=False)
