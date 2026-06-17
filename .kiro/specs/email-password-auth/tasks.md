# Implementation Plan: Email + Password Authentication

## Overview

Replace the OTP-based auth flow with classic email + password. The backend `AuthService` already has `register_with_password()` and `authenticate_with_password()` fully implemented — the work is wiring new API routes, adding Pydantic schemas, updating the frontend API client and auth provider, and rewriting the two auth forms. Tasks are ordered backend-first (schemas → routes → tests → PBT), then frontend (API client → auth provider → forms).

## Task Dependency Graph

```json
{
  "waves": [
    {
      "wave": 1,
      "tasks": ["1", "6"],
      "description": "Foundation: backend schemas and frontend API client methods — no dependencies, can run in parallel"
    },
    {
      "wave": 2,
      "tasks": ["2", "3", "7"],
      "description": "Routes and auth provider — depend on schemas (1) and API client (6) respectively"
    },
    {
      "wave": 3,
      "tasks": ["4", "8", "9"],
      "description": "Tests for backend routes (depends on 2, 3) and UI forms (depend on auth provider 7)"
    },
    {
      "wave": 4,
      "tasks": ["5"],
      "description": "Property-based tests — depend on all backend tasks (1, 2, 3, 4) being complete"
    }
  ]
}
```

## Tasks

- [x] 1. Add `RegisterRequest` and `LoginRequest` schemas to `schemas/auth.py`
  - Open `apps/api-gateway/schemas/auth.py`
  - Add `RegisterRequest` with fields: `email: EmailStr`, `password: str = Field(..., min_length=8)`, `display_name: Optional[str] = Field(None, max_length=100)`
  - Add `LoginRequest` with fields: `email: EmailStr`, `password: str`
  - Both classes extend `BaseModel`; `Field`, `EmailStr`, and `Optional` are already imported — no new imports needed
  - **Validates: Requirements 3.1, 3.2**

- [ ] 2. Add `POST /auth/register` endpoint to `routes/auth.py`
  - Import `RegisterRequest` from `schemas.auth`
  - Add `@router.post("/register", response_model=TokenResponse)` handler
  - Call `auth_service.register_with_password(db, request.email, request.password, request.display_name)`
  - On `ValueError` raise `HTTPException(status_code=409, detail=str(e))`
  - On success call `auth_service._create_token_pair(db, user)`, `db.commit()`, and return a `TokenResponse` with a fully populated `UserResponse` (mirror the pattern in `verify_otp`)
  - Pydantic automatically returns 422 for schema violations (password < 8 chars, bad email) — no extra code needed
  - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**

- [ ] 3. Add `POST /auth/login` endpoint to `routes/auth.py`
  - Import `LoginRequest` from `schemas.auth`
  - Add `@router.post("/login", response_model=TokenResponse)` handler
  - Call `auth_service.authenticate_with_password(db, request.email, request.password)`
  - On `ValueError`: check `"inactive" in str(e)` → 403 Forbidden; otherwise → 401 Unauthorized with message `"Invalid email or password"`
  - On success `db.commit()` and return `TokenResponse` (same shape as `/register`)
  - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6**

- [ ] 4. Write unit and integration tests for the new backend endpoints
  - Add a `TestPasswordAuthService` class to `apps/api-gateway/tests/test_auth.py`
  - Test `register_with_password` success: user is created, `email_verified=True`, `password_hash` is set and not equal to the plain password
  - Test `register_with_password` duplicate email: raises `ValueError`
  - Test `authenticate_with_password` success: returns a 4-tuple `(user, access_token, refresh_token, expires_in)`
  - Test `authenticate_with_password` wrong password: raises `ValueError` with message `"Invalid email or password"`
  - Test `authenticate_with_password` unknown email: raises `ValueError` with message `"Invalid email or password"`
  - Test `authenticate_with_password` inactive user: raises `ValueError` containing `"inactive"`
  - Add a `TestPasswordEndpoints` class (mirrors the `TestAuthEndpoints` setup using `override_get_db` fixture) covering:
    - `POST /auth/register` with valid payload returns 200 with `access_token`, `refresh_token`, and `user.email`
    - `POST /auth/register` with duplicate email returns 409
    - `POST /auth/register` with password shorter than 8 characters returns 422
    - `POST /auth/register` with invalid email format returns 422
    - `POST /auth/login` with correct credentials returns 200 with token pair
    - `POST /auth/login` with wrong password returns 401
    - `POST /auth/login` with unknown email returns 401
  - Run `pytest apps/api-gateway/tests/test_auth.py -v` and confirm all new tests pass
  - **Validates: Requirements 1.1–1.6, 2.1–2.6, 3.1–3.3**

