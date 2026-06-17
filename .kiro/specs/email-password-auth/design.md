# Design Document — Email + Password Authentication

## Overview

This design replaces the two-step OTP flow with a single-step email + password system. The backend `AuthService` already has `register_with_password()` and `authenticate_with_password()` fully implemented — they just need new API routes wired up. On the frontend, the multi-step OTP forms are replaced with flat, single-screen forms, and the `AuthProvider` context is updated to expose password-based `register` and `login` functions.

Session management (JWT access token + opaque refresh token, automatic token refresh, logout revocation) is **unchanged**.

---

## Architecture

```
Frontend                           Backend
────────────────────────────────   ────────────────────────────────
SignUpForm        ──POST /auth/register──▶  Auth_Router
  (name/email/pw)                              │
SignInForm        ──POST /auth/login────▶      │
  (email/pw)                                   ▼
                                        AuthService
AuthProvider                              register_with_password()
  register()                              authenticate_with_password()
  login()                                   │
  logout()  ──POST /auth/logout────▶        │
  (token refresh unchanged)             DB (users, refresh_tokens)
```

---

## Backend Changes

### 1. New Pydantic Schemas — `schemas/auth.py`

Add two new request schemas alongside the existing OTP schemas. The existing `TokenResponse` is reused unchanged.

```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    display_name: Optional[str] = Field(None, max_length=100)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
```

**Why here**: `schemas/auth.py` already owns all auth request/response types. Adding here keeps the pattern consistent and gets FastAPI auto-docs for free.

### 2. New Route Handlers — `routes/auth.py`

Add two endpoints, keeping the existing OTP endpoints untouched (they can be removed in a follow-up cleanup, but removing them now is out of scope and risks breaking other parts of the app).

#### `POST /auth/register`

```
Request:  RegisterRequest
Response: TokenResponse (HTTP 200)
Errors:
  409  — email already exists (ValueError from register_with_password)
  422  — Pydantic validation failure (password < 8 chars, bad email)
```

Implementation pattern:
```python
@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = auth_service.register_with_password(
            db, request.email, request.password, request.display_name
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    
    access_token, refresh_token, expires_in = auth_service._create_token_pair(db, user)
    db.commit()
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse(...)
    )
```

Note: `register_with_password()` already sets `email_verified=True` and creates the password hash — no additional logic needed.

#### `POST /auth/login`

```
Request:  LoginRequest
Response: TokenResponse (HTTP 200)
Errors:
  401  — wrong email or password ("Invalid email or password")
  403  — account inactive
```

Implementation pattern:
```python
@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    try:
        user, access_token, refresh_token, expires_in = (
            auth_service.authenticate_with_password(db, request.email, request.password)
        )
    except ValueError as e:
        msg = str(e)
        status_code = 403 if "inactive" in msg else 401
        raise HTTPException(status_code=status_code, detail=msg)
    
    db.commit()
    return TokenResponse(...)
```

Note: `authenticate_with_password()` already handles bcrypt verification, `last_login_at` update, and token pair generation — the route handler is thin.

### 3. Error Discrimination

`authenticate_with_password()` raises `ValueError` for both "wrong password" and "inactive account". The router distinguishes them by checking whether "inactive" appears in the message, mapping to 403 vs 401 respectively. This avoids changing the service method signature.

---

## Frontend Changes

### 4. API Client — `lib/api.ts`

Add two new methods to the `ApiClient` class alongside the existing OTP methods:

```typescript
register(email: string, password: string, displayName?: string): Promise<AuthResponse>
loginWithPassword(email: string, password: string): Promise<AuthResponse>
```

Both methods use the existing `this.request<AuthResponse>(...)` wrapper, which already handles non-2xx errors by throwing `ApiError`. No changes to `ApiError` or `request()` are needed.

