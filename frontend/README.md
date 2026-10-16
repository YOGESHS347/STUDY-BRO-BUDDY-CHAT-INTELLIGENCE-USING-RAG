# Document Intelligence RAG — Frontend Foundation (Phase 8)

Production-ready React 19 + TypeScript frontend for the Document Intelligence RAG application. Built with Vite, React Router, and Supabase Auth.

---

## Architecture Overview

- **Framework**: React 19, TypeScript, Vite
- **Routing**: React Router 7 (`/login`, `/signup`, `/dashboard`, `/*`)
- **Authentication**: Supabase Auth JS SDK (`@supabase/supabase-js`)
- **Token Handling**: Automatic Bearer token extraction and injection via centralized `apiClient`
- **Backend API**: FastAPI backend running on port 8000
- **Security**: Asymmetric ES256 JWT tokens validated by FastAPI backend using Supabase JWKS; zero backend secrets stored in frontend

---

## Prerequisites

- Node.js >= 18.0.0 (tested on v24.15.0)
- npm >= 9.0.0 (tested on v11.12.1)
- FastAPI Backend running on `http://localhost:8000`

---

## Environment Configuration

Create a `.env` file in the `frontend` root directory based on `.env.example`:

```bash
# FastAPI Backend URL
VITE_API_BASE_URL=http://localhost:8000

# Supabase Public Auth Configuration (Safe for client-side exposure)
VITE_SUPABASE_URL=https://<your-project-ref>.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_<your-key>
```

> **IMPORTANT**: Never include `SUPABASE_SECRET_KEY`, `DATABASE_URL`, or `QDRANT_API_KEY` in frontend environment variables. The publishable key is public and client-safe.

---

## Installation & Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

The development server runs by default on `http://localhost:5173`.

---

## Routes

| Route | Access | Description |
|---|---|---|
| `/` | Public / Smart Redirect | Redirects to `/dashboard` if authenticated, else `/login` |
| `/login` | Public Only | Email/password sign-in; redirects to `/dashboard` if authenticated |
| `/signup` | Public Only | Account creation with email confirmation support |
| `/dashboard` | Protected | Main application shell with sidebar, live backend health, and user profile |
| `/*` | Public | 404 Not Found fallback |

---

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── common/             # Button, Input, Badge, LoadingSpinner
│   │   └── layout/             # Sidebar, Header, DashboardLayout
│   ├── context/
│   │   └── AuthContext.tsx     # Supabase session provider & listener
│   ├── hooks/
│   │   └── useAuth.ts          # useAuth custom hook
│   ├── pages/
│   │   ├── Login.tsx           # Authentication login page
│   │   ├── Signup.tsx          # Authentication signup page
│   │   ├── Dashboard.tsx       # Main dashboard overview
│   │   └── NotFound.tsx        # 404 page
│   ├── routes/
│   │   ├── ProtectedRoute.tsx  # Route guard redirecting to /login
│   │   └── PublicOnlyRoute.tsx # Route guard redirecting to /dashboard
│   ├── services/
│   │   ├── api.ts              # Centralized Fetch wrapper attaching Bearer tokens
│   │   └── supabase.ts         # Supabase client initialization
│   ├── styles/
│   │   └── index.css           # Design system tokens and styles
│   ├── types/
│   │   ├── api.ts              # API contracts & response types
│   │   └── auth.ts             # Auth models & context interfaces
│   ├── App.tsx                 # Root application router
│   └── main.tsx                # Entry point
├── .env.example
├── .gitignore
├── package.json
├── tsconfig.json
└── vite.config.ts
```
