import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";

import { useAuthStore } from "@/store/auth";
import type { UserRole } from "@/lib/api";

type RequireRoleProps = {
  children: ReactNode;
  allowedRoles?: UserRole[];
  role?: UserRole;
};

export function RequireRole({ children, allowedRoles, role }: RequireRoleProps) {
  const token = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  const expectedRoles = allowedRoles ?? (role ? [role] : []);
  if (expectedRoles.length > 0 && user && !expectedRoles.includes(user.role)) {
    // If user is regular_user, direct them to user dashboard
    if (user.role === "regular_user") {
      return <Navigate to="/user/dashboard" replace />;
    }
    // If user is event_organizer or admin, direct them to organizer dashboard
    return <Navigate to="/organizer/dashboard" replace />;
  }

  return children;
}
