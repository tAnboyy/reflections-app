import { CalendarCheck2, ClipboardCheck, NotebookPen } from "lucide-react"
import { BarChart3, BookCopy, UserCheck } from "lucide-react"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { getCurrentUserRole } from "@/lib/auth"

const STUDENT_OVERVIEW_CARDS = [
  {
    label: "Courses in Progress",
    value: "04",
    icon: NotebookPen,
  },
  {
    label: "Assignments Due",
    value: "07",
    icon: ClipboardCheck,
  },
  {
    label: "Upcoming Sessions",
    value: "03",
    icon: CalendarCheck2,
  },
]

export function HomePage() {
  const role = getCurrentUserRole()
  const isEducator = role === "educator"

  const overviewCards = isEducator
    ? [
        {
          label: "Active Classes",
          value: "06",
          icon: BookCopy,
        },
        {
          label: "Submissions to Review",
          value: "18",
          icon: ClipboardCheck,
        },
        {
          label: "Attendance Today",
          value: "92%",
          icon: UserCheck,
        },
      ]
    : STUDENT_OVERVIEW_CARDS

  return (
    <div className="space-y-6">
      <Card className="rounded-lg border">
        <CardHeader className="gap-2">
          <CardTitle className="text-2xl">
            {isEducator ? "Educator Dashboard" : "Student Dashboard"}
          </CardTitle>
          <CardDescription>
            {isEducator
              ? "Monitor classes, evaluate submissions, and track cohort performance."
              : "Track classes, assignments, and session timelines in one place."}
          </CardDescription>
        </CardHeader>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        {overviewCards.map((item) => (
          <Card key={item.label} className="rounded-lg border">
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <CardDescription className="text-sm">{item.label}</CardDescription>
              <item.icon className="size-4" />
            </CardHeader>
            <CardContent>
              <CardTitle className="text-3xl">{item.value}</CardTitle>
            </CardContent>
          </Card>
        ))}
      </div>

      {isEducator ? (
        <Card className="rounded-lg border">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardDescription className="text-sm">Class Health Snapshot</CardDescription>
            <BarChart3 className="size-4" />
          </CardHeader>
          <CardContent>
            <CardTitle className="text-3xl">On Track</CardTitle>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
