import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import Layout from "./components/Layout";
import ApplicantsPage from "./pages/ApplicantsPage";
import ApplyPage from "./pages/ApplyPage";
import CheckinPage from "./pages/CheckinPage";
import EventAnalyticsPage from "./pages/EventAnalyticsPage";
import DashboardPage from "./pages/DashboardPage";
import FormBuilderPage from "./pages/FormBuilderPage";
import LotteryPage from "./pages/LotteryPage";
import MyPage from "./pages/MyPage";
import NotificationsPage from "./pages/NotificationsPage";
import NotifyPage from "./pages/NotifyPage";
import EventDetailPage from "./pages/EventDetailPage";
import EventFormPage from "./pages/EventFormPage";
import EventsPage from "./pages/EventsPage";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import NewOrgPage from "./pages/NewOrgPage";
import OrgAnalyticsPage from "./pages/OrgAnalyticsPage";
import OrgPublicPage from "./pages/OrgPublicPage";
import OrgSettingsPage from "./pages/OrgSettingsPage";
import PasswordResetConfirmPage from "./pages/PasswordResetConfirmPage";
import PasswordResetRequestPage from "./pages/PasswordResetRequestPage";
import ProfilePage from "./pages/ProfilePage";
import RegisterPage from "./pages/RegisterPage";
import VerifyEmailPage from "./pages/VerifyEmailPage";

const queryClient = new QueryClient();

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
      { path: "/verify-email", element: <VerifyEmailPage /> },
      { path: "/password-reset", element: <PasswordResetRequestPage /> },
      { path: "/password-reset/confirm", element: <PasswordResetConfirmPage /> },
      { path: "/profile", element: <ProfilePage /> },
      { path: "/events", element: <EventsPage /> },
      { path: "/events/:eventId", element: <EventDetailPage /> },
      { path: "/events/:eventId/edit", element: <EventFormPage /> },
      { path: "/events/:eventId/apply", element: <ApplyPage /> },
      { path: "/events/:eventId/form-builder", element: <FormBuilderPage /> },
      { path: "/events/:eventId/applicants", element: <ApplicantsPage /> },
      { path: "/events/:eventId/lottery", element: <LotteryPage /> },
      { path: "/events/:eventId/notify", element: <NotifyPage /> },
      { path: "/events/:eventId/checkins", element: <CheckinPage /> },
      { path: "/events/:eventId/analytics", element: <EventAnalyticsPage /> },
      { path: "/orgs/:orgId/analytics", element: <OrgAnalyticsPage /> },
      { path: "/my", element: <MyPage /> },
      { path: "/notifications", element: <NotificationsPage /> },
      { path: "/o/:slug", element: <OrgPublicPage /> },
      { path: "/dashboard", element: <DashboardPage /> },
      { path: "/organizations/new", element: <NewOrgPage /> },
      { path: "/orgs/:orgId/settings", element: <OrgSettingsPage /> },
      { path: "/orgs/:orgId/events/new", element: <EventFormPage /> },
    ],
  },
]);

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
