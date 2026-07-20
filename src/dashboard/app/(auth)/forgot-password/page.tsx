import { Suspense } from "react";
import ForgotPasswordForm from "./ForgotPasswordForm";

// Public — same auth layout group as /login. ``useSearchParams`` inside
// would force a CSR bailout otherwise, so the page wraps the client form
// in a Suspense boundary (Next 16 pattern, see /login/page.tsx).
export default function ForgotPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ForgotPasswordForm />
    </Suspense>
  );
}
