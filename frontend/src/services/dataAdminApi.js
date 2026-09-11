import axios from "axios";

// ---------------------------------------------------------------------------
// Data Admin API client — deliberately separated from services/api.js.
// ---------------------------------------------------------------------------
// services/api.js  (fetch) -> GM Co-Pilot APIs on the main backend (:8000)
//   /api/health, /api/chat, /api/briefing, /api/discovery, /api/audit, ...
//
// This file (axios) -> Data Management APIs on the SAME main backend (:8000)
//   /api/admin/upload/*, /api/admin/datasources/*, /api/query/*
//
// vite.config.js proxies all /api/* to http://127.0.0.1:8000. No :8001.
// ---------------------------------------------------------------------------

const dataAdminApi = axios.create({
  baseURL: "/api/admin",
  timeout: 60000,
});

export const previewExcel = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return dataAdminApi.post("/upload/preview", formData);
};

export const importExcel = (file, tableName, ifExists = "replace") => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("table_name", tableName);
  formData.append("if_exists", ifExists);
  return dataAdminApi.post("/upload/import", formData);
};

export const getImportStatus = (uploadId) => {
  return dataAdminApi.get(`/upload/status/${uploadId}`);
};

export const getDataSources = () => {
  return dataAdminApi.get("/datasources/");
};

export const deleteDataSource = (id, dropTable = false) => {
  return dataAdminApi.delete(`/datasources/${id}`, { params: { drop_table: dropTable } });
};

export const getDataSourceData = (id, limit = 50, offset = 0) => {
  return dataAdminApi.get(`/datasources/${id}/data`, { params: { limit, offset } });
};

export default dataAdminApi;
