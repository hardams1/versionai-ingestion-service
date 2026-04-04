"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Upload, MessageSquare, LogOut, User, Settings, Compass } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";

const NAV_ITEMS = [
  { href: "/ingest", label: "Ingest", icon: Upload },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/discover", label: "Discover", icon: Compass },
  { href: "/me", label: "My Profile", icon: User },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

export function NavHeader() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold text-sm">
              V
            </div>
            <span className="text-base font-semibold">VersionAI</span>
          </Link>

          <nav className="flex items-center gap-1">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                    active
                      ? "bg-muted text-foreground"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>

        {user && (
          <div className="flex items-center gap-3">
            <Link
              href="/me"
              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-xs font-medium">
                {(user.username?.[0] ?? "?").toUpperCase()}
              </div>
              <span>{user.username}</span>
            </Link>
            <Button variant="ghost" size="icon-sm" onClick={logout} title="Sign out">
              <LogOut className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </div>
    </header>
  );
}
