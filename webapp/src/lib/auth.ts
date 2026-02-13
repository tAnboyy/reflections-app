const AUTH_STORAGE_KEY = "reflections_auth_session"
const AUTH_CREDENTIALS_KEY = "reflections_auth_credentials"
const AUTH_ROLE_KEY = "reflections_auth_role"

export type UserRole = "student" | "educator"

type LocalCredentials = {
  email: string
  password: string
}

type RoleCredentials = Record<UserRole, LocalCredentials>

const DEFAULT_CREDENTIALS: RoleCredentials = {
  student: {
    email: "student@school.edu",
    password: "reflections123",
  },
  educator: {
    email: "educator@school.edu",
    password: "reflections123",
  },
}

function getStoredCredentials(): RoleCredentials {
  const raw = localStorage.getItem(AUTH_CREDENTIALS_KEY)
  if (!raw) {
    localStorage.setItem(AUTH_CREDENTIALS_KEY, JSON.stringify(DEFAULT_CREDENTIALS))
    return DEFAULT_CREDENTIALS
  }

  try {
    const parsed = JSON.parse(raw) as Partial<RoleCredentials>
    const student = parsed.student
    const educator = parsed.educator

    if (student?.email && student.password && educator?.email && educator.password) {
      return {
        student: {
          email: student.email,
          password: student.password,
        },
        educator: {
          email: educator.email,
          password: educator.password,
        },
      }
    }
  } catch {
    // Fallback to defaults when storage is malformed.
  }

  localStorage.setItem(AUTH_CREDENTIALS_KEY, JSON.stringify(DEFAULT_CREDENTIALS))
  return DEFAULT_CREDENTIALS
}

export function isAuthenticated() {
  return localStorage.getItem(AUTH_STORAGE_KEY) === "active"
}

export function getCurrentUserRole(): UserRole | null {
  const role = localStorage.getItem(AUTH_ROLE_KEY)
  return role === "student" || role === "educator" ? role : null
}

export function getDefaultCredentials(role: UserRole): LocalCredentials {
  return DEFAULT_CREDENTIALS[role]
}

export function signIn(role: UserRole, email: string, password: string) {
  const credentials = getStoredCredentials()[role]
  const emailMatches = email.trim().toLowerCase() === credentials.email.toLowerCase()
  const passwordMatches = password === credentials.password

  if (!emailMatches || !passwordMatches) {
    return false
  }

  localStorage.setItem(AUTH_STORAGE_KEY, "active")
  localStorage.setItem(AUTH_ROLE_KEY, role)
  return true
}

export function signOut() {
  localStorage.removeItem(AUTH_STORAGE_KEY)
  localStorage.removeItem(AUTH_ROLE_KEY)
}
