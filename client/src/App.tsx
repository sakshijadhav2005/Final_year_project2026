import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { RequireAuth } from "@/components/RequireAuth";
import { RequireRole } from "@/components/RequireRole";
import { LandingPage } from "@/pages/LandingPage";
import { useAuthStore } from "@/store/auth";

// Every page except the landing page is split into its own chunk and
// downloaded the first time its route is visited.
const AdminPage = lazy(() => import("@/pages/AdminPage").then((m) => ({ default: m.AdminPage })));
const CatalogPage = lazy(() => import("@/pages/CatalogPage").then((m) => ({ default: m.CatalogPage })));
const CommunityPage = lazy(() => import("@/pages/CommunityPage").then((m) => ({ default: m.CommunityPage })));
const EventDetailPage = lazy(() => import("@/pages/EventDetailPage").then((m) => ({ default: m.EventDetailPage })));
const FixesPage = lazy(() => import("@/pages/FixesPage").then((m) => ({ default: m.FixesPage })));
const JobDetailPage = lazy(() => import("@/pages/JobDetailPage").then((m) => ({ default: m.JobDetailPage })));
const LoginPage = lazy(() => import("@/pages/LoginPage").then((m) => ({ default: m.LoginPage })));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage").then((m) => ({ default: m.NotFoundPage })));
const OrganizerDashboard = lazy(() =>
  import("@/pages/OrganizerDashboard").then((m) => ({ default: m.OrganizerDashboard })),
);
const RegisterPage = lazy(() => import("@/pages/RegisterPage").then((m) => ({ default: m.RegisterPage })));
const ReviewPage = lazy(() => import("@/pages/ReviewPage").then((m) => ({ default: m.ReviewPage })));
const SettingsPage = lazy(() => import("@/pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const UserDashboard = lazy(() => import("@/pages/UserDashboard").then((m) => ({ default: m.UserDashboard })));

function PageLoading() {
  return (
    <div role="status" className="grid min-h-screen place-items-center text-sm opacity-60">
      Loading…
    </div>
  );
}


function DashboardDispatcher() {
  const user = useAuthStore((s) => s.user);
  if (user?.role === "regular_user") {
    return <Navigate to="/user/dashboard" replace />;
  }
  return <Navigate to="/organizer/dashboard" replace />;
}

export function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoading />}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Generic Dashboard Redirector */}
          <Route
            path="/dashboard"
            element={
              <RequireAuth>
                <DashboardDispatcher />
              </RequireAuth>
            }
          />

          {/* Organizer Executive Dashboard */}
          <Route
            path="/organizer/dashboard"
            element={
              <RequireRole allowedRoles={["event_organizer", "admin", "content_creator"]}>
                <OrganizerDashboard />
              </RequireRole>
            }
          />

          {/* Regular User Attendee Dashboard */}
          <Route
            path="/user/dashboard"
            element={
              <RequireRole allowedRoles={["regular_user", "event_organizer", "admin", "content_creator"]}>
                <UserDashboard />
              </RequireRole>
            }
          />

          {/* Catalogs (Meetup, Event, Speech, All) */}
          <Route
            path="/catalog/:type"
            element={
              <RequireAuth>
                <CatalogPage />
              </RequireAuth>
            }
          />

          {/* Event Detail Hub with Transcript and Generated Posts */}
          <Route
            path="/events/:eventId"
            element={
              <RequireAuth>
                <EventDetailPage />
              </RequireAuth>
            }
          />

          {/* Community Feed */}

          <Route
            path="/community"
            element={
              <RequireAuth>
                <CommunityPage />
              </RequireAuth>
            }
          />

          <Route
            path="/jobs/:jobId"
            element={
              <RequireAuth>
                <JobDetailPage />
              </RequireAuth>
            }
          />
          <Route
            path="/review/:contentId"
            element={
              <RequireAuth>
                <ReviewPage />
              </RequireAuth>
            }
          />
          <Route
            path="/settings"
            element={
              <RequireAuth>
                <SettingsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/admin"
            element={
              <RequireAuth>
                <AdminPage />
              </RequireAuth>
            }
          />
          <Route
            path="/admin/fixes"
            element={
              <RequireAuth>
                <FixesPage />
              </RequireAuth>
            }
          />
          <Route path="/home" element={<Navigate to="/" replace />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
