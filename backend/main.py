import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.controller.router import api_router

app = FastAPI()


_default_origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]
_extra = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra,

    allow_origin_regex=r"https?://[^/]+:8080",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router=api_router, prefix="")
