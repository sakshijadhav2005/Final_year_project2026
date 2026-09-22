import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { RequireAuth } from "@/components/RequireAuth";
import { RequireRole } from "@/components/RequireRole";
import { AdminPage } from "@/pages/AdminPage";
import { CatalogPage } from "@/pages/CatalogPage";
import { CommunityPage } from "@/pages/CommunityPage";
import { JobDetailPage } from "@/pages/JobDetailPage";
import { LandingPage } from "@/pages/LandingPage";
import { LoginPage } from "@/pages/LoginPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { OrganizerDashboard } from "@/pages/OrganizerDashboard";
import { RegisterPage } from "@/pages/RegisterPage";
import { ReviewPage } from "@/pages/ReviewPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { UserDashboard } from "@/pages/UserDashboard";
import { useAuthStore } from "@/store/auth";

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
        <Route path="/home" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}
