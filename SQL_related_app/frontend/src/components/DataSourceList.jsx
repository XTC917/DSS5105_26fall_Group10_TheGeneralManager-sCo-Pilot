import React, { useEffect, useState } from 'react'
import {
  Table, Tag, Button, Space, message, Descriptions, Drawer, Popconfirm,
  Modal, Form, Input, Alert
} from 'antd'
import {
  ReloadOutlined, DeleteOutlined, EyeOutlined, DatabaseOutlined, EditOutlined,
  SaveOutlined
} from '@ant-design/icons'
import {
  getDataSources, deleteDataSource, getDataSourceData, updateDataSourceRows
} from '../api'

const PAGE_SIZE = 50
const PRIMARY_KEYS = {
  orders: ['order_id'],
  production_log: ['production_date', 'stage'],
  workshops: ['workshop_id', 'makes']
}
const NULLABLE_COLUMNS = {
  orders: ['completed_date', 'days_late'],
  production_log: [],
  workshops: ['max_batch_pieces']
}

const DataSourceList = () => {
  const [dataSources, setDataSources] = useState([])
  const [loading, setLoading] = useState(false)
  const [drawerVisible, setDrawerVisible] = useState(false)
  const [currentDataSource, setCurrentDataSource] = useState(null)
  const [dataPreview, setDataPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewPage, setPreviewPage] = useState(1)
  const [editRow, setEditRow] = useState(null)
  const [editVisible, setEditVisible] = useState(false)
  const [pendingUpdates, setPendingUpdates] = useState([])
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await getDataSources()
      setDataSources(res.data)
    } catch (error) {
      message.error('Failed to load data sources')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const loadPreview = async (record, page = 1) => {
    setPreviewLoading(true)
    try {
      const offset = (page - 1) * PAGE_SIZE
      const res = await getDataSourceData(record.id, PAGE_SIZE, offset)
      setDataPreview(res.data)
      setPreviewPage(page)
    } catch (error) {
      message.error('Failed to load data')
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleViewData = async (record) => {
    setCurrentDataSource(record)
    setDrawerVisible(true)
    setDataPreview(null)
    setPendingUpdates([])
    await loadPreview(record, 1)
  }

  const primaryKeys = PRIMARY_KEYS[currentDataSource?.table_name] || []

  const rowKeyObject = (row) => Object.fromEntries(
    primaryKeys.map((column) => [column, row[column]])
  )

  const rowKeyText = (row) => JSON.stringify(rowKeyObject(row))

  const openEditor = (row) => {
    const marker = rowKeyText(row)
    const staged = pendingUpdates.find(
      (item) => JSON.stringify(item.key) === marker
    )
    setEditRow(row)
    form.setFieldsValue({ ...row, ...(staged?.changes || {}) })
    setEditVisible(true)
  }

  const stageUpdate = async () => {
    const values = await form.validateFields()
    const changes = {}
    Object.entries(values).forEach(([column, value]) => {
      if (primaryKeys.includes(column)) return
      const normalized = value === '' &&
        (NULLABLE_COLUMNS[currentDataSource.table_name] || []).includes(column)
        ? null
        : value
      if (String(normalized ?? '') !== String(editRow[column] ?? '')) {
        changes[column] = normalized
      }
    })
    if (Object.keys(changes).length === 0) {
      message.info('No changed fields to stage')
      return
    }
    const update = { key: rowKeyObject(editRow), changes }
    const marker = rowKeyText(editRow)
    const alreadyStaged = pendingUpdates.some(
      (item) => JSON.stringify(item.key) === marker
    )
    if (!alreadyStaged && pendingUpdates.length >= 50) {
      message.error('A batch can contain at most 50 rows')
      return
    }
    setPendingUpdates((current) => [
      ...current.filter((item) => JSON.stringify(item.key) !== marker),
      update
    ])
    setEditVisible(false)
    setEditRow(null)
    message.success('Row change staged; save the batch to apply it')
  }

  const savePending = async () => {
    if (!currentDataSource || pendingUpdates.length === 0) return
    setSaving(true)
    try {
      const response = await updateDataSourceRows(currentDataSource.id, pendingUpdates)
      message.success(`${response.data.updated_count} row(s) updated atomically`)
      setPendingUpdates([])
      await loadPreview(currentDataSource, previewPage)
      await fetchData()
    } catch (error) {
      const detail = error.response?.data?.detail || 'Failed to update rows'
      message.error(detail)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      await deleteDataSource(id, false)
      message.success('Data source deactivated')
      fetchData()
    } catch (error) {
      message.error('Failed to delete')
    }
  }

  const columns = [
    {
      title: 'Source Name',
      dataIndex: 'source_name',
      key: 'source_name',
      render: (text) => (
        <Space>
          <DatabaseOutlined />
          <span>{text}</span>
        </Space>
      )
    },
    {
      title: 'Table Name',
      dataIndex: 'table_name',
      key: 'table_name',
      render: (text) => <Tag color="blue">{text}</Tag>
    },
    {
      title: 'Original File',
      dataIndex: 'original_file',
      key: 'original_file'
    },
    {
      title: 'Row Count',
      dataIndex: 'row_count',
      key: 'row_count'
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true
    },
    {
      title: 'Status',
      key: 'status',
      render: (_, record) => (
        <Tag color={record.is_active ? 'green' : 'red'}>
          {record.is_active ? 'Active' : 'Inactive'}
        </Tag>
      )
    },
    {
      title: 'Created At',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text) => (text ? new Date(text).toLocaleString() : '')
    },
    {
      title: 'Actions',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewData(record)}
          >
            View
          </Button>
          <Popconfirm
            title="Deactivate this data source?"
            description="The PostgreSQL table and its rows are kept. Only the catalog entry is marked inactive."
            onConfirm={() => handleDelete(record.id)}
            okText="Yes"
            cancelText="No"
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              Deactivate
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ]

  const getPreviewColumns = () => {
    if (!dataPreview || !dataPreview.columns) return []
    const columns = dataPreview.columns
      .filter((col) => col.name && col.name !== 'created_at')
      .map((col) => ({
        title: col.name,
        dataIndex: col.name,
        key: col.name,
        ellipsis: true,
        width: 120
      }))
    columns.push({
      title: 'Actions',
      key: '_actions',
      fixed: 'right',
      width: 100,
      render: (_, row) => (
        <Button size="small" icon={<EditOutlined />} onClick={() => openEditor(row)}>
          Edit
        </Button>
      )
    })
    return columns
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2>Data Source Management</h2>
        <Button icon={<ReloadOutlined />} onClick={fetchData}>Refresh</Button>
      </div>

      <Table
        columns={columns}
        dataSource={dataSources}
        loading={loading}
        rowKey="id"
        pagination={{ pageSize: 10 }}
      />

      <Drawer
        title={`Data Preview - ${currentDataSource?.source_name || ''}`}
        placement="right"
        width={800}
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
      >
        {currentDataSource && (
          <Descriptions column={2} style={{ marginBottom: 16 }}>
            <Descriptions.Item label="Table Name">{currentDataSource.table_name}</Descriptions.Item>
            <Descriptions.Item label="Row Count">{currentDataSource.row_count}</Descriptions.Item>
            <Descriptions.Item label="Original File">{currentDataSource.original_file}</Descriptions.Item>
            <Descriptions.Item label="Description">{currentDataSource.description}</Descriptions.Item>
          </Descriptions>
        )}

        {previewLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>Loading...</div>
        ) : dataPreview && (
          <>
            <Alert
              type="info"
              showIcon
              style={{ marginBottom: 12 }}
              message={`${pendingUpdates.length} pending row change(s)`}
              description="Edits are staged locally. Save applies the whole batch in one database transaction; any invalid row rolls back the entire batch."
              action={(
                <Space>
                  <Button
                    size="small"
                    onClick={() => setPendingUpdates([])}
                    disabled={pendingUpdates.length === 0 || saving}
                  >
                    Clear
                  </Button>
                  <Button
                    size="small"
                    type="primary"
                    icon={<SaveOutlined />}
                    loading={saving}
                    disabled={pendingUpdates.length === 0}
                    onClick={savePending}
                  >
                    Save batch
                  </Button>
                </Space>
              )}
            />
            <Table
              columns={getPreviewColumns()}
              dataSource={(dataPreview.data || []).map((row, i) => ({
                ...row,
                _rowKey: `${dataPreview.offset}-${i}`
              }))}
              rowKey="_rowKey"
              scroll={{ x: 'max-content' }}
              size="small"
              pagination={{
                current: previewPage,
                total: dataPreview.total,
                pageSize: PAGE_SIZE,
                showTotal: (total) => `Total ${total} rows`,
                onChange: (page) => {
                  if (currentDataSource) {
                    loadPreview(currentDataSource, page)
                  }
                }
              }}
            />
          </>
        )}
      </Drawer>

      <Modal
        title="Stage row changes"
        open={editVisible}
        onOk={stageUpdate}
        onCancel={() => {
          setEditVisible(false)
          setEditRow(null)
        }}
        okText="Stage change"
        destroyOnClose
        forceRender
      >
        <Form form={form} layout="vertical" preserve={false}>
          {(dataPreview?.columns || [])
            .filter((column) => column.name && column.name !== 'created_at')
            .map((column) => (
              <Form.Item
                key={column.name}
                name={column.name}
                label={column.name}
              >
                <Input disabled={primaryKeys.includes(column.name)} />
              </Form.Item>
            ))}
        </Form>
      </Modal>
    </div>
  )
}

export default DataSourceList
