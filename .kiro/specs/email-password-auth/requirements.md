# Requirements Document

## Introduction

This feature replaces the current OTP-based authentication flow in CyberShield AI with a classic email + password system. Users will be able to register with a name, email, and password, and sign in with email and password — all in a single step, with no OTP codes, no email verification step, and no countdown timers. The existing JWT-based session management (access token + refresh token) is preserved. The backend already contains `register_with_password()` and `authenticate_with_password()` methods in `AuthService` that need to be wired to new API routes. The frontend sign-up and sign-in forms need to be rewritten to collect credentials instead of OTP codes.

## Glossary

- **Auth_Service**: The backend `AuthService` class in `apps/api-gateway/services/auth_service.py` that handles user creation and authentication logic.
- **Auth_Router**: The FastAPI router in `apps/api-gateway/routes/auth.py` that exposes authentication endpoints.
- **API_Client**: The frontend TypeScript client in `apps/web/src/lib/api.ts` that communicates with the backend.
- **Auth_Provider**: The React context provider in `apps/web/src/providers/auth-provider.tsx` that manages authentication state.
- **Sign_Up_Form**: The React component in `apps/web/src/components/auth/sign-up-form.tsx` that collects registration data.
- **Sign_In_Form**: The React component in `apps/web/src/components/auth/sign-in-form.tsx` that collects login credentials.
- **Password_Hash**: A bcrypt-hashed representation of a user's password stored in the `password_hash` column of the `users` table.
- **Token_Pair**: A set of two tokens: a short-lived JWT access token and a long-lived opaque refresh token, used for session management.
- **Access_Token**: A short-lived JWT used to authenticate API requests.
- **Refresh_Token**: A long-lived opaque token used to obtain new Access_Tokens without re-authentication.

---

## Requirements

### Requirement 1: User Registration via Email and Password

**User Story:** As a new user, I want to create an account by providing my name, email, and a password, so that I can access CyberShield AI immediately after registering without any additional verification step.

#### Acceptance Criteria

1. THE Auth_Router SHALL expose a `POST /auth/register` endpoint that accepts `display_name`, `email`, and `password` fields.
2. WHEN a registration request is received with a valid email and a password that is at least 8 characters long, THE Auth_Service SHALL create a new user record with a Password_Hash and return a Token_Pair.
3. WHEN a registration request is received for an email address that already exists in the database, THE Auth_Router SHALL return an HTTP 409 Conflict response with a descriptive error message.
4. WHEN a registration request is received with a password shorter than 8 characters, THE Auth_Router SHALL return an HTTP 422 Unprocessable Entity response indicating the password length constraint.
5. WHEN a user is successfully registered, THE Auth_Service SHALL set `email_verified` to `true` on the new user record.
6. WHEN a user is successfully registered, THE Auth_Router SHALL return a Token_Pair and the user profile in the same response format as the existing `POST /auth/verify-otp` endpoint (`TokenResponse` schema).

### Requirement 2: User Login via Email and Password

**User Story:** As a returning user, I want to sign in with my email and password in a single step, so that I can access my account quickly without waiting for a code.

#### Acceptance Criteria

1. THE Auth_Router SHALL expose a `POST /auth/login` endpoint that accepts `email` and `password` fields.
2. WHEN a login request is received with a correct email and password combination, THE Auth_Service SHALL authenticate the user, update `last_login_at`, and return a Token_Pair.
3. WHEN a login request is received with an email that does not exist in the database, THE Auth_Router SHALL return an HTTP 401 Unauthorized response with the message "Invalid email or password".
4. WHEN a login request is received with an incorrect password, THE Auth_Router SHALL return an HTTP 401 Unauthorized response with the message "Invalid email or password".
5. WHEN a login request is received for a user whose account is inactive, THE Auth_Router SHALL return an HTTP 403 Forbidden response with a descriptive error message.
6. WHEN a user is successfully authenticated, THE Auth_Router SHALL return a Token_Pair and the user profile in the `TokenResponse` schema.

### Requirement 3: Backend Request/Response Schemas

**User Story:** As a backend developer, I want well-typed Pydantic schemas for the new endpoints, so that request validation and API documentation are handled automatically.

#### Acceptance Criteria

1. THE Auth_Router SHALL define a `RegisterRequest` Pydantic schema with fields: `email` (EmailStr), `password` (str, minimum length 8), and `display_name` (optional str, maximum length 100).
2. THE Auth_Router SHALL define a `LoginRequest` Pydantic schema with fields: `email` (EmailStr) and `password` (str).
3. THE Auth_Router SHALL reuse the existing `TokenResponse` schema for both `POST /auth/register` and `POST /auth/login` success responses.

