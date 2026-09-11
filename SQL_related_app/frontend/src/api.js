import axios from 'axios'

const api = axios.create({
  baseURL: '/api/admin',
  timeout: 60000
})

export const previewExcel = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/upload/preview', formData)
}

export const importExcel = (file, tableName, ifExists = 'replace') => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('table_name', tableName)
  formData.append('if_exists', ifExists)
  return api.post('/upload/import', formData)
}

export const getImportStatus = (uploadId) => {
  return api.get(`/upload/status/${uploadId}`)
}

export const getDataSources = () => {
  return api.get('/datasources')
}

export const deleteDataSource = (id, dropTable = false) => {
  return api.delete(`/datasources/${id}`, { params: { drop_table: dropTable } })
}

export const getDataSourceData = (id, limit = 50, offset = 0) => {
  return api.get(`/datasources/${id}/data`, { params: { limit, offset } })
}
