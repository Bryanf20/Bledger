import apiClient from "./client";

// Verified against backend/apps/activity/{views,serializers}.py.
//   GET /activity/                     manager+ (managers see is_major
//     only; owners see everything — server-enforced by role, not a param)
//   optional filters: ?action=<key>  ?actor=<user id>  ?page=<n>
// Paginated ({count,next,previous,results}) like sales history.

export async function fetchActivity({ page = 1, action, actor } = {}) {
  const { data } = await apiClient.get("/activity/", {
    params: {
      page,
      action: action || undefined,
      actor: actor || undefined,
    },
  });
  return data; // { count, next, previous, results: ActivityLog[] }
}