### Requirement 4: Frontend API Client Methods

**User Story:** As a frontend developer, I want API client methods for the new register and login endpoints, so that the UI components can authenticate users without touching raw fetch calls.

#### Acceptance Criteria

1. THE API_Client SHALL expose a `register(email, password, displayName?)` method that sends a `POST` request to `/auth/register` and returns an `AuthResponse`.
2. THE API_Client SHALL expose a `loginWithPassword(email, password)` method that sends a `POST` request to `/auth/login` and returns an `AuthResponse`.
3. WHEN the `register` or `loginWithPassword` method receives a non-2xx HTTP response, THE API_Client SHALL throw an `ApiError` with the status code and error message from the response body.

### Requirement 5: Auth Provider Integration

**User Story:** As a frontend developer, I want the Auth_Provider to expose `register` and `login` functions that use the new password-based endpoints, so that UI components can trigger authentication through the existing context API.

#### Acceptance Criteria

1. THE Auth_Provider SHALL expose a `register(email, password, displayName?)` function that calls `API_Client.register`, stores the returned Token_Pair, updates the user state, and navigates to `/dashboard`.
2. THE Auth_Provider SHALL expose a `login(email, password)` function that calls `API_Client.loginWithPassword`, stores the returned Token_Pair, updates the user state, and navigates to `/dashboard`.
3. WHEN `register` or `login` throws an `ApiError`, THE Auth_Provider SHALL propagate the error to the calling component without altering the current authentication state.
4. THE Auth_Provider SHALL remove the `requestOtp`, `signup` (OTP-based), and `login` (OTP-based) functions from the context interface, replacing them with the password-based `register` and `login` functions defined above.

### Requirement 6: Sign-Up Form (Password-Based)

**User Story:** As a new user, I want to fill in my name, email, and password on a single screen and be taken to the dashboard immediately after submitting, so that registration is fast and requires no extra steps.

#### Acceptance Criteria

1. THE Sign_Up_Form SHALL display three fields: Full Name, Email Address, and Password — all on a single screen with no multi-step flow.
2. THE Sign_Up_Form SHALL display a password strength indicator that evaluates the entered password in real time.
3. WHEN the Sign_Up_Form is submitted with a password shorter than 8 characters, THE Sign_Up_Form SHALL display an inline validation error below the password field before sending any network request.
4. WHEN the Sign_Up_Form is submitted with a valid name, email, and password, THE Sign_Up_Form SHALL call `Auth_Provider.register`, show a loading state on the submit button, and navigate to `/dashboard` on success.
5. WHEN `Auth_Provider.register` returns an error indicating the email is already taken (HTTP 409), THE Sign_Up_Form SHALL display the error message inline below the email field.
6. THE Sign_Up_Form SHALL NOT include any OTP input, countdown timer, or "resend code" interaction.

### Requirement 7: Sign-In Form (Password-Based)

**User Story:** As a returning user, I want to enter my email and password on a single screen and be signed in immediately, so that login is simple and direct.

#### Acceptance Criteria

1. THE Sign_In_Form SHALL display two fields: Email Address and Password — on a single screen with no multi-step flow.
2. WHEN the Sign_In_Form is submitted with both fields populated, THE Sign_In_Form SHALL call `Auth_Provider.login`, show a loading state on the submit button, and navigate to `/dashboard` on success.
3. WHEN `Auth_Provider.login` returns an HTTP 401 error, THE Sign_In_Form SHALL display the error message "Invalid email or password" below the form without clearing the email field.
4. THE Sign_In_Form SHALL include a "Show/Hide password" toggle button on the password field.
5. THE Sign_In_Form SHALL NOT include any OTP input, countdown timer, or "resend code" interaction.

### Requirement 8: Session Continuity

**User Story:** As a user, I want my session to behave the same way it did before — with automatic token refresh and persistent login — so that the change in authentication method does not disrupt my existing workflow.

#### Acceptance Criteria

1. WHILE a valid Access_Token is present in storage, THE Auth_Provider SHALL include it as a `Bearer` token on all API requests.
2. WHEN the Access_Token has expired, THE Auth_Provider SHALL automatically attempt to obtain a new Access_Token using the stored Refresh_Token before retrying the original request.
3. WHEN the Refresh_Token is invalid or expired, THE Auth_Provider SHALL clear all stored tokens, reset the user state to `null`, and redirect the user to the sign-in page.
4. WHEN the user calls `logout`, THE Auth_Provider SHALL call `POST /auth/logout` to revoke the Refresh_Token on the backend, then clear all stored tokens and redirect to the home page.
