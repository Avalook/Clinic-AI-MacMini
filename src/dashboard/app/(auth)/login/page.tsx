import { Suspense } from "react";
import LoginForm from "./LoginForm";

// Suspense boundary required by Next 16 because LoginForm calls
// useSearchParams() (CSR bailout otherwise).
export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
