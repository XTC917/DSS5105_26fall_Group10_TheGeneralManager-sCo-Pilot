import axios from "axios";
import { authHeaders } from "./authApi.js";

const usersApi = axios.create({
  baseURL: "/api/admin/users",
  timeout: 30000,
});

usersApi.interceptors.request.use((config) => {
  config.headers = { ...(config.headers || {}), ...authHeaders() };
  return config;
});

export const listPendingUsers = () => usersApi.get("/pending").then((r) => r.data);
export const listAllUsers = () => usersApi.get("/").then((r) => r.data);
export const approveUser = (id) => usersApi.post(`/${id}/approve`).then((r) => r.data);
export const rejectUser = (id) => usersApi.post(`/${id}/reject`).then((r) => r.data);
export const disableUser = (id) => usersApi.post(`/${id}/disable`).then((r) => r.data);

export default usersApi;