The existing `requestOtp` and `verifyOtp` methods are left in place (they're still wired to live endpoints).

### 5. Auth Provider — `providers/auth-provider.tsx`

**Interface changes:**

| Remove (OTP-based) | Add (password-based) |
|---|---|
| `login(email, otp)` | `login(email, password)` |
| `signup(email, otp, displayName?)` | `register(email, password, displayName?)` |
| `requestOtp(email, purpose)` | — |

The `logout`, `refreshUser`, `isAuthenticated`, `user`, and `isLoading` members are **unchanged**.

**New function implementations:**

```typescript
const register = useCallback(async (email, password, displayName?) => {
  const res = await api.register(email, password, displayName);
  setTokens(res.access_token, res.refresh_token);
  setUser(res.user);
  setStoredUser(res.user);
  router.push("/dashboard");
}, [router]);

const login = useCallback(async (email, password) => {
  const res = await api.loginWithPassword(email, password);
  setTokens(res.access_token, res.refresh_token);
  setUser(res.user);
  setStoredUser(res.user);
  router.push("/dashboard");
}, [router]);
```

Errors from `api.register` / `api.loginWithPassword` propagate to callers unchanged — `AuthProvider` does not swallow them.

The bootstrap `useEffect` (token refresh on mount), `logout`, and `refreshUser` are untouched — session continuity is preserved.

### 6. Sign-Up Form — `components/auth/sign-up-form.tsx`

**Full rewrite** of the component. The multi-step OTP flow is replaced with a single flat form.

**Form schema (zod):**
```typescript
const schema = z.object({
  displayName: z.string().min(2).max(100),
  email: z.string().email(),
  password: z.string().min(8, "Password must be at least 8 characters"),
});
```

**Fields rendered (all on one screen):**
1. Full Name (`displayName`) — text input with User icon
2. Email Address (`email`) — email input with Mail icon
3. Password (`password`) — password input with Lock icon + show/hide toggle
4. Password strength indicator — evaluated in real time against the `password` field value

**Password strength indicator:**
- Evaluated client-side with a simple heuristic: length ≥ 8 = weak, + mixed case = medium, + number + symbol = strong
- Rendered as a 3-segment bar (red → yellow → green) below the password field
- Updates on every keystroke via `watch("password")`

**Submit flow:**
1. Zod validates on submit — password < 8 chars shows inline error below password field, no network request
2. Button enters loading state (`isLoading = true`)
3. Calls `auth.register(email, password, displayName)`
4. On success: `AuthProvider` navigates to `/dashboard`
5. On `ApiError` with status 409: show error below email field
6. On other errors: show error below the form

**Removed entirely:** `OtpInput`, `CountdownTimer`, step state, resend logic, all OTP-related imports.

### 7. Sign-In Form — `components/auth/sign-in-form.tsx`

**Full rewrite** of the component. Single-screen, two fields.

**Form schema (zod):**
```typescript
const schema = z.object({
  email: z.string().email(),
  password: z.string().min(1, "Password is required"),
});
```

**Fields rendered:**
1. Email Address — email input with Mail icon
2. Password — password input with Lock icon + show/hide toggle (Eye / EyeOff icons)

**Submit flow:**
1. Both fields must be populated (zod enforces)
2. Button enters loading state
3. Calls `auth.login(email, password)`
4. On success: `AuthProvider` navigates to `/dashboard`
5. On `ApiError` with status 401: display "Invalid email or password" below the form, email field is **not** cleared
6. On other errors: display error message below the form

**Removed entirely:** step state, OTP input, countdown timer, resend logic.

---

## Data Flow Diagrams

### Registration

```
User fills form → zod validates → auth.register(email, pw, name)
  → api.register POST /auth/register
    → AuthService.register_with_password()
      → hash password (bcrypt)
      → INSERT user (email_verified=true)
      → _create_token_pair()
    → return TokenResponse
  → setTokens() + setUser() + router.push("/dashboard")
```

### Login

```
User fills form → zod validates → auth.login(email, pw)
  → api.loginWithPassword POST /auth/login
    → AuthService.authenticate_with_password()
      → lookup user by email
      → verify_password() (bcrypt)
      → update last_login_at
      → _create_token_pair()
    → return TokenResponse
  → setTokens() + setUser() + router.push("/dashboard")
```

### Token Refresh (unchanged)

```
API request → token expired → api.refreshToken(refresh_token)
  → POST /auth/refresh → new access_token
  → retry original request
```

---

## Component Dependency Map

```
sign-up-form.tsx
  → useAuth()  (register)
  → react-hook-form + zod
  → lucide-react (User, Mail, Lock, Eye, EyeOff, Loader2)
  → @/components/ui/button, input, label

sign-in-form.tsx
  → useAuth()  (login)
  → react-hook-form + zod
  → lucide-react (Mail, Lock, Eye, EyeOff, Loader2)
  → @/components/ui/button, input, label

auth-provider.tsx
  → api.register, api.loginWithPassword
  → lib/auth (setTokens, clearTokens, getStoredUser, ...)
  → next/navigation (useRouter)

lib/api.ts
  → POST /auth/register
  → POST /auth/login
  (existing: POST /auth/refresh, POST /auth/logout, GET /auth/me)
```

---

## Files to Create or Modify

| File | Action | What changes |
|------|--------|-------------|
| `apps/api-gateway/schemas/auth.py` | Modify | Add `RegisterRequest`, `LoginRequest` |
| `apps/api-gateway/routes/auth.py` | Modify | Add `POST /register`, `POST /login` handlers; import new schemas |
| `apps/web/src/lib/api.ts` | Modify | Add `register()`, `loginWithPassword()` methods |
| `apps/web/src/providers/auth-provider.tsx` | Modify | Replace OTP functions with `register`, `login`; update context interface |
| `apps/web/src/components/auth/sign-up-form.tsx` | Rewrite | Single-screen form with password field + strength indicator |
| `apps/web/src/components/auth/sign-in-form.tsx` | Rewrite | Single-screen form with password field + show/hide toggle |

No new files need to be created. No database migrations are needed — the `password_hash` column already exists on the `users` table (confirmed in `register_with_password()` which sets it).

---

## What Is Explicitly Out of Scope

- Removing the existing OTP endpoints (`/request-otp`, `/verify-otp`) — they remain to avoid breaking anything dependent on them
- Password reset / forgot password flow
- Email verification emails
- Rate limiting on the new endpoints (the existing `rate_limit_dependency` can be added later)
