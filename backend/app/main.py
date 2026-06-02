from fastapi import FastAPI
from api.v1.routes import router
from fastapi.middleware.cors import CORSMiddleware
 
app = FastAPI(title="하이디플 B2B 매칭 시스템", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(router)