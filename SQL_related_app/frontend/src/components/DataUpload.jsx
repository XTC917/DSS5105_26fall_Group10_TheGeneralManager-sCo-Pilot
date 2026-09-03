import React, { useEffect, useRef, useState } from 'react'
import {
  Upload, Button, Table, Alert, Steps, Space, message,
  Card, Tag, Spin, Progress, Tabs
} from 'antd'
import {
  CloudUploadOutlined, CheckCircleOutlined,
  CloseCircleOutlined, LoadingOutlined, FileExcelOutlined,
  FileTextOutlined, DatabaseOutlined
} from '@ant-design/icons'
import { previewExcel, importExcel, getImportStatus } from '../api'

const { Dragger } = Upload
const { Step } = Steps
const MAX_POLLS = 60

const emptyTabState = () => ({
  currentStep: 0,
  file: null,
  previewData: null,
  importing: false,
  uploadId: null,
  importStatus: null
})

const DataUpload = () => {
  const [activeTab, setActiveTab] = useState('orders')
  const [uploadStates, setUploadStates] = useState({
    orders: emptyTabState(),
    production_log: emptyTabState(),
    workshops: emptyTabState()
  })
  const timersRef = useRef({})

  const fileTypeMapping = {
    orders: {
      label: 'Orders',
      description: 'Customer orders (orders.csv)',
      tableName: 'orders',
      icon: <FileTextOutlined style={{ fontSize: 48, color: '#1890ff' }} />,
      tabIcon: <FileTextOutlined />
    },
    production_log: {
      label: 'Production Log',
      description: 'Daily production output (production_log.csv)',
      tableName: 'production_log',
      icon: <FileExcelOutlined style={{ fontSize: 48, color: '#52c41a' }} />,
      tabIcon: <FileExcelOutlined />
    },
    workshops: {
      label: 'Workshops',
      description: 'Workshop profiles (workshops.csv)',
      tableName: 'workshops',
      icon: <DatabaseOutlined style={{ fontSize: 48, color: '#faad14' }} />,
      tabIcon: <DatabaseOutlined />
    }
  }

  const clearTimer = (tab) => {
    if (timersRef.current[tab]) {
      clearInterval(timersRef.current[tab])
      delete timersRef.current[tab]
    }
  }

  useEffect(() => {
    return () => {
      Object.keys(timersRef.current).forEach(clearTimer)
    }
  }, [])

  const updateState = (tab, updates) => {
    setUploadStates((prev) => ({
      ...prev,
      [tab]: { ...prev[tab], ...updates }
    }))
  }

  const handleUpload = async (tab, file) => {
    try {
      const res = await previewExcel(file)
      if (res.data.success) {
        updateState(tab, {
          file,
          previewData: res.data,
          currentStep: 1
        })
        message.success(`File parsed: ${res.data.total_rows} rows`)
      } else {
        message.error(res.data.error || 'Parse failed')
      }
    } catch (error) {
      message.error(error.response?.data?.detail || 'Parse failed')
    }
    return false
  }

  const handleImport = async (tab) => {
    const state = uploadStates[tab]
    const tableName = fileTypeMapping[tab].tableName
    updateState(tab, { importing: true })
    clearTimer(tab)

    try {
      const res = await importExcel(state.file, tableName, 'replace')
      const { upload_id } = res.data
      updateState(tab, { uploadId: upload_id })

      let attempts = 0
      const timer = setInterval(async () => {
        attempts += 1
        try {
          const statusRes = await getImportStatus(upload_id)
          const data = statusRes.data
          updateState(tab, { importStatus: data })

          if (['success', 'failed', 'partial'].includes(data.status) || attempts >= MAX_POLLS) {
            clearTimer(tab)
            updateState(tab, {
              importing: false,
              currentStep: 2
            })
            if (data.status === 'success') {
              message.success('Data imported successfully!')
            } else if (data.status === 'partial') {
              message.warning('Partial import completed')
            } else if (attempts >= MAX_POLLS && data.status === 'processing') {
              message.error('Import timed out')
            } else {
              message.error(`Import failed: ${data.error_message}`)
            }
          }
        } catch (error) {
          if (attempts >= MAX_POLLS) {
            clearTimer(tab)
            updateState(tab, { importing: false, currentStep: 2 })
            message.error('Failed to read import status')
          }
        }
      }, 2000)

      timersRef.current[tab] = timer
    } catch (error) {
      updateState(tab, { importing: false })
      message.error(error.response?.data?.detail || 'Import failed')
    }
  }

  const resetState = (tab) => {
    clearTimer(tab)
    updateState(tab, emptyTabState())
  }

  const renderPreview = (tab) => {
    const state = uploadStates[tab]
    const { previewData } = state
    if (!previewData) return null

    const columns = previewData.columns.map((col) => ({
      title: col,
      dataIndex: col,
      key: col,
      ellipsis: true,
      width: 120
    }))

    return (
      <div>
        <Alert
          message={`File: ${previewData.file_name} (${(previewData.file_size / 1024).toFixed(1)}KB)`}
          description={`${previewData.total_rows} rows, ${previewData.total_cols} columns. Destination table: ${fileTypeMapping[tab].tableName}`}
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <Table
          columns={columns}
          dataSource={previewData.preview_data.map((row, i) => ({ ...row, key: i }))}
          pagination={false}
          scroll={{ x: 'max-content' }}
          size="small"
          bordered
        />
        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <Button
            type="primary"
            icon={<CloudUploadOutlined />}
            loading={state.importing}
            onClick={() => handleImport(tab)}
            size="large"
          >
            Confirm Import
          </Button>
          <Button style={{ marginLeft: 8 }} onClick={() => resetState(tab)}>
            Cancel
          </Button>
        </div>
      </div>
    )
  }

  const renderProgress = (tab) => {
    const { importStatus } = uploadStates[tab]
    if (!importStatus) {
      return <Spin tip="Importing..." />
    }

    const { status, file_name, details, error_message } = importStatus
    const isComplete = ['success', 'failed', 'partial'].includes(status)

    return (
      <div>
        <Alert
          message={
            status === 'success' ? 'Import complete' :
            status === 'partial' ? 'Partial import' :
            status === 'failed' ? 'Import failed' :
            'Importing...'
          }
          description={`File: ${file_name}`}
          type={
            status === 'success' ? 'success' :
            status === 'partial' ? 'warning' :
            status === 'failed' ? 'error' : 'info'
          }
          showIcon
          style={{ marginBottom: 16 }}
        />
        {error_message && (
          <Alert
            message="Error"
            description={error_message}
            type="error"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}
        {details && details.map((detail, index) => (
          <Card
            key={index}
            size="small"
            style={{ marginBottom: 8 }}
            title={
              <Space>
                {detail.status === 'success' && <CheckCircleOutlined style={{ color: '#52c41a' }} />}
                {detail.status === 'failed' && <CloseCircleOutlined style={{ color: '#ff4d4f' }} />}
                {detail.status === 'processing' && <LoadingOutlined style={{ color: '#1890ff' }} />}
                <span>{detail.file_name}</span>
                <Tag color="blue">{detail.table_name}</Tag>
              </Space>
            }
            extra={
              <span>
                {detail.status === 'processing' && <Spin size="small" />}
                {detail.status === 'success' && `${detail.success_rows} rows`}
                {detail.status === 'failed' && <span style={{ color: 'red' }}>Failed</span>}
              </span>
            }
          >
            {detail.status === 'success' && (
              <Progress
                percent={100}
                status="success"
                format={() => `${detail.success_rows} / ${detail.total_rows}`}
              />
            )}
            {detail.status === 'failed' && detail.error_message && (
              <Alert message={detail.error_message} type="error" showIcon />
            )}
          </Card>
        ))}
        {isComplete && (
          <div style={{ marginTop: 16, textAlign: 'center' }}>
            <Button onClick={() => resetState(tab)}>Upload another file</Button>
          </div>
        )}
      </div>
    )
  }

  const renderUploadArea = (tab) => {
    const state = uploadStates[tab]
    const config = fileTypeMapping[tab]
    if (state.currentStep === 0) {
      return (
        <Dragger
          accept=".csv,.xlsx,.xls"
          beforeUpload={(file) => handleUpload(tab, file)}
          maxCount={1}
          style={{ padding: 40 }}
        >
          <p className="ant-upload-drag-icon">{config.icon}</p>
          <p className="ant-upload-text" style={{ fontSize: 16 }}>
            Click or drag to upload {config.label} file
          </p>
          <p className="ant-upload-hint">
            {config.description}
            <br />
            Supports .csv / .xlsx / .xls, max 100MB. Imports into table `{config.tableName}`.
          </p>
        </Dragger>
      )
    }
    if (state.currentStep === 1) return renderPreview(tab)
    if (state.currentStep === 2) return renderProgress(tab)
    return null
  }

  const tabItems = Object.keys(fileTypeMapping).map((key) => ({
    key,
    label: (
      <span>
        {fileTypeMapping[key].tabIcon} {fileTypeMapping[key].label}
      </span>
    ),
    children: (
      <div>
        <Steps current={uploadStates[key].currentStep} style={{ marginBottom: 30 }}>
          <Step title="Upload" description="Select file" />
          <Step title="Preview" description="Check data" />
          <Step title="Complete" description="View results" />
        </Steps>
        {renderUploadArea(key)}
      </div>
    )
  }))

  return (
    <div>
      <h2>Data Upload</h2>
      <p style={{ color: '#666', marginBottom: 20 }}>
        Upload a CSV or Excel file into one of the three SQLite tables.
        Re-importing a file replaces the existing rows in that table.
      </p>
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
    </div>
  )
}

export default DataUpload
