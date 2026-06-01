from fastapi import FastAPI
from api.v1.routes import router
 
app = FastAPI(title="하이디플 B2B 매칭 시스템", version="0.1.0")
app.include_router(router)