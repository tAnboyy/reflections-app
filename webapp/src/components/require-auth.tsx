import { Navigate, Outlet, useLocation } from "react-router-dom"

import { isAuthenticated } from "@/lib/auth"

export function RequireAuth() {
  const location = useLocation()

  if (!isAuthenticated()) {
    return <Navigate to="/auth/login" replace state={{ from: location }} />
  }

  return <Outlet />
}
