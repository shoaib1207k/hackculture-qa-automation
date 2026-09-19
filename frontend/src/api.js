const json = async (res) => {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
};

export const listLeads = () => fetch("/api/leads").then(json);
export const getLead = (id) => fetch(`/api/leads/${id}`).then(json);
export const scoreLead = (id, force = false) =>
  fetch(`/api/leads/${id}/score?force=${force}`, { method: "POST" }).then(json);
