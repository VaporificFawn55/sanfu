# Sanfu Data Collection App

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/Fr4cas/sanfu
   cd sanfu

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   .venv\Scripts\Activate.ps1  # Windows PowerShell

3. Install backend dependencies:
   ```bash
   pip install -r backend/requirements.txt

4. Run the backend server:
   ```bash
   cd backend
   uvicorn app:app --reload

5. Install frontend dependencies:
   ```bash
   cd frontend
   npm install

6. Run frontend server:
   ```bash
   npm run dev