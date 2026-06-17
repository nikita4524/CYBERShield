"use client";

import { useState, useCallback } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2, Mail, Lock, User, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const schema = z.object({
  displayName: z
    .string()
    .min(2, "Name must be at least 2 characters")
    .max(100, "Name must be 100 characters or less"),
  email: z.string().email("Please enter a valid email address"),
  password: z
    .string()
    .min(8, "Password must be at least 8 characters"),
});
type FormData = z.infer<typeof schema>;

/* ── Password strength heuristic ── */
type Strength = "weak" | "medium" | "strong";

function getPasswordStrength(pw: string): Strength {
  if (pw.length < 8) return "weak";
  const hasMixedCase = /[a-z]/.test(pw) && /[A-Z]/.test(pw);
  const hasDigit = /\d/.test(pw);
  const hasSymbol = /[^a-zA-Z0-9]/.test(pw);
  if (hasMixedCase && hasDigit && hasSymbol) return "strong";
  if (hasMixedCase) return "medium";
  return "weak";
}

const strengthConfig: Record<Strength, { label: string; color: string; segments: number }> = {
  weak:   { label: "Weak",   color: "bg-red-500",    segments: 1 },
  medium: { label: "Medium", color: "bg-yellow-500", segments: 2 },
  strong: { label: "Strong", color: "bg-green-500",  segments: 3 },
};

export function SignUpForm() {
  const { register: authRegister } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const form = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { displayName: "", email: "", password: "" },
  });

  const passwordValue = form.watch("password");
  const strength = passwordValue ? getPasswordStrength(passwordValue) : null;

  const handleSubmit = useCallback(
    async (data: FormData) => {
      setIsLoading(true);
      setFormError(null);
      try {
        await authRegister(data.email, data.password, data.displayName);
        // AuthProvider navigates to /dashboard on success
        toast.success("Account created!", {
          description: "Welcome to CyberShield AI.",
        });
      } catch (err) {
        if (err instanceof ApiError) {
          if (err.status === 409) {
            form.setError("email", { message: err.message });
          } else {
            setFormError(err.message);
          }
        } else {
          setFormError("Something went wrong. Please try again.");
          toast.error("Something went wrong");
        }
      } finally {
        setIsLoading(false);
      }
    },
    [authRegister, form]
  );

  return (
    <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
      {/* Full Name */}
      <div className="space-y-2">
        <Label htmlFor="displayName" className="text-sm">
          Full Name
        </Label>
        <div className="relative">
          <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            id="displayName"
            type="text"
            placeholder="Your name"
            autoComplete="name"
            autoFocus
            disabled={isLoading}
            className="pl-10 h-11"
            {...form.register("displayName")}
          />
        </div>
        {form.formState.errors.displayName && (
          <p className="text-xs text-destructive">
            {form.formState.errors.displayName.message}
          </p>
        )}
      </div>

      {/* Email */}
      <div className="space-y-2">
        <Label htmlFor="email" className="text-sm">
          Email Address
        </Label>
        <div className="relative">
          <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            id="email"
            type="email"
            placeholder="you@example.com"
            autoComplete="email"
            disabled={isLoading}
            className="pl-10 h-11"
            {...form.register("email")}
          />
        </div>
        {form.formState.errors.email && (
          <p className="text-xs text-destructive">
            {form.formState.errors.email.message}
          </p>
        )}
      </div>

      {/* Password */}
      <div className="space-y-2">
        <Label htmlFor="password" className="text-sm">
          Password
        </Label>
        <div className="relative">
          <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            id="password"
            type={showPassword ? "text" : "password"}
            placeholder="Min. 8 characters"
            autoComplete="new-password"
            disabled={isLoading}
            className="pl-10 pr-10 h-11"
            {...form.register("password")}
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            aria-label={showPassword ? "Hide password" : "Show password"}
          >
            {showPassword ? (
              <EyeOff className="h-4 w-4" />
            ) : (
              <Eye className="h-4 w-4" />
            )}
          </button>
        </div>

        {/* Password strength indicator */}
        {passwordValue && strength && (
          <div className="space-y-1">
            <div className="flex gap-1">
              {[1, 2, 3].map((seg) => (
                <div
                  key={seg}
                  className={`h-1 flex-1 rounded-full transition-colors ${
                    seg <= strengthConfig[strength].segments
                      ? strengthConfig[strength].color
                      : "bg-muted"
                  }`}
                />
              ))}
            </div>
            <p className="text-xs text-muted-foreground">
              Strength:{" "}
              <span
                className={
                  strength === "strong"
                    ? "text-green-500"
                    : strength === "medium"
                    ? "text-yellow-500"
                    : "text-red-500"
                }
              >
                {strengthConfig[strength].label}
              </span>
            </p>
          </div>
        )}

        {form.formState.errors.password && (
          <p className="text-xs text-destructive">
            {form.formState.errors.password.message}
          </p>
        )}
      </div>

      {/* Form-level error */}
      {formError && (
        <p className="text-xs text-destructive text-center">{formError}</p>
      )}

      <Button
        type="submit"
        className="w-full h-11 bg-primary hover:bg-primary/90 font-semibold"
        disabled={isLoading}
      >
        {isLoading ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : null}
        {isLoading ? "Creating account…" : "Create Account"}
      </Button>
    </form>
  );
}
