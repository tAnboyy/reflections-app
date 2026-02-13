import { useEffect, useState } from "react"
import type { FormEvent } from "react"
import { BookMarked, LockKeyhole, Mail } from "lucide-react"
import { useLocation, useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  getDefaultCredentials,
  isAuthenticated,
  signIn,
  type UserRole,
} from "@/lib/auth"

type LocationState = {
  from?: {
    pathname?: string
  }
}

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [role, setRole] = useState<UserRole>("student")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")

  useEffect(() => {
    if (isAuthenticated()) {
      navigate("/", { replace: true })
    }
  }, [navigate])

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const success = signIn(role, email, password)
    if (!success) {
      setError("Invalid email or password.")
      return
    }

    const routeState = location.state as LocationState
    const redirectTo = routeState?.from?.pathname ?? "/"
    navigate(redirectTo, { replace: true })
  }

  return (
    <div className="flex min-h-svh items-center justify-center bg-muted/50 px-4 py-8">
      <Card className="w-full max-w-md rounded-lg border">
        <CardHeader className="gap-3">
          <div className="flex items-center gap-2 rounded-lg bg-secondary px-3 py-2">
            <BookMarked className="size-5" />
            <CardTitle className="text-base">Reflections LMS</CardTitle>
          </div>
          <CardTitle className="text-xl">Sign In</CardTitle>
          <CardDescription>
            Continue to your classroom dashboard.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs
            value={role}
            onValueChange={(value) => {
              setRole(value as UserRole)
              setError("")
            }}
            className="space-y-4"
          >
            <TabsList className="grid w-full grid-cols-2 rounded-lg">
              <TabsTrigger value="student">Student</TabsTrigger>
              <TabsTrigger value="educator">Educator</TabsTrigger>
            </TabsList>
            <TabsContent value={role} className="mt-0">
              <form className="space-y-4" onSubmit={handleSubmit}>
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <div className="relative">
                    <Mail className="text-muted-foreground absolute top-1/2 left-3 size-4 -translate-y-1/2" />
                    <Input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      className="rounded-lg pl-9"
                      placeholder={
                        role === "student"
                          ? "student@school.edu"
                          : "educator@school.edu"
                      }
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <div className="relative">
                    <LockKeyhole className="text-muted-foreground absolute top-1/2 left-3 size-4 -translate-y-1/2" />
                    <Input
                      id="password"
                      type="password"
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      className="rounded-lg pl-9"
                      placeholder="Enter password"
                    />
                  </div>
                </div>
                {error ? (
                  <CardDescription className="rounded-lg border bg-secondary px-3 py-2 text-sm text-foreground">
                    {error}
                  </CardDescription>
                ) : null}
                <CardDescription className="rounded-lg border bg-secondary px-3 py-2 text-xs">
                  Demo login for {role}:{" "}
                  {getDefaultCredentials(role).email} /{" "}
                  {getDefaultCredentials(role).password}
                </CardDescription>
                <Button type="submit" className="w-full rounded-lg">
                  Continue as {role === "student" ? "Student" : "Educator"}
                </Button>
              </form>
            </TabsContent>
          </Tabs>
        </CardContent>
        <CardFooter className="pt-0">
          <CardDescription className="text-xs">
            Sign up is disabled for this app.
          </CardDescription>
        </CardFooter>
      </Card>
    </div>
  )
}
