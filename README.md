# Diffrun Clone - Backend

AI-powered personalized children's storybook generation system.

## Prerequisites

- Python 3.11+
- NVIDIA GPU with CUDA support (4GB+ VRAM recommended)
- Gemini API Key

## Setup

### 1. Create virtual environment

```powershell
cd C:\Users\prabhakar\Desktop\Projects(Zerzura)\diffrun_clone\backend
python -m venv venv
```

### 2. Activate virtual environment

```powershell
# PowerShell
.\venv\Scripts\Activate.ps1

# Command Prompt
venv\Scripts\activate.bat
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Configure environment

Copy `.env.example` to `.env` and add your settings:

```powershell
copy .env.example .env
```

Edit `.env` file and add:
- `GEMINI_API_KEY=your_gemini_api_key`

## Running the Application

### Start the backend server

```powershell
python -m app.main
```

Or using uvicorn directly:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login (returns JWT token)
- `GET /api/auth/me` - Get current user info

### Children
- `POST /api/children/` - Create child profile with photo
- `GET /api/children/` - List user's children
- `GET /api/children/{id}` - Get child details
- `PUT /api/children/{id}` - Update child info
- `DELETE /api/children/{id}` - Delete child

### Books
- `GET /api/books/` - List available books
- `GET /api/books/{id}` - Get book details

### Stories
- `POST /api/stories/` - Create and generate new story
- `GET /api/stories/` - List user's stories
- `GET /api/stories/{id}` - Get story details
- `GET /api/stories/{id}/preview` - Get preview pages
- `PUT /api/stories/{id}` - Update story
- `DELETE /api/stories/{id}` - Delete story

### Images
- `GET /api/images/{page_id}` - Get generated page image

## Example Usage

### 1. Register a user
```powershell
curl -X POST http://localhost:8000/api/auth/register `
  -H "Content-Type: application/json" `
  -d '{"email":"test@example.com","password":"password123","full_name":"Test User"}'
```

### 2. Login
```powershell
curl -X POST http://localhost:8000/api/auth/login `
  -H "Content-Type: application/x-www-form-urlencoded" `
  -d "username=test@example.com&password=password123"
```

### 3. Create child profile (with photo)
```powershell
# Use multipart/form-data
curl -X POST http://localhost:8000/api/children/ `
  -H "Authorization: Bearer YOUR_TOKEN" `
  -F "name=Alice" `
  -F "gender=female" `
  -F "age=5" `
  -F "photo=@photo.jpg"
```

### 4. List books
```powershell
curl -X GET http://localhost:8000/api/books/ `
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 5. Create story
```powershell
curl -X POST http://localhost:8000/api/stories/ `
  -H "Authorization: Bearer YOUR_TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"child_id":1,"book_id":1}'
```

## Project Structure

```
backend/
├── app/
│   ├── main.py           # FastAPI entry point
│   ├── config.py         # Settings & configuration
│   ├── database.py       # SQLite database setup
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── routers/          # API endpoints
│   └── services/         # Business logic
│       ├── auth_service.py
│       ├── ai_service.py
│       └── story_service.py
├── uploads/              # User uploaded photos
├── output/               # Generated images
├── models/               # ML model files
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
└── README.md           # This file
```

## Troubleshooting

### Out of VRAM
If you get CUDA out of memory errors:
- Reduce image resolution in `ai_service.py`
- Use CPU for image generation (slower but works)
- Reduce `num_inference_steps`

### InsightFace errors
If face embedding fails:
- Ensure clear, frontal face photo
- Photo must contain detectable face

### Gemini API errors
- Verify API key in `.env`
- Check API quota on Google AI Studio