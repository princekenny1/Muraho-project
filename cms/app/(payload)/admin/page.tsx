import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import config from "@payload-config";

export default async function AdminIndexPage() {
  const cookieStore = await cookies();
  const resolvedConfig = await config;
  const tokenName = `${resolvedConfig.cookiePrefix || "payload"}-token`;
  const hasAuthToken = Boolean(cookieStore.get(tokenName)?.value);

  if (!hasAuthToken) {
    redirect("/admin/login?redirect=%2Fadmin%2Fcollections%2Fstories");
  }

  redirect("/admin/collections/stories");
}
