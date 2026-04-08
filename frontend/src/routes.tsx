import { createBrowserRouter } from "react-router";
import RequireAuth from "@/components/RequireAuth";
import AdminPage from "@/pages/AdminPage";
import AnalysisStatusPage from "@/pages/AnalysisStatusPage";
import HomePage from "@/pages/HomePage";
import LoginPage from "@/pages/LoginPage";
import ProfilePage from "@/pages/ProfilePage";
import SignupPage from "@/pages/SignupPage";
import UploadPage from "@/pages/UploadPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: (
      <RequireAuth>
        <HomePage />
      </RequireAuth>
    ),
  },
  {
    path: "/profile",
    element: (
      <RequireAuth>
        <ProfilePage />
      </RequireAuth>
    ),
  },
  {
    path: "/analysis/:id",
    element: (
      <RequireAuth>
        <AnalysisStatusPage />
      </RequireAuth>
    ),
  },
  {
    path: "/admin",
    element: (
      <RequireAuth>
        <AdminPage />
      </RequireAuth>
    ),
  },
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/signup",
    element: <SignupPage />,
  },
  {
    path: "/upload",
    element: (
      <RequireAuth>
        <UploadPage />
      </RequireAuth>
    ),
  },
]);

export default router;