- [ ] 5. Write property-based tests for backend auth correctness
  - Add `hypothesis==6.131.16` to `apps/api-gateway/requirements.txt`
  - Create `apps/api-gateway/tests/test_auth_properties.py`
  - Use `@given` from `hypothesis` with `pytest` as the runner; use an in-memory SQLite session for database-backed properties (reuse the `TestSessionLocal` and `Base.metadata` pattern from `conftest.py`)
  - Implement exactly the four named properties below:

  **Property 1 — Password hashing is non-reversible**
  - Strategy: `st.text(min_size=8, max_size=72)` for passwords
  - Assert `hash_password(pw) != pw`
  - Assert `verify_password(pw, hash_password(pw)) is True`
  - Assert `verify_password(pw + "x", hash_password(pw)) is False` (suffix makes it a different password)
  - **Validates: Requirement 1.2**

  **Property 2 — Duplicate email registration is always rejected**
  - Strategy: `st.emails()` for email, `st.text(min_size=8, max_size=72)` for password
  - First call to `register_with_password(db, email, password)` must succeed
  - Second call with the same email must raise `ValueError`
  - Use a fresh in-memory DB session per example via `@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])`
  - **Validates: Requirement 1.3**

  **Property 3 — Invalid credentials always return 401-equivalent error**
  - Strategy: `st.tuples(st.emails(), st.text(min_size=8, max_size=72), st.text(min_size=8, max_size=72))` with `assume(pw1 != pw2)`
  - Register user with `pw1`; attempt `authenticate_with_password(db, email, pw2)` → must raise `ValueError` with message `"Invalid email or password"`
  - **Validates: Requirements 2.3, 2.4**

  **Property 4 — Successful registration always returns a valid token pair**
  - Strategy: `st.emails()` for email, `st.text(min_size=8, max_size=72)` for password, `st.one_of(st.none(), st.text(min_size=1, max_size=100))` for display name
  - After `register_with_password` + `_create_token_pair`: assert `access_token` decodes (via `decode_token`) to a payload where `sub == str(user.id)` and `email == user.email`; assert `refresh_token` is a non-empty string
  - **Validates: Requirements 1.6, 2.6**

  - Run `pytest apps/api-gateway/tests/test_auth_properties.py -v` and update PBT status
  - **This is a PBT task**

- [x] 6. Add `register()` and `loginWithPassword()` methods to `apps/web/src/lib/api.ts`
  - Read the existing file first to understand the `ApiClient` class shape, the `request<T>()` wrapper, and the `AuthResponse` / `ApiError` types
  - Add `register(email: string, password: string, displayName?: string): Promise<AuthResponse>` — sends `POST /auth/register` with body `{ email, password, display_name: displayName }`
  - Add `loginWithPassword(email: string, password: string): Promise<AuthResponse>` — sends `POST /auth/login` with body `{ email, password }`
  - Both methods use the existing `request<T>()` wrapper; no changes to `ApiError` or `request()` are needed
  - Run `npm run type-check` inside `apps/web` and fix any TypeScript errors before marking done
  - **Validates: Requirements 4.1, 4.2, 4.3**

