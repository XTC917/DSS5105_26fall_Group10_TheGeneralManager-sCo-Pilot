import React, { useEffect, useState } from 'react'
import {
  Table, Tag, Button, Space, message, Descriptions, Drawer, Popconfirm
} from 'antd'
import {
  ReloadOutlined, DeleteOutlined, EyeOutlined, DatabaseOutlined
} from '@ant-design/icons'
import { getDataSources, deleteDataSource, getDataSourceData } from '../api'

const PAGE_SIZE = 50

const DataSourceList = () => {
  const [dataSources, setDataSources] = useState([])
  const [loading, setLoading] = useState(false)
  const [drawerVisible, setDrawerVisible] = useState(false)
  const [currentDataSource, setCurrentDataSource] = useState(null)
  const [dataPreview, setDataPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewPage, setPreviewPage] = useState(1)

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
    await loadPreview(record, 1)
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
            description="The SQLite table is kept. Only the catalog entry is marked inactive."
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
    return dataPreview.columns
      .filter((col) => col.name && col.name !== 'created_at')
      .map((col) => ({
        title: col.name,
        dataIndex: col.name,
        key: col.name,
        ellipsis: true,
        width: 120
      }))
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
        )}
      </Drawer>
    </div>
  )
}

export default DataSourceList
