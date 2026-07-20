import { requireNavAccess } from "../../../lib/clinic-session";
import OpsCenter from "./OpsCenter";

export const dynamic = "force-dynamic";

export default async function OpsPage() {
  await requireNavAccess("/ops");
  return <OpsCenter />;
}