- [ ] 7. Update `apps/web/src/providers/auth-provider.tsx` — replace OTP functions with password-based auth
  - Read the existing file to understand the full context interface, `setTokens`, `setUser`, `setStoredUser`, router usage, and the bootstrap `useEffect`
  - Add `register(email: string, password: string, displayName?: string): Promise<void>` — calls `api.register`, stores token pair via `setTokens`, sets user state, calls `router.push("/dashboard")`
  - Add `login(email: string, password: string): Promise<void>` — calls `api.loginWithPassword`, stores token pair, sets user state, calls `router.push("/dashboard")`
  - Both functions let `ApiError` propagate to callers without altering auth state
  - Remove `requestOtp`, the OTP-based `signup`, and the OTP-based `login` from the context interface and the provider's context value object
  - Keep `logout`, `refreshUser`, `isAuthenticated`, `user`, `isLoading`, and the token-refresh bootstrap `useEffect` completely untouched
  - Update the context TypeScript type/interface to reflect the removed and added functions
  - Run `npm run type-check` inside `apps/web` and resolve all type errors before marking done
  - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 8.1, 8.2, 8.3, 8.4**

- [ ] 8. Rewrite `apps/web/src/components/auth/sign-up-form.tsx` — single-screen password form
  - Read the existing file first to understand current imports, layout wrappers, and UI component usage
  - Define zod schema: `displayName: z.string().min(2).max(100)`, `email: z.string().email()`, `password: z.string().min(8, "Password must be at least 8 characters")`
  - Render three fields on one screen with no step state: Full Name (User icon), Email Address (Mail icon), Password (Lock icon + show/hide toggle using Eye/EyeOff icons)
  - Add a password strength indicator below the password field evaluated via `watch("password")` on every keystroke using the heuristic: length ≥ 8 = weak (red), + mixed case = medium (yellow), + digit + symbol = strong (green); render as a 3-segment bar
  - Submit flow: zod validates on submit (password < 8 shows inline error below password field, no network request) → `isLoading = true` → call `auth.register(email, password, displayName)` → `AuthProvider` navigates on success
  - On `ApiError` with `status === 409`: use `setError("email", { message: ... })` to display error below the email field
  - On other errors: display error message below the form
  - Remove all OTP-related code: `OtpInput`, `CountdownTimer`, step state, resend logic, and their imports
  - Run `npm run type-check` inside `apps/web` and fix all TypeScript errors
  - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6**

- [ ] 9. Rewrite `apps/web/src/components/auth/sign-in-form.tsx` — single-screen password form
  - Read the existing file first to understand current imports, layout wrappers, and UI component usage
  - Define zod schema: `email: z.string().email()`, `password: z.string().min(1, "Password is required")`
  - Render two fields on one screen with no step state: Email Address (Mail icon), Password (Lock icon + show/hide toggle using Eye/EyeOff icons)
  - Submit flow: zod validates → `isLoading = true` → call `auth.login(email, password)` → `AuthProvider` navigates on success
  - On `ApiError` with `status === 401`: display `"Invalid email or password"` below the form; do NOT clear the email field
  - On other errors: display error message below the form
  - Remove all OTP-related code: step state, OTP input, countdown timer, resend logic, and their imports
  - Run `npm run type-check` inside `apps/web` and fix all TypeScript errors
  - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5**

## Notes

- The existing OTP endpoints (`/request-otp`, `/verify-otp`) are **not removed** in this spec. They remain untouched to avoid breaking anything dependent on them. A cleanup task can be created separately.
- The backend `register_with_password()` and `authenticate_with_password()` service methods in `auth_service.py` are **already implemented** — tasks 2 and 3 only wire them to routes.
- No database migrations are required — the `password_hash` column already exists on the `users` table.
- `hypothesis` must be installed (`pip install hypothesis==6.131.16`) before running task 5. Add it to `requirements.txt` as part of that task.
- The frontend has no test framework configured (no vitest/jest in `package.json`). Frontend correctness is validated via `npm run type-check` in tasks 6–9.
- Password strength evaluation in task 8 is purely client-side and does not affect form submission validation — the only hard constraint is `min_length=8` enforced by both zod and the backend schema.
