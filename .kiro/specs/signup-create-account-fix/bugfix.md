# Bugfix Requirements Document

## Introduction

The sign-up / create-account flow in CyberShield AI is broken due to four compounding defects
spanning the backend configuration, the OTP delivery layer, and the frontend auth provider.
Together they cause:

- The backend application server to behave unpredictably at startup due to duplicate Pydantic
  field declarations in `config.py`.
- OTP emails to never be sent — the async `send_otp_email` service function is never called;
  only a synchronous console-print fallback runs.
- The user's display name entered on the sign-up form to be silently discarded — the
  `signup` function in `auth-provider.tsx` does not forward the name to the backend.
- The resend-countdown timer in the OTP step to reset on every render because the
  `onComplete` callback is not stabilised with `useCallback`.

Affected files:
- `apps/api-gateway/config.py`
- `apps/api-gateway/services/auth_service.py`
- `apps/web/src/providers/auth-provider.tsx`
- `apps/web/src/components/auth/sign-up-form.tsx`

---

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the backend application starts AND `config.py` is loaded THEN the system produces
    a duplicate-field `Settings` model because `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
    `SMTP_PASSWORD`, and `FROM_EMAIL` are each declared twice in the same `Settings` class,
    causing the second declarations to shadow the first and reset `SMTP_HOST` to `None`,
    `SMTP_PORT` to `587`, `SMTP_USER` to `None`, `SMTP_PASSWORD` to `None`, and `FROM_EMAIL`
    to `"noreply@cybershield.ai"`.

1.2 WHEN a user submits the sign-up form with a valid email AND the backend calls
    `auth_service.request_otp()` THEN the system calls the synchronous
    `self._deliver_otp()` console-print method instead of the async `send_otp_email()`
    function from `email_service.py`, so no OTP email is ever delivered to the user's
    inbox regardless of SMTP configuration.

1.3 WHEN a user enters their display name on the sign-up form AND completes OTP verification
    THEN the system discards the entered display name because `signup(email, otp)` in
    `auth-provider.tsx` does not pass `displayName`, and `_get_or_create_user()` falls back
    to deriving the name from the email prefix.

1.4 WHEN the user reaches the OTP step AND the countdown timer is rendered THEN the system
    resets the countdown timer on every parent component re-render because the `onComplete`
    callback passed to `CountdownTimer` is an inline arrow function that is recreated on
    every render, causing `useEffect` in `CountdownTimer` to re-fire.

### Expected Behavior (Correct)

2.1 WHEN the backend application starts AND `config.py` is loaded THEN the system SHALL
    define each SMTP setting field exactly once in the `Settings` class, producing a valid
    Pydantic model that correctly reads `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
    `SMTP_PASSWORD`, and `FROM_EMAIL` from the environment without shadowing.

2.2 WHEN a user submits the sign-up form with a valid email AND the backend calls
    `auth_service.request_otp()` THEN the system SHALL call `await send_otp_email()`
    from `email_service.py` to attempt email delivery, falling back to console logging
    only when SMTP is not configured.

2.3 WHEN a user enters their display name on the sign-up form AND completes OTP verification
    THEN the system SHALL pass `displayName` through the `signup()` call in
    `auth-provider.tsx` and forward it to the backend so the user record is created with
    the name the user actually provided.

2.4 WHEN the user reaches the OTP step AND the countdown timer is rendered THEN the system
    SHALL stabilise the `onComplete` callback with `useCallback` so the countdown timer
    does not reset on parent re-renders.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN SMTP credentials are not configured in the environment THEN the system SHALL
    CONTINUE TO fall back to printing the OTP to the server console (development mode),
    and SHALL CONTINUE TO expose `dev_otp` in the API response so the frontend can
    display it for local development.

3.2 WHEN an existing user signs in via the login OTP flow (not sign-up) THEN the system
    SHALL CONTINUE TO authenticate them correctly and issue access and refresh tokens.

3.3 WHEN a user requests an OTP within the 60-second rate-limit window THEN the system
    SHALL CONTINUE TO return a 429 Too Many Requests error.

3.4 WHEN a user submits an incorrect OTP THEN the system SHALL CONTINUE TO increment the
    attempt counter and return a meaningful error after each failed attempt, locking the
    OTP after 3 failed attempts.

3.5 WHEN a user submits a valid OTP after expiry THEN the system SHALL CONTINUE TO reject
    it and prompt the user to request a new code.

3.6 WHEN a new user completes OTP verification for the first time THEN the system SHALL
    CONTINUE TO auto-create the user account and mark `email_verified` as `true`.

3.7 WHEN the OTP countdown reaches zero THEN the system SHALL CONTINUE TO show the
    "Resend code" button so the user can request a new OTP.

---

## Bug Condition Pseudocode

### Bug Condition Functions

```pascal
FUNCTION isConfigDuplicateFieldBug()
  // Triggers when the Settings class is loaded
  RETURN SMTP_HOST is declared more than once in config.Settings
END FUNCTION

FUNCTION isOtpEmailNeverSentBug(X)
  INPUT: X — an OTP request with any valid email
  OUTPUT: boolean
  RETURN auth_service.request_otp does NOT call send_otp_email()
END FUNCTION

FUNCTION isDisplayNameDiscardedBug(X)
  INPUT: X — a sign-up flow where user enters a displayName
  OUTPUT: boolean
  RETURN signup() in auth-provider.tsx does NOT forward X.displayName to backend
END FUNCTION

FUNCTION isTimerResetBug()
  // Triggers on any parent re-render during the OTP step
  RETURN onComplete callback passed to CountdownTimer is NOT wrapped in useCallback
END FUNCTION
```

### Fix-Checking Properties

```pascal
// Property 2.1 — Config deduplication fix
FOR ALL backend_startup WHERE isConfigDuplicateFieldBug() DO
  settings ← Settings()
  ASSERT settings.SMTP_HOST is defined once
  ASSERT settings.SMTP_PORT is defined once
  ASSERT no Pydantic field-shadow warnings emitted
END FOR

// Property 2.2 — OTP email delivery fix
FOR ALL X WHERE isOtpEmailNeverSentBug(X) DO
  result ← request_otp'(db, X.email, X.purpose)
  ASSERT send_otp_email() was called OR SMTP not configured AND console log emitted
END FOR

// Property 2.3 — Display name preservation fix
FOR ALL X WHERE isDisplayNameDiscardedBug(X) DO
  await signup'(X.email, X.otp, X.displayName)
  user ← db.query(User).filter(email == X.email)
  ASSERT user.display_name == X.displayName
END FOR

// Property 2.4 — Timer stability fix
FOR ALL renders WHERE isTimerResetBug() DO
  ASSERT onComplete reference is stable across parent re-renders
  ASSERT countdown does NOT restart on re-render
END FOR
```

### Preservation Property

```pascal
// Preservation: all non-buggy inputs must produce identical behaviour before and after the fix
FOR ALL X WHERE NOT (isConfigDuplicateFieldBug()
                  OR isOtpEmailNeverSentBug(X)
                  OR isDisplayNameDiscardedBug(X)
                  OR isTimerResetBug()) DO
  ASSERT F(X) = F'(X)
END FOR
```
