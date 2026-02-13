import { LogOut } from "lucide-react";
import { Outlet, useNavigate } from "react-router-dom";

import { AppSidebar } from "@/components/app-sidebar";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { getCurrentUserRole, signOut } from "@/lib/auth";

export function AppShell() {
  const navigate = useNavigate();
  const role = getCurrentUserRole();
  const isEducator = role === "educator";

  const handleSignOut = () => {
    signOut();
    navigate("/auth/login", { replace: true });
  };

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <div className="flex h-svh flex-col overflow-hidden">
          <div className="sticky top-0 z-30 flex h-16 shrink-0 items-center justify-between border-b bg-background px-4 md:px-6">
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">
                  {isEducator ? "Educator Dashboard" : "Student Dashboard"}
                </CardTitle>
              </div>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="icon">
                  <Avatar className="size-8 rounded-lg">
                    <AvatarFallback className="rounded-lg bg-secondary text-xs">
                      {isEducator ? "ED" : "ST"}
                    </AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-48">
                <DropdownMenuItem onClick={handleSignOut}>
                  <LogOut className="mr-2 size-4" />
                  <span>Sign Out</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <div className="flex-1 overflow-y-auto bg-muted/50 p-4 md:p-6">
            <Outlet />
          </div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
