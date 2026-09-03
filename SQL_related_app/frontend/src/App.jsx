import React, { useState } from 'react'
import { Layout, Menu, Typography } from 'antd'
import { UploadOutlined, DatabaseOutlined } from '@ant-design/icons'
import DataUpload from './components/DataUpload'
import DataSourceList from './components/DataSourceList'

const { Header, Content, Sider } = Layout
const { Title } = Typography

function App() {
  const [currentMenu, setCurrentMenu] = useState('upload')

  const renderContent = () => {
    switch (currentMenu) {
      case 'datasources':
        return <DataSourceList />
      default:
        return <DataUpload />
    }
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ background: '#001529', color: 'white', padding: '0 24px' }}>
        <Title level={3} style={{ color: 'white', margin: '16px 0' }}>
          Factory Data Management
        </Title>
      </Header>
      <Layout>
        <Sider width={200} style={{ background: '#fff' }}>
          <Menu
            mode="inline"
            selectedKeys={[currentMenu]}
            style={{ height: '100%', borderRight: 0 }}
            items={[
              {
                key: 'upload',
                icon: <UploadOutlined />,
                label: 'Upload Data',
                onClick: () => setCurrentMenu('upload')
              },
              {
                key: 'datasources',
                icon: <DatabaseOutlined />,
                label: 'Data Sources',
                onClick: () => setCurrentMenu('datasources')
              }
            ]}
          />
        </Sider>
        <Layout style={{ padding: '24px' }}>
          <Content style={{ background: '#fff', padding: 24, borderRadius: 8 }}>
            {renderContent()}
          </Content>
        </Layout>
      </Layout>
    </Layout>
  )
}

export default App
