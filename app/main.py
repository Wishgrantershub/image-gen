from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.routers import auth, children, books, stories, images

app = FastAPI(
    title="Diffrun Clone API",
    description="Personalized Storybook Generation API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(children.router)
app.include_router(books.router)
app.include_router(stories.router)
app.include_router(images.router)

@app.on_event("startup")
def on_startup():
    init_db()
    print("Database initialized")

@app.get("/")
def root():
    return {"message": "Diffrun Clone API", "status": "running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True
    )