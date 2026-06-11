from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.routes import router


app = FastAPI(title="HIDIPL B2B Matching API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

app.include_router(router)
